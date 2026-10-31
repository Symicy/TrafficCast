"""Evenimente JSON corelabile între citirea SUMO, MQTT și gateway."""

from dataclasses import asdict
from datetime import datetime, timezone
import json


def trace(event, measurement):
    print(json.dumps({
        "event": event,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "message_id": measurement.message_id,
        "topic": measurement.topic,
        "payload": asdict(measurement),
    }, ensure_ascii=False, allow_nan=False), flush=True)
