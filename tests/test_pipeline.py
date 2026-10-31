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
    broker_executable = shutil.which("mosquitto")
    if not broker_executable:
        pytest.skip("Testul de integrare necesită mosquitto în PATH")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    config = tmp_path / "mosquitto.conf"
    config.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\npersistence false\n")
    broker_log = (tmp_path / "broker.log").open("w")
    gateway_log_path = tmp_path / "gateway.log"
    gateway_log = gateway_log_path.open("w")
    monitor_log_path = tmp_path / "mqtt.log"
    monitor_log = monitor_log_path.open("w")
    broker = subprocess.Popen([broker_executable, "-c", str(config)], stdout=broker_log, stderr=subprocess.STDOUT)
    gateway = None
    monitor = None
    db = tmp_path / "data.sqlite3"
    try:
        def broker_ready():
            if broker.poll() is not None:
                raise AssertionError((tmp_path / "broker.log").read_text())
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
        wait_until(lambda: "GATEWAY_READY" in gateway_log_path.read_text())
        monitor = subprocess.Popen(
            [sys.executable, "-m", "trafficcast", "monitor", "--port", str(port)],
            stdout=monitor_log, stderr=subprocess.STDOUT,
        )
        wait_until(lambda: "MONITOR_READY" in monitor_log_path.read_text())
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


@pytest.fixture
def scenario(tmp_path):
    if os.environ.get("TRAFFICCAST_TEST_SUMO") != "1":
        pytest.skip("Setează TRAFFICCAST_TEST_SUMO=1 pentru SUMO real")
    source = Path(__file__).resolve().parents[1] / "simulation" / "intersection"
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
        capture_output=True, text=True, timeout=45,
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
        wait_until(lambda: "RESPINS" in log.read_text())
        assert len(rows(db, "validation")) == 1
    finally:
        close(client)


def test_other_sensors_continue_when_one_is_stopped(pipeline, scenario, tmp_path):
    port, db, gateway_log, _ = pipeline
    log_path = tmp_path / "sensors.log"
    with log_path.open("w") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "trafficcast", "run", "--scenario", str(scenario),
             "--steps", "80", "--pace", "0.04", "--port", str(port), "--run-id", "failure"],
            stdout=output, stderr=subprocess.STDOUT,
        )
        try:
            wait_until(lambda: len(rows(db, "failure")) >= 8)
            line = next(line for line in log_path.read_text().splitlines() if line.startswith("SENZOR_PORNIT N "))
            os.kill(int(line.split("pid=")[1]), signal.SIGTERM)
            assert process.wait(timeout=20) == 0, log_path.read_text()
            wait_until(lambda: len([row for row in rows(db, "failure") if row[0] == "E"]) == 80)
            measurements = rows(db, "failure")
            for direction in ("E", "S", "W"):
                assert len([row for row in measurements if row[0] == direction]) == 80
            assert 0 < len([row for row in measurements if row[0] == "N"]) < 80
            assert "FĂRĂ DATE direcția N" in gateway_log.read_text()
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

    wait_until(lambda: len(events(monitor_log.read_text(), "MQTT_OBSERVED")) == 320)
    wait_until(lambda: len(events(gateway_log.read_text(), "GATEWAY_STORED")) == 320)
    stages = {
        "SUMO_READ": result.stdout, "MQTT_PUBLISH": result.stdout,
        "MQTT_PUBACK": result.stdout, "MQTT_OBSERVED": monitor_log.read_text(),
        "GATEWAY_RECEIVE": gateway_log.read_text(), "GATEWAY_STORED": gateway_log.read_text(),
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
