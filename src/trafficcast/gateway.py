"""Gateway MQTT pentru validarea și stocarea măsurătorilor de trafic."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from threading import Lock
import time

from .messages import DIRECTIONS, Measurement
from .quality import ReceptionTracker
from .runtime import Shutdown
from .tracing import event, trace
from .transport import close, connect


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS measurements (
                run_id TEXT NOT NULL, sensor_id TEXT NOT NULL,
                sequence INTEGER NOT NULL, direction TEXT NOT NULL,
                sim_time_s REAL NOT NULL, source TEXT NOT NULL,
                vehicle_count INTEGER NOT NULL, mean_speed_m_s REAL,
                occupancy_pct REAL NOT NULL, jam_length_m REAL NOT NULL,
                exit_vehicle_count INTEGER NOT NULL, tls_phase INTEGER NOT NULL,
                received_at_utc TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY (run_id, sensor_id, sequence)
            )
        """)
        additions = dict(schema_version="INTEGER NOT NULL DEFAULT 1", halting_count="INTEGER",
                         phase_elapsed_s="REAL", red_elapsed_s="REAL", tls_state="TEXT",
                         quality="TEXT", reception_quality="TEXT NOT NULL DEFAULT 'ok'")
        existing = {row[1] for row in self.db.execute("PRAGMA table_info(measurements)")}
        with self.db:
            for name, kind in additions.items():
                if name not in existing:
                    self.db.execute(f"ALTER TABLE measurements ADD COLUMN {name} {kind}")
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS measurement_lanes (
                    run_id TEXT NOT NULL, sensor_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    lane_id TEXT NOT NULL, detector_id TEXT NOT NULL, vehicle_count INTEGER,
                    halting_count INTEGER, mean_speed_m_s REAL, occupancy_pct REAL, jam_length_m REAL,
                    detector_length_m REAL NOT NULL, coverage_limited INTEGER NOT NULL, status TEXT NOT NULL,
                    PRIMARY KEY (run_id,sensor_id,sequence,lane_id),
                    FOREIGN KEY (run_id,sensor_id,sequence)
                        REFERENCES measurements(run_id,sensor_id,sequence) ON DELETE CASCADE
                )
            """)
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS measurement_exits (
                    run_id TEXT NOT NULL, sensor_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    lane_id TEXT NOT NULL, detector_id TEXT NOT NULL, vehicle_count INTEGER,
                    passed_vehicle_count INTEGER, flow_veh_h REAL, window_s REAL NOT NULL, status TEXT NOT NULL,
                    PRIMARY KEY (run_id,sensor_id,sequence,lane_id),
                    FOREIGN KEY (run_id,sensor_id,sequence)
                        REFERENCES measurements(run_id,sensor_id,sequence) ON DELETE CASCADE
                )
            """)

    def insert(self, message, reception_quality="ok"):
        data = {name: getattr(message, name) for name in (
            "run_id", "sensor_id", "sequence", "direction", "sim_time_s", "source",
            "vehicle_count", "mean_speed_m_s", "occupancy_pct", "jam_length_m",
            "exit_vehicle_count", "tls_phase", "schema_version", "halting_count",
            "phase_elapsed_s", "red_elapsed_s", "tls_state", "quality")}
        data.update(received_at_utc=datetime.now(timezone.utc).isoformat(),
                    payload=message.to_json(), reception_quality=reception_quality)
        with self.db:
            cursor = self.db.execute(
                f"INSERT OR IGNORE INTO measurements ({','.join(data)}) VALUES ({','.join('?' for _ in data)})",
                tuple(data.values()))
            if cursor.rowcount != 1:
                return False
            prefix = message.run_id, message.sensor_id, message.sequence
            self.db.executemany("INSERT INTO measurement_lanes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                (*prefix, lane.lane_id, lane.detector_id, lane.vehicle_count, lane.halting_count,
                 lane.mean_speed_m_s, lane.occupancy_pct, lane.jam_length_m, lane.detector_length_m,
                 int(lane.coverage_limited), lane.status) for lane in message.lanes])
            self.db.executemany("INSERT INTO measurement_exits VALUES (?,?,?,?,?,?,?,?,?,?)", [
                (*prefix, lane.lane_id, lane.detector_id, lane.vehicle_count, lane.passed_vehicle_count,
                 lane.flow_veh_h, lane.window_s, lane.status) for lane in message.exits])
        return True

    def close(self):
        self.db.close()


def run_gateway(host, port, db, stale_after):
    with Shutdown() as stop:
        _run_gateway(host, port, db, stale_after, stop)


def _run_gateway(host, port, db, stale_after, stop):
    lock = Lock()
    last_seen = {direction: time.monotonic() for direction in DIRECTIONS}
    warned = set()
    failure = []
    store = Store(db)
    tracker = ReceptionTracker()

    def on_message(client, userdata, packet):
        try:
            measurement = Measurement.from_json(packet.payload, packet.topic)
        except (ValueError, TypeError, UnicodeError) as exc:
            print(f"RESPINS {packet.topic}: {exc}", flush=True)
            return
        trace("GATEWAY_RECEIVE", measurement)
        reception = tracker.observe(measurement)
        try:
            inserted = store.insert(measurement, reception)
        except sqlite3.Error as exc:
            failure.append(exc)
            stop.set()
            return
        with lock:
            last_seen[measurement.direction] = time.monotonic()
            warned.discard(measurement.direction)
        trace("GATEWAY_STORED" if inserted else "GATEWAY_DUPLICATE", measurement)
        if inserted and reception != "ok":
            event("RECEPTION_QUALITY", run_id=measurement.run_id, sensor_id=measurement.sensor_id,
                  sequence=measurement.sequence, quality=reception)

    client = None
    try:
        client = connect(host, port, "gateway", on_message, "trafficcast/J0/sensors/+")
        print(f"GATEWAY_READY mqtt={host}:{port} db={db}", flush=True)
        while not stop.wait(0.25):
            with lock:
                for direction, received in last_seen.items():
                    if time.monotonic() - received > stale_after and direction not in warned:
                        warned.add(direction)
                        print(f"FĂRĂ DATE direcția {direction} de peste {stale_after:g}s reale", flush=True)
        if failure:
            raise RuntimeError(f"Scriere SQLite eșuată: {failure[0]}")
    finally:
        if client:
            close(client)
        store.close()
