#!/usr/bin/env bash
# Pornește SUMO → senzori → MQTT → gateway, cu observator MQTT separat.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python_bin="${TRAFFICCAST_PYTHON:-.venv/bin/python}"
if ! command -v mosquitto >/dev/null 2>&1; then
    echo "Lipsește Mosquitto. Pe Fedora: sudo dnf install mosquitto" >&2
    exit 1
fi
if [ ! -x "$python_bin" ]; then
    echo "Creează mediul .venv și instalează proiectul conform docs/pornire.md." >&2
    exit 1
fi
mkdir -p data/runtime
broker_pid=""
gateway_pid=""
monitor_pid=""
cleanup() {
    for pid in "$monitor_pid" "$gateway_pid" "$broker_pid"; do
        if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; fi
    done
    wait 2>/dev/null || true
}
trap cleanup EXIT
mosquitto -c config/mosquitto.conf >data/runtime/broker.log 2>&1 &
broker_pid=$!
# Așteaptă portul și verifică faptul că brokerul pornit de noi rămâne activ.
"$python_bin" - <<'PY'
import socket, time
for attempt in range(50):
    try:
        with socket.create_connection(("127.0.0.1", 1883), timeout=0.1):
            break
    except OSError:
        time.sleep(0.1)
else:
    raise SystemExit("Brokerul nu a pornit. Vezi data/runtime/broker.log")
PY
if ! kill -0 "$broker_pid" 2>/dev/null; then
    echo "Brokerul nu a pornit; verifică dacă portul 1883 este ocupat. Vezi data/runtime/broker.log." >&2
    exit 1
fi
"$python_bin" -m trafficcast gateway >data/runtime/gateway.log 2>&1 &
gateway_pid=$!
wait_ready() {
    local process_pid="$1" marker="$2" logfile="$3"
    for attempt in {1..100}; do
        if grep -q "$marker" "$logfile" 2>/dev/null; then return; fi
        if ! kill -0 "$process_pid" 2>/dev/null; then
            cat "$logfile" >&2
            return 1
        fi
        sleep 0.1
    done
    echo "Componenta nu este pregătită. Vezi $logfile." >&2
    return 1
}
wait_ready "$gateway_pid" GATEWAY_READY data/runtime/gateway.log
"$python_bin" -m trafficcast monitor >data/runtime/mqtt.log 2>&1 &
monitor_pid=$!
wait_ready "$monitor_pid" MONITOR_READY data/runtime/mqtt.log
echo "Gateway și observator MQTT active. În alte terminale:"
echo "  tail -f data/runtime/mqtt.log"
echo "  tail -f data/runtime/gateway.log"
if [ "$#" -eq 0 ]; then
    set -- --gui --steps 120 --pace 1
fi
"$python_bin" -m trafficcast run "$@" | tee data/runtime/sumo-mqtt.log
# Permite gateway-ului să consume ultimele mesaje după PUBACK-ul brokerului.
sleep 1
for pid in "$gateway_pid" "$monitor_pid"; do
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "Gateway-ul sau observatorul s-a oprit. Verifică jurnalele din data/runtime/." >&2
        exit 1
    fi
done
echo "Date: data/runtime/trafficcast.sqlite3. Urmărire: sumo-mqtt.log, mqtt.log, gateway.log."
