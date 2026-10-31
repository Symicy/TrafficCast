"""Conexiuni MQTT locale, cu așteptarea confirmărilor brokerului."""

from threading import Event
import uuid

import paho.mqtt.client as mqtt


def connect(host, port, role, on_message=None, subscription=None):
    ready = Event()
    errors = []
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"tc-{role}-{uuid.uuid4().hex[:10]}",
        protocol=mqtt.MQTTv311,
    )
    client.connect_timeout = 5
    client.max_queued_messages_set(100)

    def on_connect(current, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            errors.append(str(reason_code))
            ready.set()
        elif subscription:
            current.subscribe(subscription, qos=1)
        else:
            ready.set()

    def on_subscribe(current, userdata, mid, reason_codes, properties):
        if any(code.is_failure for code in reason_codes):
            errors.append("Brokerul a refuzat abonarea")
        ready.set()

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    if on_message:
        client.on_message = on_message
    try:
        client.connect(host, port)
        client.loop_start()
        if not ready.wait(10) or errors:
            raise RuntimeError(f"Conectare MQTT nereușită: {errors or 'timeout'}")
    except BaseException:
        close(client)
        raise
    return client


def publish(client, measurement):
    info = client.publish(measurement.topic, measurement.to_json(), qos=1, retain=False)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"Publicare MQTT eșuată: {mqtt.error_string(info.rc)}")
    info.wait_for_publish(timeout=10)
    if not info.is_published():
        raise TimeoutError("Brokerul nu a confirmat mesajul în 10 secunde")


def close(client):
    client.disconnect()
    client.loop_stop()
