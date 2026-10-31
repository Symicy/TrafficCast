"""Contractul comun surse → senzori → gateway. Unitățile sunt explicite."""

from dataclasses import asdict, dataclass
import json
import math
import re

DIRECTIONS = ("N", "E", "S", "W")


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

    def __post_init__(self):
        if not isinstance(self.run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.run_id):
            raise ValueError("run_id trebuie să aibă 1–64 caractere: litere, cifre, _ sau -")
        if self.direction not in DIRECTIONS or self.sensor_id != f"E2_{self.direction}":
            raise ValueError("Identificator sau direcție de senzor invalidă")
        if self.source != "sumo":
            raise ValueError("Sursa măsurătorilor trebuie să fie SUMO")
        for name in ("sequence", "vehicle_count", "exit_vehicle_count", "tls_phase", "schema_version"):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= 2**63 - 1:
                raise ValueError(f"{name} trebuie să fie întreg nenegativ pe 64 de biți")
        if self.schema_version != 1 or self.sequence < 1 or self.tls_phase > 5:
            raise ValueError("Versiune, secvență sau fază invalidă")
        for name in ("sim_time_s", "occupancy_pct", "jam_length_m", "mean_speed_m_s"):
            value = getattr(self, name)
            if name == "mean_speed_m_s" and value is None:
                continue
            try:
                valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError(f"{name} trebuie să fie finit și nenegativ")
        if self.occupancy_pct > 100:
            raise ValueError("Ocuparea trebuie să fie între 0 și 100%")

    @property
    def topic(self):
        return f"trafficcast/J0/sensors/{self.direction}"

    @property
    def message_id(self):
        return f"{self.run_id}:{self.sensor_id}:{self.sequence}"

    def to_json(self):
        return json.dumps(asdict(self), allow_nan=False)

    @classmethod
    def from_json(cls, payload, topic):
        message = cls(**json.loads(payload))
        if message.topic != topic:
            raise ValueError("Topic-ul nu corespunde direcției din mesaj")
        return message
