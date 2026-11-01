from itertools import islice
import xml.etree.ElementTree as ET
from types import SimpleNamespace
import subprocess
import sys

import pytest

from trafficcast.sources import detector_groups, read_direction, run_scenario, sumo_frames
from trafficcast import runtime
from test_pipeline import scenario  # Refolosește copiile izolate ale ambelor scenarii.


def connection_for_readings(counts, speeds):
    return SimpleNamespace(
        lanearea=SimpleNamespace(
            getLastStepVehicleNumber=lambda item: counts[item],
            getLastStepMeanSpeed=lambda item: speeds[item],
            getLastStepOccupancy=lambda item: {"a": 20, "b": 60}[item],
            getJamLengthMeters=lambda item: {"a": 15, "b": 40}[item],
        ),
        inductionloop=SimpleNamespace(getLastStepVehicleNumber=lambda _: 1),
        simulation=SimpleNamespace(getTime=lambda: 42),
    )


def test_direction_aggregation_uses_vehicle_weights_and_longest_queue():
    connection = connection_for_readings({"a": 1, "b": 3}, {"a": 10, "b": 2})
    reading = read_direction(connection, "N", (["a", "b"], ["x", "y"]), 3)
    assert reading == dict(sim_time_s=42, direction="N", vehicle_count=4,
                           mean_speed_m_s=4, occupancy_pct=40, jam_length_m=40,
                           exit_vehicle_count=2, tls_phase=3)


@pytest.mark.parametrize("counts,speeds,expected", [
    ({"a": 0, "b": 0}, {"a": -1, "b": -1}, None),
    ({"a": 1, "b": 0}, {"a": 0, "b": -1}, 0),
    ({"a": 1, "b": 3}, {"a": -1, "b": 2}, 2),
])
def test_missing_speed_and_stopped_vehicles(counts, speeds, expected):
    reading = read_direction(connection_for_readings(counts, speeds), "N", (["a", "b"], ["x"]), 0)
    assert reading["mean_speed_m_s"] == expected


def test_missing_lane_detector_is_rejected():
    connection = SimpleNamespace(
        edge=SimpleNamespace(getLaneNumber=lambda _: 2),
        lanearea=SimpleNamespace(getIDList=lambda: ["E2_N_0"], getLaneID=lambda _: "N_in_0"),
        inductionloop=None,
    )
    with pytest.raises(ValueError, match="N_in"):
        detector_groups(connection)


def test_missing_native_executable_explains_setup(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "find_binary", lambda _: None)
    with pytest.raises(RuntimeError, match="PATH și SUMO_HOME"):
        runtime.sumo_executable("sumo", tmp_path, "native")


def test_cli_cannot_mix_continuous_and_finite_steps():
    result = subprocess.run([sys.executable, "-m", "trafficcast", "run", "--continuous", "--steps", "5"],
                            capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert result.returncode == 2
    assert "not allowed" in result.stderr


def test_full_fixed_simulation_has_no_collisions_teleports_or_unfinished_trips(scenario):
    run_scenario(scenario, "headless", "auto")
    results = scenario.parent / "results"
    last = ET.parse(results / "summary.xml").getroot().findall("step")[-1].attrib
    assert int(last["collisions"]) == int(last["teleports"]) == int(last["discarded"]) == 0
    assert int(last["running"]) == int(last["waiting"]) == 0
    assert int(last["inserted"]) == int(last["arrived"]) == 780
    trips = ET.parse(results / "tripinfo.xml").getroot().findall("tripinfo")
    assert len(trips) == 780
    if (results / "vehroute.xml").exists():
        vehicles = ET.parse(results / "vehroute.xml").getroot().findall("vehicle")
        routes = {vehicle.get("id"): vehicle.find("route").get("edges") for vehicle in vehicles}
        assert len(set(routes.values())) == 12
        straight = {"N_in S_out", "E_in W_out", "S_in N_out", "W_in E_out"}
        used = {trip.get("departLane")[-1] for trip in trips if routes[trip.get("id")] in straight}
        assert used == {"0", "1"}


def test_continuous_demand_survives_original_flow_end_without_reset(scenario):
    import traci

    route_file = scenario.parent / "traffic.rou.xml"
    tree = ET.parse(route_file)
    for flow in tree.getroot().findall("flow"):
        flow.set("end", "10")
    tree.write(route_file, encoding="utf-8", xml_declaration=True)
    frames = sumo_frames(scenario, None, False, "auto", continuous=True)
    try:
        observed = list(islice(frames, 100))
        connection = traci.getConnection("trafficcast")
        assert observed[-1]["N"]["sim_time_s"] == 100
        assert any(".continuous." in vehicle for vehicle in connection.vehicle.getIDList())
        assert any(frame["N"]["vehicle_count"] > 0 for frame in observed[70:])
        assert connection.simulation.getCollidingVehiclesNumber() == 0
    finally:
        frames.close()


def test_v2_exit_passages_count_every_vehicle_once(scenario):
    frames = sumo_frames(scenario, 2400, False, "auto")
    total = 0
    try:
        for frame in frames:
            assert all(item["quality"] == "ok" for item in frame.values())
            total += sum(lane.passed_vehicle_count for item in frame.values() for lane in item["exits"])
    finally:
        frames.close()
    assert total == 780


def test_variable_profile_continues_in_new_cycles(scenario):
    import traci

    frames = sumo_frames(scenario, None, False, "auto", continuous=True,
                         profile="balanced", demand_duration=20, seed=42)
    try:
        observed = list(islice(frames, 100))
        connection = traci.getConnection("trafficcast")
        assert observed[-1]["N"]["sim_time_s"] == 100
        assert any(".profile.3." in item or ".profile.4." in item for item in connection.vehicle.getIDList())
    finally:
        frames.close()
