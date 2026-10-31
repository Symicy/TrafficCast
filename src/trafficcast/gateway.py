"""Consumator MQTT cu validare, deduplicare și stocare SQLite."""

from datetime import datetime, timezone
from pathlib import Path
import signal
import sqlite3
from threading import Event, Lock
import time

from .messages import DIRECTIONS, Measurement
from .tracing import trace
from .transport import close, connect


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
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

    def insert(self, message):
        with self.db:
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO measurements VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (message.run_id, message.sensor_id, message.sequence, message.direction,
                 message.sim_time_s, message.source, message.vehicle_count,
                 message.mean_speed_m_s, message.occupancy_pct, message.jam_length_m,
                 message.exit_vehicle_count, message.tls_phase,
                 datetime.now(timezone.utc).isoformat(), message.to_json()),
            )
        return cursor.rowcount == 1

    def close(self):
        self.db.close()


def run_gateway(host, port, db, stale_after):
    stop = Event()
    lock = Lock()
    last_seen = {direction: time.monotonic() for direction in DIRECTIONS}
    warned = set()
    failure = []
    store = Store(db)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    def on_message(client, userdata, packet):
        try:
            measurement = Measurement.from_json(packet.payload, packet.topic)
        except (ValueError, TypeError, UnicodeError) as exc:
            print(f"RESPINS {packet.topic}: {exc}", flush=True)
            return
        trace("GATEWAY_RECEIVE", measurement)
        try:
            inserted = store.insert(measurement)
        except sqlite3.Error as exc:
            failure.append(exc)
            stop.set()
            return
        with lock:
            last_seen[measurement.direction] = time.monotonic()
            warned.discard(measurement.direction)
        if inserted:
            trace("GATEWAY_STORED", measurement)
        else:
            trace("GATEWAY_DUPLICATE", measurement)

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
