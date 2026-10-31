from dataclasses import replace
import math

import pytest

from trafficcast.gateway import Store
from trafficcast.messages import Measurement


def sample():
    return Measurement("test-1", "E2_N", "N", 1, 10, "sumo", 2, None, 5, 7, 1, 0)


@pytest.mark.parametrize("changes", [
    {"vehicle_count": -1}, {"vehicle_count": True}, {"sim_time_s": math.nan},
    {"jam_length_m": math.inf}, {"occupancy_pct": 101}, {"direction": "X"},
    {"sensor_id": "E2_E"}, {"schema_version": 2}, {"run_id": "bad/run"},
    {"vehicle_count": 2**64}, {"sim_time_s": 10**1000},
    {"source": "external"},
])
def test_invalid_measurement(changes):
    with pytest.raises(ValueError):
        replace(sample(), **changes)


def test_topic_must_match_payload():
    with pytest.raises(ValueError):
        Measurement.from_json(sample().to_json(), "trafficcast/J0/sensors/E")


def test_sqlite_deduplicates_qos1_and_separates_runs(tmp_path):
    store = Store(tmp_path / "gateway.sqlite3")
    try:
        assert store.insert(sample())
        assert not store.insert(sample())
        assert store.insert(replace(sample(), run_id="test-2"))
        assert store.db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0] == 2
        assert store.db.execute("SELECT mean_speed_m_s FROM measurements LIMIT 1").fetchone()[0] is None
    finally:
        store.close()
