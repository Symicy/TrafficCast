"""Măsurători pe bandă, debite E1 și ceasul de roșu în timpul simulatorului."""

from collections import defaultdict, deque

from .messages import DIRECTIONS, ExitMeasurement, LaneMeasurement


class Telemetry:
    def __init__(self, connection, groups):
        self.connection = connection
        self.groups = groups
        self.lanes = {}
        self.exits = {}
        self.red_start = {direction: 0 for direction in DIRECTIONS}
        self.passed = defaultdict(deque)
        self.previous_passes = defaultdict(set)
        self.completed_vehicle_ids = set()
        self.started = connection.simulation.getTime()
        self.flow_started = defaultdict(lambda: self.started)
        for entries, exits in groups.values():
            for detector in entries:
                self.lanes[detector] = (connection.lanearea.getLaneID(detector),
                                        connection.lanearea.getLength(detector))
            for detector in exits:
                self.exits[detector] = connection.inductionloop.getLaneID(detector)

    def read_lane(self, detector):
        from traci.exceptions import TraCIException

        lane, length = self.lanes[detector]
        try:
            domain = self.connection.lanearea
            count = domain.getLastStepVehicleNumber(detector)
            halted = domain.getLastStepHaltingNumber(detector)
            speed = domain.getLastStepMeanSpeed(detector)
            occupancy = domain.getLastStepOccupancy(detector)
            jam = domain.getJamLengthMeters(detector)
            return LaneMeasurement(detector, lane, count, halted, speed if speed >= 0 else None,
                                   occupancy, jam, length, jam >= 0.9 * length)
        except (TraCIException, ValueError):
            return LaneMeasurement(detector, lane, None, None, None, None, None, length,
                                   status="unavailable")

    def read_exit(self, detector, now):
        from traci.exceptions import TraCIException

        window = max(0.001, min(60, now - self.flow_started[detector]))
        try:
            domain = self.connection.inductionloop
            count = domain.getLastStepVehicleNumber(detector)
            complete = {(item[0], item[2], item[3]) for item in domain.getVehicleData(detector) if item[3] >= 0}
            candidates = complete - self.previous_passes[detector]
            new_ids = {item[0] for item in candidates} - self.completed_vehicle_ids
            newly_passed = len(new_ids)
            self.completed_vehicle_ids.update(new_ids)
            self.previous_passes[detector] = complete
            history = self.passed[detector]
            history.append((now, newly_passed))
            while history and history[0][0] <= now - 60:
                history.popleft()
            flow = sum(number for _, number in history) * 3600 / window
            return ExitMeasurement(detector, self.exits[detector], count, newly_passed, flow, window)
        except (TraCIException, ValueError):
            # Nu prelungim un debit vechi peste o întrerupere de observație.
            self.passed[detector].clear()
            self.previous_passes[detector].clear()
            self.flow_started[detector] = now
            return ExitMeasurement(detector, self.exits[detector], None, None, None, window,
                                   status="unavailable")

    def frame(self):
        connection = self.connection
        now = connection.simulation.getTime()
        phase = connection.trafficlight.getPhase("J0")
        elapsed = connection.trafficlight.getSpentDuration("J0")
        state = connection.trafficlight.getRedYellowGreenState("J0")
        frame = {}
        for direction, (entries, exits) in self.groups.items():
            green, yellow = (0, 1) if direction in ("N", "S") else (3, 4)
            if phase in (green, yellow):
                self.red_start[direction] = None
            elif self.red_start[direction] is None:
                self.red_start[direction] = now - elapsed
            lanes = tuple(self.read_lane(detector) for detector in entries)
            out = tuple(self.read_exit(detector, now) for detector in exits)
            known = [item for item in lanes if item.status == "ok"]
            available = [item for item in known if item.vehicle_count > 0 and item.mean_speed_m_s is not None]
            weight = sum(item.vehicle_count for item in available)
            frame[direction] = dict(
                sim_time_s=now, direction=direction, tls_phase=phase, schema_version=2,
                vehicle_count=sum(item.vehicle_count for item in known),
                halting_count=sum(item.halting_count for item in known),
                mean_speed_m_s=sum(item.mean_speed_m_s * item.vehicle_count for item in available) / weight if weight else None,
                occupancy_pct=sum(item.occupancy_pct for item in known) / len(known) if known else 0,
                jam_length_m=max((item.jam_length_m for item in known), default=0),
                exit_vehicle_count=sum(item.vehicle_count for item in out if item.status == "ok"),
                lanes=lanes, exits=out, phase_elapsed_s=elapsed, tls_state=state,
                red_elapsed_s=0 if self.red_start[direction] is None else now - self.red_start[direction],
                quality="ok" if all(item.status == "ok" for item in (*lanes, *out)) else "degraded",
            )
        # O schimbare de bandă la E1 poate apărea în două detectoare. Numărăm
        # vehiculul o dată și eliberăm memoria când părăsește rețeaua livrată.
        self.completed_vehicle_ids.intersection_update(connection.vehicle.getIDList())
        return frame
