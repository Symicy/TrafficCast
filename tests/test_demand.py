from pathlib import Path

from trafficcast.demand import DemandModel, intervals, write_demand

SCENARIO = Path(__file__).resolve().parents[1] / "simulation/intersection-urban/intersection.sumocfg"


def test_same_seed_produces_identical_departures_and_routes(tmp_path):
    first, second = tmp_path / "one.xml", tmp_path / "two.xml"
    count = write_demand(SCENARIO, "switching", 42, 300, first)
    assert count > 0
    assert count == write_demand(SCENARIO, "switching", 42, 300, second)
    assert first.read_bytes() == second.read_bytes()
    write_demand(SCENARIO, "switching", 43, 300, second)
    assert first.read_bytes() != second.read_bytes()


def test_switching_profile_reverses_major_axis():
    north = list(intervals("switching", 900, "N", 7.5))
    east = list(intervals("switching", 900, "E", 12))
    assert north[0][2] > east[0][2]
    assert north[1][2] < east[1][2]


def test_left_heavy_changes_turn_share_without_changing_geometry():
    model = DemandModel(SCENARIO)
    vehicles = model.vehicles("left-heavy", 42, 1800)
    assert all(float(first["depart"]) <= float(second["depart"]) for first, second in zip(vehicles, vehicles[1:]))
    left = {"NE", "ES", "SW", "WN"}
    assert sum(item["route"] in left for item in vehicles) / len(vehicles) > 0.35
