"""Pornire comună Windows/Linux pentru simulare, senzori și demonstrație."""

import argparse
import sys
import uuid

from .gateway import run_gateway
from .monitor import run_monitor
from .runtime import DEFAULT_SCENARIO
from .sensors import run_sensors
from .demand import PROFILES


def positive_int(text):
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("Valoarea trebuie să fie pozitivă")
    return value


def nonnegative_float(text):
    import math
    value = float(text)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError("Valoarea trebuie să fie finită și nenegativă")
    return value


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="TrafficCast — SUMO, senzori și gateway MQTT")
    subparsers = parser.add_subparsers(dest="command", required=True)
    gateway = subparsers.add_parser("gateway", help="Primește și salvează măsurătorile")
    gateway.add_argument("--db", default="data/runtime/trafficcast.sqlite3")
    gateway.add_argument("--stale-after", type=nonnegative_float, default=5)
    monitor = subparsers.add_parser("monitor", help="Afișează mesajele primite de la broker")
    run = subparsers.add_parser("run", help="Pornește adaptorul și patru procese senzor")
    demo = subparsers.add_parser("demo", help="Demonstrația completă pe Windows/Linux")
    demo.add_argument("--external-broker", action="store_true", help="Folosește brokerul existent fără a-l opri")
    demo.add_argument("--runtime-dir", default="data/runtime", help="Director pentru SQLite și jurnale")
    scenario = subparsers.add_parser("scenario", help="Deschide sau regenerează un scenariu SUMO")
    scenario.add_argument("action", choices=("gui", "headless", "rebuild"))
    for child in (run, demo, scenario):
        child.add_argument("--scenario", default=DEFAULT_SCENARIO)
        child.add_argument("--sumo-backend", choices=("auto", "native", "flatpak"), default="auto")
    for child in (run, demo):
        child.add_argument("--gui", action="store_true")
        duration = child.add_mutually_exclusive_group()
        duration.add_argument("--steps", type=positive_int, default=None)
        duration.add_argument("--continuous", action="store_true", help="Trafic continuu până la Ctrl+C")
        child.add_argument("--pace", type=nonnegative_float, default=None, help="Pauză reală după fiecare cadru")
        child.add_argument("--run-id", default=uuid.uuid4().hex[:12])
        child.add_argument("--profile", choices=PROFILES, default="baseline")
        child.add_argument("--seed", type=int, default=None)
        child.add_argument("--demand-duration", type=positive_int, default=1800,
                           help="Durata profilurilor variabile; baseline folosește fluxurile scenariului")
    for child in (gateway, monitor, run, demo):
        child.add_argument("--host", default="127.0.0.1")
        child.add_argument("--port", type=positive_int, default=1883)
    args = parser.parse_args()
    if hasattr(args, "port") and args.port > 65535:
        parser.error("Portul trebuie să fie cel mult 65535")
    if args.command in ("run", "demo"):
        args.steps = args.steps or 120
        args.pace = args.pace if args.pace is not None else (1.0 if args.continuous else 0.1)
    try:
        seed = getattr(args, "seed", None)
        if seed is not None and not 0 <= seed <= 2**31 - 1:
            raise ValueError("Seed trebuie să fie între 0 și 2147483647")
        if args.command == "gateway":
            run_gateway(args.host, args.port, args.db, args.stale_after)
        elif args.command == "monitor":
            run_monitor(args.host, args.port)
        elif args.command == "scenario":
            from .sources import run_scenario
            run_scenario(args.scenario, args.action, args.sumo_backend)
        elif args.command == "demo":
            from .demo import run_demo
            run_demo(args)
        else:
            run_sensors(args)
    except KeyboardInterrupt:
        print("Oprit de utilizator.", flush=True)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"Eroare: {exc}\n")
