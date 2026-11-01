"""Teste cu broker Mosquitto real; SUMO este activat explicit prin mediu."""

import os
import json
from pathlib import Path
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time

import pytest

from trafficcast.messages import Measurement
from trafficcast.runtime import find_binary
from trafficcast.transport import close, connect, publish


def wait_until(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("Condiția nu s-a îndeplinit înainte de timeout")


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture
def pipeline(tmp_path):
    broker_executable = find_binary("mosquitto")
    if not broker_executable:
        pytest.skip("Testul de integrare necesită mosquitto în PATH")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    config = tmp_path / "mosquitto.conf"
    config.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\npersistence false\n")
    broker_log = (tmp_path / "broker.log").open("w", encoding="utf-8")
    gateway_log_path = tmp_path / "gateway.log"
    gateway_log = gateway_log_path.open("w", encoding="utf-8")
    monitor_log_path = tmp_path / "mqtt.log"
    monitor_log = monitor_log_path.open("w", encoding="utf-8")
    broker = subprocess.Popen([broker_executable, "-c", str(config)], stdout=broker_log, stderr=subprocess.STDOUT)
    gateway = None
    monitor = None
    db = tmp_path / "data.sqlite3"
    try:
        def broker_ready():
            if broker.poll() is not None:
                raise AssertionError((tmp_path / "broker.log").read_text(encoding='utf-8'))
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    return True
            except OSError:
                return False
        wait_until(broker_ready)
        gateway = subprocess.Popen(
            [sys.executable, "-m", "trafficcast", "gateway", "--port", str(port),
             "--db", str(db), "--stale-after", "0.5"],
            stdout=gateway_log, stderr=subprocess.STDOUT,
        )
        wait_until(lambda: "GATEWAY_READY" in gateway_log_path.read_text(encoding='utf-8'))
        monitor = subprocess.Popen(
            [sys.executable, "-m", "trafficcast", "monitor", "--port", str(port)],
            stdout=monitor_log, stderr=subprocess.STDOUT,
        )
        wait_until(lambda: "MONITOR_READY" in monitor_log_path.read_text(encoding='utf-8'))
        yield port, db, gateway_log_path, monitor_log_path
    finally:
        if monitor:
            stop(monitor)
        if gateway:
            stop(gateway)
        stop(broker)
        broker_log.close()
        gateway_log.close()
        monitor_log.close()


@pytest.fixture(params=["intersection", "intersection-urban"])
def scenario(tmp_path, request):
    if os.environ.get("TRAFFICCAST_TEST_SUMO") != "1":
        pytest.skip("Setează TRAFFICCAST_TEST_SUMO=1 pentru SUMO real")
    source = Path(__file__).resolve().parents[1] / "simulation" / request.param
    target = tmp_path / "intersection"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("results"))
    return target / "intersection.sumocfg"


def rows(db, run_id):
    with sqlite3.connect(db) as connection:
        return connection.execute(
            "SELECT direction,sequence,sim_time_s,vehicle_count,mean_speed_m_s,"
            "occupancy_pct,jam_length_m,exit_vehicle_count,tls_phase "
            "FROM measurements WHERE run_id=? ORDER BY direction,sequence", (run_id,),
        ).fetchall()


def run(port, *arguments):
    result = subprocess.run(
        [sys.executable, "-m", "trafficcast", "run", "--port", str(port),
         "--pace", "0", *arguments],
        capture_output=True, text=True, encoding="utf-8", timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def test_gateway_rejects_bad_data_and_deduplicates(pipeline):
    port, db, log, _ = pipeline
    client = connect("127.0.0.1", port, "test")
    try:
        message = Measurement("validation", "E2_N", "N", 1, 1, "sumo", 0, None, 0, 0, 0, 0)
        publish(client, message)
        publish(client, message)
        info = client.publish(message.topic, '{"vehicle_count": -5}', qos=1)
        info.wait_for_publish(timeout=5)
        wait_until(lambda: "RESPINS" in log.read_text(encoding='utf-8'))
        assert len(rows(db, "validation")) == 1
    finally:
        close(client)


def test_other_sensors_continue_when_one_is_stopped(pipeline, scenario, tmp_path):
    port, db, gateway_log, _ = pipeline
    log_path = tmp_path / "sensors.log"
    with log_path.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "trafficcast", "run", "--scenario", str(scenario),
             "--steps", "80", "--pace", "0.04", "--port", str(port), "--run-id", "failure"],
            stdout=output, stderr=subprocess.STDOUT,
        )
        try:
            wait_until(lambda: len(rows(db, "failure")) >= 8)
            line = next(line for line in log_path.read_text(encoding='utf-8').splitlines() if line.startswith("SENZOR_PORNIT N "))
            os.kill(int(line.split("pid=")[1]), signal.SIGTERM)
            assert process.wait(timeout=20) == 0, log_path.read_text(encoding='utf-8')
            wait_until(lambda: len([row for row in rows(db, "failure") if row[0] == "E"]) == 80)
            measurements = rows(db, "failure")
            for direction in ("E", "S", "W"):
                assert len([row for row in measurements if row[0] == direction]) == 80
            assert 0 < len([row for row in measurements if row[0] == "N"]) < 80
            assert "FĂRĂ DATE direcția N" in gateway_log.read_text(encoding='utf-8')
        finally:
            stop(process)


def test_sumo_to_gateway_with_identical_payload_at_every_stage(pipeline, scenario):
    port, db, gateway_log, monitor_log = pipeline
    result = run(port, "--steps", "80", "--run-id", "sumo-test", "--scenario", str(scenario))
    wait_until(lambda: len(rows(db, "sumo-test")) == 320)
    measurements = rows(db, "sumo-test")
    assert {row[0] for row in measurements} == {"N", "E", "S", "W"}
    assert any(row[3] > 0 for row in measurements)  # vehicule observate
    assert any(row[6] > 0 for row in measurements)  # coadă observată
    assert sum(row[7] for row in measurements) > 0  # treceri la ieșire
    assert len({row[8] for row in measurements}) > 1  # fazele evoluează

    def events(text, event):
        return [record for line in text.splitlines() if line.startswith("{")
                if (record := json.loads(line))["event"] == event]

    wait_until(lambda: len(events(monitor_log.read_text(encoding='utf-8'), "MQTT_OBSERVED")) == 320)
    wait_until(lambda: len(events(gateway_log.read_text(encoding='utf-8'), "GATEWAY_STORED")) == 320)
    stages = {
        "SUMO_READ": result.stdout, "MQTT_PUBLISH": result.stdout,
        "MQTT_PUBACK": result.stdout, "MQTT_OBSERVED": monitor_log.read_text(encoding='utf-8'),
        "GATEWAY_RECEIVE": gateway_log.read_text(encoding='utf-8'), "GATEWAY_STORED": gateway_log.read_text(encoding='utf-8'),
    }
    reference = {record["message_id"]: record["payload"] for record in events(result.stdout, "SUMO_READ")}
    for stage, log in stages.items():
        records = events(log, stage)
        assert len(records) == 320, stage
        assert {record["message_id"]: record["payload"] for record in records} == reference, stage
        assert all(record["timestamp_utc"] and record["payload"]["source"] == "sumo" for record in records)
    with sqlite3.connect(db) as connection:
        stored = [json.loads(row[0]) for row in connection.execute(
            "SELECT payload FROM measurements WHERE run_id='sumo-test'",
        )]
    assert {f"{m['run_id']}:{m['sensor_id']}:{m['sequence']}": m for m in stored} == reference


def unused_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def test_demo_manages_own_broker_and_saves_480_messages(scenario, tmp_path):
    if not find_binary("mosquitto"):
        pytest.skip("Mosquitto indisponibil")
    port = unused_port()
    runtime = tmp_path / "runtime with spaces"
    result = subprocess.run(
        [sys.executable, "-m", "trafficcast", "demo", "--scenario", str(scenario),
         "--port", str(port), "--steps", "120", "--pace", "0", "--runtime-dir", str(runtime),
         "--run-id", "demo-test"], capture_output=True, text=True, encoding="utf-8", timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "salvate=480" in result.stdout
    assert len(rows(runtime / "trafficcast.sqlite3", "demo-test")) == 480
    source_log = (runtime / "sumo-mqtt.log").read_text(encoding="utf-8")
    def stage(text, name):
        records = [json.loads(line) for line in text.splitlines() if line.startswith("{")]
        return {record["message_id"]: record["payload"] for record in records if record["event"] == name}
    reference = stage(source_log, "SUMO_READ")
    for name, text in (("MQTT_PUBLISH", source_log), ("MQTT_PUBACK", source_log),
                       ("MQTT_OBSERVED", (runtime / "mqtt.log").read_text(encoding="utf-8")),
                       ("GATEWAY_RECEIVE", (runtime / "gateway.log").read_text(encoding="utf-8")),
                       ("GATEWAY_STORED", (runtime / "gateway.log").read_text(encoding="utf-8"))):
        assert stage(text, name) == reference
    assert not list(runtime.glob(".stop-*"))
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", port), timeout=0.2)


def test_continuous_demo_stops_cleanly_and_keeps_external_broker(pipeline, scenario, tmp_path):
    import xml.etree.ElementTree as ET

    port, _, _, _ = pipeline
    route_file = scenario.parent / "traffic.rou.xml"
    tree = ET.parse(route_file)
    for flow in tree.getroot().findall("flow"):
        flow.set("end", "10")
    tree.write(route_file, encoding="utf-8", xml_declaration=True)
    runtime = tmp_path / "continuous runtime"
    shutdown = tmp_path / "stop-demo"
    log = tmp_path / "continuous.log"
    environment = dict(os.environ, TRAFFICCAST_STOP_FILE=str(shutdown))
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "trafficcast", "demo", "--external-broker", "--continuous",
             "--scenario", str(scenario), "--port", str(port), "--pace", "0.005",
             "--runtime-dir", str(runtime), "--run-id", "continuous-test"],
            stdout=output, stderr=subprocess.STDOUT, env=environment,
        )
        try:
            def reached_time():
                if process.poll() is not None:
                    raise AssertionError(log.read_text(encoding="utf-8"))
                db = runtime / "trafficcast.sqlite3"
                if not db.exists():
                    return False
                try:
                    return any(row[2] >= 90 for row in rows(db, "continuous-test"))
                except sqlite3.OperationalError:
                    return False
            wait_until(reached_time, timeout=25)
            shutdown.touch()
            assert process.wait(timeout=25) == 0, log.read_text(encoding="utf-8")
            assert "DEMO_TERMINAT" in log.read_text(encoding="utf-8")
            assert not list(runtime.glob(".stop-*"))
            # Brokerul extern este încă utilizabil după oprirea coordonată.
            client = connect("127.0.0.1", port, "after-demo")
            close(client)
            stored = rows(runtime / "trafficcast.sqlite3", "continuous-test")
            last_sequence = max(row[1] for row in stored)
            assert len(stored) == 4 * last_sequence
            for file, event in (("mqtt.log", "MQTT_OBSERVED"), ("gateway.log", "GATEWAY_STORED")):
                records = [json.loads(line) for line in (runtime / file).read_text(encoding="utf-8").splitlines()
                           if line.startswith("{")]
                assert sum(record["event"] == event for record in records) == len(stored)
        finally:
            shutdown.touch()
            stop(process)


def test_busy_port_does_not_stop_existing_broker(pipeline, scenario, tmp_path):
    port, _, _, _ = pipeline
    result = subprocess.run(
        [sys.executable, "-m", "trafficcast", "demo", "--scenario", str(scenario),
         "--port", str(port), "--steps", "1", "--runtime-dir", str(tmp_path / "busy")],
        capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert result.returncode == 1
    assert "--external-broker" in result.stderr
    client = connect("127.0.0.1", port, "still-alive")
    close(client)


def test_data_pipeline_keeps_sumo_program_and_does_not_publish_commands(pipeline, scenario):
    port, db, _, _ = pipeline
    received = []
    client = connect("127.0.0.1", port, "command-observer",
                     lambda current, userdata, packet: received.append((packet.topic, packet.payload)),
                     "trafficcast/J0/commands/#")
    topic = "trafficcast/J0/commands/data-source"
    payload = json.dumps(dict(run_id="data-source", sequence=1, sim_time_s=1,
                              tls_phase=0, action="switch", reason="external", schema_version=1))
    try:
        info = client.publish(topic, payload, qos=1, retain=True)
        info.wait_for_publish(timeout=5)
        wait_until(lambda: len(received) == 1)
        result = run(port, "--scenario", str(scenario), "--steps", "80", "--run-id", "data-source")
        wait_until(lambda: len(rows(db, "data-source")) == 320)
        for reading in rows(db, "data-source"):
            position = (int(reading[2]) - 1) % 70
            expected = next(index for index, end in enumerate((30, 33, 35, 65, 68, 70)) if position < end)
            assert reading[8] == expected
        assert received == [(topic, payload.encode())]
        events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        assert all(not event["event"].startswith("CONTROL_") for event in events)
    finally:
        client.publish(topic, b"", qos=1, retain=True).wait_for_publish(timeout=5)
        close(client)
