#!/usr/bin/env bash
# Adaptor Linux pentru coordonatorul comun Windows/Linux.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python_bin="${TRAFFICCAST_PYTHON:-.venv/bin/python}"
if [ ! -x "$python_bin" ]; then
    echo "Creează .venv și instalează proiectul conform docs/pornire.md." >&2
    exit 1
fi
if [ "$#" -eq 0 ]; then
    set -- --gui --steps 120 --pace 1
fi
exec "$python_bin" -m trafficcast demo "$@"
