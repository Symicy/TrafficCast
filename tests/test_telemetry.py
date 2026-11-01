from dataclasses import replace
import json
import sqlite3

import pytest

from trafficcast.gateway import Store
from trafficcast.messages import ExitMeasurement, LaneMeasurement, Measurement
from trafficcast.telemetry import Telemetry


def v2_sample():
    lane = LaneMeasurement("E2_N_0", "N_in_0", 3, 2, 1.5, 10, 12, 150)
    exit = ExitMeasurement("E1_N_out_0", "N_out_0", 1, 1, 180, 20)
    return Measurement("v2-test", "E2_N", "N", 1, 20, "sumo", 3, 1.5, 10, 12, 1, 0,
                       schema_version=2, halting_count=2, lanes=(lane,), exits=(exit,),
                       phase_elapsed_s=20, red_elapsed_s=0, tls_state="GrGr", quality="ok")


def test_v2_round_trip_and_normalized_storage(tmp_path):
    sample = v2_sample()
    assert Measurement.from_json(sample.to_json(), sample.topic) == sample
    store = Store(tmp_path / "data.sqlite3")
    try:
        assert store.insert(sample)
        assert not store.insert(sample)
        assert store.db.execute("SELECT halting_count,quality,schema_version FROM measurements").fetchone() == (2, "ok", 2)
        assert store.db.execute("SELECT lane_id,halting_count FROM measurement_lanes").fetchone() == ("N_in_0", 2)
        assert store.db.execute("SELECT passed_vehicle_count FROM measurement_exits").fetchone() == (1,)
    finally:
        store.close()


@pytest.mark.parametrize("changes", [dict(halting_count=9), dict(phase_elapsed_s=-1),
                                     dict(quality="degraded"), dict(tls_state="wrong"),
                                     dict(lanes=()), dict(red_elapsed_s=float("inf"))])
def test_invalid_v2_measurements_are_rejected(changes):
    with pytest.raises(ValueError):
        replace(v2_sample(), **changes)


def test_unavailable_values_are_null_and_not_good_zero_measurements(tmp_path):
    sample = v2_sample()
    unknown = LaneMeasurement("E2_N_0", "N_in_0", None, None, None, None, None, 150, status="unavailable")
    message = replace(sample, lanes=(unknown,), vehicle_count=0, halting_count=0,
                      mean_speed_m_s=None, occupancy_pct=0, jam_length_m=0, quality="degraded")
    assert message.lanes[0].vehicle_count is None
    assert Measurement.from_json(message.to_json(), message.topic).quality == "degraded"


def test_real_sumo_halting_count_can_differ_from_last_step_observation_count():
    # Observat efectiv în SUMO 1.28 la schimbarea benzii/ieșirea din zona E2.
    lane = LaneMeasurement("E2_N_0", "N_in_0", 0, 1, None, 3.333, 5, 150)
    assert lane.status == "ok"


def test_existing_v1_database_is_migrated_without_losing_rows(tmp_path):
    path = tmp_path / "old.sqlite3"
    sample = Measurement("legacy", "E2_N", "N", 1, 1, "sumo", 0, None, 0, 0, 0, 0)
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE measurements (
            run_id TEXT NOT NULL, sensor_id TEXT NOT NULL, sequence INTEGER NOT NULL,
            direction TEXT NOT NULL, sim_time_s REAL NOT NULL, source TEXT NOT NULL,
            vehicle_count INTEGER NOT NULL, mean_speed_m_s REAL, occupancy_pct REAL NOT NULL,
            jam_length_m REAL NOT NULL, exit_vehicle_count INTEGER NOT NULL, tls_phase INTEGER NOT NULL,
            received_at_utc TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(run_id,sensor_id,sequence))""")
        db.execute("INSERT INTO measurements VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   ("legacy", "E2_N", 1, "N", 1, "sumo", 0, None, 0, 0, 0, 0, "old", sample.to_json()))
    store = Store(path)
    try:
        assert store.db.execute("SELECT schema_version,payload FROM measurements").fetchone() == (1, sample.to_json())
        assert store.insert(v2_sample())
        assert store.db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0] == 2
    finally:
        store.close()


def test_exit_count_deduplicates_completed_passes_and_uses_bounded_window():
    from collections import defaultdict
    from types import SimpleNamespace

    domain = SimpleNamespace(getLastStepVehicleNumber=lambda _: 1,
                             getVehicleData=lambda _: [("car", 5, 1.1, 1.8, "car")])
    telemetry = Telemetry.__new__(Telemetry)
    telemetry.connection = SimpleNamespace(inductionloop=domain)
    telemetry.started = 0
    telemetry.flow_started = defaultdict(lambda: 0)
    telemetry.exits = {"loop": "N_out_0", "other-lane": "N_out_1"}
    from collections import deque
    telemetry.passed = defaultdict(deque)
    telemetry.previous_passes = defaultdict(set)
    telemetry.completed_vehicle_ids = set()
    assert telemetry.read_exit("loop", 2).passed_vehicle_count == 1
    assert telemetry.read_exit("other-lane", 2).passed_vehicle_count == 0
    assert telemetry.read_exit("loop", 3).passed_vehicle_count == 0
    assert telemetry.read_exit("loop", 70).flow_veh_h == 0


def test_v1_wire_payload_cannot_hide_v2_fields_as_null():
    payload = Measurement("legacy", "E2_N", "N", 1, 1, "sumo", 0, None, 0, 0, 0, 0).to_dict()
    payload["halting_count"] = None
    with pytest.raises(ValueError):
        Measurement.from_json(json.dumps(payload), "trafficcast/J0/sensors/N")


def test_live_frame_aggregates_lane_details_consistently():
    from types import SimpleNamespace

    telemetry = Telemetry.__new__(Telemetry)
    telemetry.groups = {"N": (["a", "b"], ["x", "y"])}
    telemetry.red_start = {"N": 0}
    telemetry.completed_vehicle_ids = set()
    telemetry.connection = SimpleNamespace(
        simulation=SimpleNamespace(getTime=lambda: 42),
        trafficlight=SimpleNamespace(getPhase=lambda _: 0, getSpentDuration=lambda _: 7,
                                     getRedYellowGreenState=lambda _: "GrGr"),
        vehicle=SimpleNamespace(getIDList=lambda: []),
    )
    lanes = {"a": LaneMeasurement("E2_N_0", "N_in_0", 1, 1, 10, 20, 15, 150),
             "b": LaneMeasurement("E2_N_1", "N_in_1", 3, 2, 2, 60, 40, 150)}
    telemetry.read_lane = lambda item: lanes[item]
    telemetry.read_exit = lambda item, now: ExitMeasurement("E1_N_out_0" if item == "x" else "E1_N_out_1",
                                                          "N_out_0" if item == "x" else "N_out_1", 1, 1, 60, 60)
    reading = telemetry.frame()["N"]
    assert reading["vehicle_count"] == 4
    assert reading["halting_count"] == 3
    assert reading["mean_speed_m_s"] == 4
    assert reading["occupancy_pct"] == 40
    assert reading["jam_length_m"] == 40
    assert reading["exit_vehicle_count"] == 2
    assert reading["quality"] == "ok"
