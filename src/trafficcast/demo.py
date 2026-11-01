"""Coordonatorul demonstrației, fără dependență de Bash sau PowerShell."""

import json
import os
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import sys
from threading import Thread
import time
import uuid

from .messages import Measurement
from .runtime import Shutdown, find_binary
from .sources import ContinuousDemand, sumo_command
from .transport import close, connect


class Child:
    def __init__(self, command, log_path, controlled=True, tee=False, run_id=None):
        self.path = Path(log_path)
        self.log = self.path.open("w", encoding="utf-8")
        self.controlled = controlled
        self.stop_file = self.path.parent / f".stop-{uuid.uuid4().hex}"
        self.confirmed = 0
        self.observed = 0
        self.run_id = run_id
        self.echo = tee
        self.errors = []
        environment = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        if controlled:
            environment["TRAFFICCAST_STOP_FILE"] = str(self.stop_file)
        else:
            environment.pop("TRAFFICCAST_STOP_FILE", None)
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        try:
            self.process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE if controlled else self.log, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", env=environment, **options,
            )
        except BaseException:
            self.log.close()
            raise
        self.reader = Thread(target=self._tee, daemon=True) if controlled else None
        if self.reader:
            self.reader.start()

    def _tee(self):
        for line in self.process.stdout:
            self.log.write(line)
            self.log.flush()
            if self.echo:
                print(line, end="", flush=True)
            if line.startswith("{"):
                try:
                    record = json.loads(line)
                except ValueError as exc:
                    self.errors.append(str(exc))
                    continue
                if record.get("payload", {}).get("run_id") != self.run_id:
                    continue
                if record.get("event") == "MQTT_PUBACK":
                    self.confirmed += 1
                elif record.get("event") == "MQTT_OBSERVED":
                    self.observed += 1

    def request_stop(self):
        if self.process.poll() is None and self.controlled:
            self.stop_file.touch()

    def stop(self):
        if self.process.poll() is None:
            if self.controlled:
                self.request_stop()
            else:
                self.process.terminate()
            try:
                self.process.wait(timeout=20 if self.controlled else 5)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                else:
                    os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=5)
        if self.reader:
            self.reader.join(timeout=5)
            self.process.stdout.close()
        self.log.close()
        self.stop_file.unlink(missing_ok=True)

    def ready(self, marker, stop):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(self.path.read_text(encoding="utf-8"))
            if marker in self.path.read_text(encoding="utf-8"):
                return
            if stop.wait(0.05):
                raise KeyboardInterrupt
        raise TimeoutError(f"Componenta nu este pregătită. Vezi {self.path}")


def database_count(path, run_id):
    if not Path(path).is_file():
        return 0
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='measurements'").fetchone():
            return 0
        return db.execute("SELECT COUNT(*) FROM measurements WHERE run_id=?", (run_id,)).fetchone()[0]


def run_demo(args):
    Measurement(args.run_id, "E2_N", "N", 1, 0, "sumo", 0, None, 0, 0, 0, 0)
    args.scenario = str(Path(args.scenario).resolve())
    sumo_command(args.scenario, args.gui, args.sumo_backend)
    if args.continuous and args.profile == "baseline":
        ContinuousDemand(args.scenario)
    directory = Path(args.runtime_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    db = directory / "trafficcast.sqlite3"
    if database_count(db, args.run_id):
        raise ValueError("run_id există deja în SQLite; alege o identificare nouă")
    if not args.external_broker and args.host != "127.0.0.1":
        raise ValueError("Brokerul demo ascultă pe 127.0.0.1; pentru alt host folosește --external-broker")
    python = [sys.executable, "-X", "utf8", "-u", "-m", "trafficcast"]
    broker = gateway = monitor = sensors = None
    with Shutdown() as stop:
        try:
            if not args.external_broker:
                with socket.socket() as probe:
                    try:
                        probe.bind((args.host, args.port))
                    except OSError as exc:
                        raise RuntimeError(f"Portul {args.port} este ocupat. Folosește --external-broker sau alt --port.") from exc
                binary = find_binary("mosquitto")
                if not binary:
                    raise RuntimeError("Nu am găsit Mosquitto. Instalează-l și configurează PATH.")
                config = directory / "mosquitto.conf"
                config.write_text(f"listener {args.port} 127.0.0.1\nallow_anonymous true\npersistence false\nlog_dest stdout\nlog_type all\n", encoding="utf-8")
                broker = Child([binary, "-c", str(config)], directory / "broker.log", controlled=False)
                deadline = time.monotonic() + 5
                while True:
                    if broker.process.poll() is not None:
                        raise RuntimeError((directory / "broker.log").read_text(encoding="utf-8"))
                    try:
                        with socket.create_connection((args.host, args.port), timeout=0.1):
                            break
                    except OSError:
                        if time.monotonic() > deadline:
                            raise TimeoutError("Brokerul local nu a pornit")
                        if stop.wait(0.1):
                            raise KeyboardInterrupt
            else:
                client = connect(args.host, args.port, "demo-check")
                close(client)
                print(f"BROKER_EXTERN mqtt={args.host}:{args.port}; rămâne pornit la final", flush=True)
            mqtt = ["--host", args.host, "--port", str(args.port)]
            gateway = Child(python + ["gateway", *mqtt, "--db", str(db)], directory / "gateway.log", run_id=args.run_id)
            gateway.ready("GATEWAY_READY", stop)
            monitor = Child(python + ["monitor", *mqtt], directory / "mqtt.log", run_id=args.run_id)
            monitor.ready("MONITOR_READY", stop)
            command = python + ["run", *mqtt, "--scenario", args.scenario,
                                "--sumo-backend", args.sumo_backend, "--pace", str(args.pace),
                                "--run-id", args.run_id, "--profile", args.profile,
                                "--demand-duration", str(args.demand_duration)]
            if args.seed is not None:
                command += ["--seed", str(args.seed)]
            command += ["--continuous"] if args.continuous else ["--steps", str(args.steps)]
            if args.gui:
                command.append("--gui")
            print(f"DEMO_READY run={args.run_id} logs={directory}", flush=True)
            sensors = Child(command, directory / "sumo-mqtt.log", tee=True, run_id=args.run_id)
            while sensors.process.poll() is None:
                for child in (gateway, monitor):
                    if child.process.poll() is not None:
                        raise RuntimeError(f"Componentă oprită neașteptat. Vezi {child.path}")
                for child in (sensors, gateway, monitor):
                    if child.errors:
                        raise RuntimeError(f"Jurnal JSON invalid în {child.path}: {child.errors[0]}")
                if stop.wait(0.1):
                    sensors.request_stop()
                    break
            sensors.process.wait(timeout=25)
            sensors.reader.join(timeout=5)
            if sensors.errors:
                raise RuntimeError(f"Jurnal JSON invalid: {sensors.errors[0]}")
            if sensors.process.returncode:
                raise RuntimeError(f"Fluxul a eșuat. Vezi {sensors.path}")
            deadline = time.monotonic() + 10
            while database_count(db, args.run_id) != sensors.confirmed or monitor.observed != sensors.confirmed:
                if any(child.process.poll() is not None or child.errors for child in (gateway, monitor)) or time.monotonic() > deadline:
                    raise RuntimeError("SQLite/observatorul nu confirmă toate mesajele primite de broker")
                time.sleep(0.05)
            if not args.continuous and not stop.is_set() and sensors.confirmed != 4 * args.steps:
                raise RuntimeError("Rulare incompletă: unul sau mai mulți senzori nu au transmis toate cadrele")
            print(f"DEMO_TERMINAT run={args.run_id} salvate={sensors.confirmed} db={db}", flush=True)
        finally:
            failures = []
            for child in (sensors, monitor, gateway, broker):
                if child:
                    try:
                        child.stop()
                    except (OSError, subprocess.SubprocessError) as exc:
                        failures.append(f"{child.path}: {exc}")
            if failures:
                raise RuntimeError("Închidere incompletă: " + "; ".join(failures))
