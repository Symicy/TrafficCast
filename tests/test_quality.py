from trafficcast.messages import Measurement
from trafficcast.quality import ReceptionTracker


def sample(sequence=1, time=1):
    return Measurement("quality-test", "E2_N", "N", sequence, time, "sumo", 0, None, 0, 0, 0, 0)


def test_reception_reports_gaps_and_does_not_rewind_on_old_packets():
    tracker = ReceptionTracker()
    assert tracker.observe(sample()) == "ok"
    assert tracker.observe(sample(3, 3)) == "sequence_gap"
    assert tracker.observe(sample(2, 2)) == "out_of_order"
    assert tracker.observe(sample(4, 3)) == "stale"
    assert tracker.observe(sample(5, 5)) == "ok"
