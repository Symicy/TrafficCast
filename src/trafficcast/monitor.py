"""Abonat independent pentru observarea mesajelor livrate de broker."""

import signal
from threading import Event

from .messages import Measurement
from .tracing import trace
from .transport import close, connect


def run_monitor(host, port):
    stop = Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    def on_message(client, userdata, packet):
        try:
            measurement = Measurement.from_json(packet.payload, packet.topic)
        except (ValueError, TypeError, UnicodeError) as exc:
            print(f"MQTT_INVALID {packet.topic}: {exc}", flush=True)
            return
        trace("MQTT_OBSERVED", measurement)

    client = connect(host, port, "monitor", on_message, "trafficcast/J0/sensors/+")
    try:
        print(f"MONITOR_READY mqtt={host}:{port}", flush=True)
        while not stop.wait(0.25):
            pass
    finally:
        close(client)
