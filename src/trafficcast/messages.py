"""Contracte JSON pentru măsurători v1/v2; unități și calitate explicite."""

from dataclasses import asdict, dataclass
import json
import math
import re

DIRECTIONS = ("N", "E", "S", "W")
EXTENDED_FIELDS = ("halting_count", "lanes", "exits", "phase_elapsed_s",
                   "red_elapsed_s", "tls_state", "quality")


def integer(value, name):
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValueError(f"{name} trebuie să fie întreg nenegativ pe 64 de biți")


def number(value, name, optional=False):
    if optional and value is None:
        return
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} trebuie să fie finit și nenegativ")


@dataclass(frozen=True)
class LaneMeasurement:
    detector_id: str
    lane_id: str
    vehicle_count: int | None
    halting_count: int | None
    mean_speed_m_s: float | None
    occupancy_pct: float | None
    jam_length_m: float | None
    detector_length_m: float
    coverage_limited: bool = False
    status: str = "ok"

    def __post_init__(self):
        if not isinstance(self.detector_id, str) or not isinstance(self.lane_id, str):
            raise ValueError("Identificatori de bandă invalizi")
        number(self.detector_length_m, "detector_length_m")
        if self.detector_length_m <= 0 or type(self.coverage_limited) is not bool:
            raise ValueError("Acoperire invalidă")
        if self.status not in ("ok", "unavailable"):
            raise ValueError("Stare de detector invalidă")
        values = (self.vehicle_count, self.halting_count, self.mean_speed_m_s,
                  self.occupancy_pct, self.jam_length_m)
        if self.status == "unavailable":
            if any(value is not None for value in values) or self.coverage_limited:
                raise ValueError("Citirea indisponibilă trebuie marcată prin null")
            return
        integer(self.vehicle_count, "vehicle_count")
        integer(self.halting_count, "halting_count")
        number(self.mean_speed_m_s, "mean_speed_m_s", optional=True)
        number(self.occupancy_pct, "occupancy_pct")
        number(self.jam_length_m, "jam_length_m")
        if self.occupancy_pct > 100:
            raise ValueError("Ocuparea depășește 100%")


@dataclass(frozen=True)
class ExitMeasurement:
    detector_id: str
    lane_id: str
    vehicle_count: int | None
    passed_vehicle_count: int | None
    flow_veh_h: float | None
    window_s: float
    status: str = "ok"

    def __post_init__(self):
        if not isinstance(self.detector_id, str) or not isinstance(self.lane_id, str):
            raise ValueError("Identificatori de ieșire invalizi")
        number(self.window_s, "window_s")
        if self.window_s <= 0 or self.window_s > 60 or self.status not in ("ok", "unavailable"):
            raise ValueError("Fereastră sau stare E1 invalidă")
        values = (self.vehicle_count, self.passed_vehicle_count, self.flow_veh_h)
        if self.status == "unavailable":
            if any(value is not None for value in values):
                raise ValueError("Citirea E1 indisponibilă trebuie marcată prin null")
        else:
            integer(self.vehicle_count, "vehicle_count")
            integer(self.passed_vehicle_count, "passed_vehicle_count")
            number(self.flow_veh_h, "flow_veh_h")


@dataclass(frozen=True)
class Measurement:
    run_id: str
    sensor_id: str
    direction: str
    sequence: int
    sim_time_s: float
    source: str
    vehicle_count: int
    mean_speed_m_s: float | None
    occupancy_pct: float
    jam_length_m: float
    exit_vehicle_count: int
    tls_phase: int
    schema_version: int = 1
    halting_count: int | None = None
    lanes: tuple = ()
    exits: tuple = ()
    phase_elapsed_s: float | None = None
    red_elapsed_s: float | None = None
    tls_state: str | None = None
    quality: str | None = None

    def __post_init__(self):
        if not isinstance(self.run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.run_id):
            raise ValueError("run_id trebuie să aibă 1–64 caractere: litere, cifre, _ sau -")
        if self.direction not in DIRECTIONS or self.sensor_id != f"E2_{self.direction}":
            raise ValueError("Identificator sau direcție de senzor invalidă")
        if self.source != "sumo":
            raise ValueError("Sursa măsurătorilor trebuie să fie SUMO")
        for name in ("sequence", "vehicle_count", "exit_vehicle_count", "tls_phase", "schema_version"):
            integer(getattr(self, name), name)
        if self.schema_version not in (1, 2) or self.sequence < 1 or self.tls_phase > 5:
            raise ValueError("Versiune, secvență sau fază invalidă")
        for name in ("sim_time_s", "occupancy_pct", "jam_length_m", "mean_speed_m_s"):
            number(getattr(self, name), name, optional=name == "mean_speed_m_s")
        if self.occupancy_pct > 100:
            raise ValueError("Ocuparea trebuie să fie între 0 și 100%")
        if self.schema_version == 1:
            if self.lanes or self.exits or any(getattr(self, name) is not None
                    for name in EXTENDED_FIELDS if name not in ("lanes", "exits")):
                raise ValueError("Câmpurile extinse cer schema_version=2")
            return
        if not isinstance(self.lanes, (list, tuple)) or not isinstance(self.exits, (list, tuple)):
            raise ValueError("Liste de benzi/ieșiri invalide")
        object.__setattr__(self, "lanes", tuple(
            LaneMeasurement(**item) if isinstance(item, dict) else item for item in self.lanes))
        object.__setattr__(self, "exits", tuple(
            ExitMeasurement(**item) if isinstance(item, dict) else item for item in self.exits))
        if not self.lanes or not self.exits:
            raise ValueError("Măsurătoarea v2 cere benzi și ieșiri")
        integer(self.halting_count, "halting_count")
        number(self.phase_elapsed_s, "phase_elapsed_s")
        number(self.red_elapsed_s, "red_elapsed_s")
        if not isinstance(self.tls_state, str) or not re.fullmatch(r"[rgyG]{4}|[rgyG]{16}", self.tls_state):
            raise ValueError("Stare TLS invalidă")
        for items, cls, edge, prefix in ((self.lanes, LaneMeasurement, "in", f"E2_{self.direction}"),
                                        (self.exits, ExitMeasurement, "out", f"E1_{self.direction}_out")):
            if any(not isinstance(item, cls) for item in items):
                raise ValueError("Citire de bandă invalidă")
            if len({item.lane_id for item in items}) != len(items) or len({item.detector_id for item in items}) != len(items):
                raise ValueError("Benzi sau detectoare duplicate")
            for item in items:
                if not re.fullmatch(rf"{self.direction}_{edge}_[0-9]+", item.lane_id):
                    raise ValueError("Banda nu corespunde direcției")
                if item.detector_id != prefix and not re.fullmatch(rf"{prefix}_[0-9]+", item.detector_id):
                    raise ValueError("Detectorul nu corespunde direcției")
        expected = "ok" if all(item.status == "ok" for item in (*self.lanes, *self.exits)) else "degraded"
        if self.quality != expected:
            raise ValueError("Calitatea nu corespunde citirilor")
        known = [item for item in self.lanes if item.status == "ok"]
        if self.vehicle_count != sum(item.vehicle_count for item in known) or self.halting_count != sum(item.halting_count for item in known):
            raise ValueError("Totalurile nu corespund benzilor")
        if self.exit_vehicle_count != sum(item.vehicle_count for item in self.exits if item.status == "ok"):
            raise ValueError("Totalul ieșirilor este inconsistent")

    @property
    def topic(self):
        return f"trafficcast/J0/sensors/{self.direction}"

    @property
    def message_id(self):
        return f"{self.run_id}:{self.sensor_id}:{self.sequence}"

    def to_dict(self):
        result = asdict(self)
        if self.schema_version == 1:
            for name in EXTENDED_FIELDS:
                result.pop(name)
        else:
            result["lanes"] = [asdict(item) for item in self.lanes]
            result["exits"] = [asdict(item) for item in self.exits]
        return result

    def to_json(self):
        return json.dumps(self.to_dict(), allow_nan=False)

    @classmethod
    def from_json(cls, payload, topic):
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("Mesajul trebuie să fie un obiect JSON")
        if data.get("schema_version", 1) == 1 and any(name in data for name in EXTENDED_FIELDS):
            raise ValueError("Câmpuri v2 într-un mesaj v1")
        message = cls(**data)
        if message.topic != topic:
            raise ValueError("Topic-ul nu corespunde direcției din mesaj")
        return message
