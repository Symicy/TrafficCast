"""Interfața de pornire a gateway-ului și a proceselor senzor."""

import argparse
import uuid

from .gateway import run_gateway
from .monitor import run_monitor
from .sensors import run_sensors


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
    parser = argparse.ArgumentParser(description="TrafficCast — senzori și gateway MQTT")
    subparsers = parser.add_subparsers(dest="command", required=True)
    gateway = subparsers.add_parser("gateway", help="Primește și salvează măsurătorile")
    gateway.add_argument("--db", default="data/runtime/trafficcast.sqlite3")
    gateway.add_argument("--stale-after", type=nonnegative_float, default=5,
                         help="Prag fără mesaje, în secunde reale")
    monitor = subparsers.add_parser("monitor", help="Afișează mesajele primite de la broker")
    run = subparsers.add_parser("run", help="Pornește adaptorul și patru procese senzor")
    run.add_argument("--scenario", default="simulation/intersection/intersection.sumocfg")
    run.add_argument("--sumo-backend", choices=("auto", "native", "flatpak"), default="auto")
    run.add_argument("--gui", action="store_true")
    run.add_argument("--steps", type=positive_int, default=120)
    run.add_argument("--pace", type=nonnegative_float, default=0.1,
                     help="Pauză în secunde reale după fiecare cadru")
    run.add_argument("--run-id", default=uuid.uuid4().hex[:12])
    for child in (gateway, monitor, run):
        child.add_argument("--host", default="127.0.0.1")
        child.add_argument("--port", type=positive_int, default=1883)
    args = parser.parse_args()
    if args.port > 65535:
        parser.error("Portul trebuie să fie cel mult 65535")
    try:
        if args.command == "gateway":
            run_gateway(args.host, args.port, args.db, args.stale_after)
        elif args.command == "monitor":
            run_monitor(args.host, args.port)
        else:
            run_sensors(args)
    except KeyboardInterrupt:
        print("Oprit de utilizator.", flush=True)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"Eroare: {exc}\n")
