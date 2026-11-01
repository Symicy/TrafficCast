"""Evenimente JSON corelabile între citirea SUMO, MQTT și gateway."""

from dataclasses import asdict
from datetime import datetime, timezone
import json
import sys


def trace(event, measurement):
    line = json.dumps({
        "event": event,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "message_id": measurement.message_id,
        "topic": measurement.topic,
        "payload": measurement.to_dict() if hasattr(measurement, "to_dict") else asdict(measurement),
    }, ensure_ascii=False, allow_nan=False)
    # O singură scriere include și newline: procesele împart același pipe pe Windows.
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def event(name, **fields):
    line = json.dumps(dict(event=name, timestamp_utc=datetime.now(timezone.utc).isoformat(), **fields),
                      ensure_ascii=False, allow_nan=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
