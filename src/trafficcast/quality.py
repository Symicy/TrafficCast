"""Calitatea fluxului de măsurători, independentă de semaforizare."""

from collections import OrderedDict


class ReceptionTracker:
    def __init__(self):
        self.last = OrderedDict()

    def observe(self, measurement):
        key = measurement.run_id, measurement.sensor_id
        previous = self.last.get(key)
        if previous and measurement.sequence <= previous[0]:
            return "out_of_order"
        result = "ok"
        if previous and measurement.sim_time_s <= previous[1]:
            result = "stale"
        elif measurement.sequence != (previous[0] + 1 if previous else 1):
            result = "sequence_gap"
        self.last[key] = measurement.sequence, measurement.sim_time_s
        self.last.move_to_end(key)
        while len(self.last) > 1024:
            self.last.popitem(last=False)
        return result
