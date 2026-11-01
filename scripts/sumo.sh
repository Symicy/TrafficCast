#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python_bin="${TRAFFICCAST_PYTHON:-.venv/bin/python}"
action="${1:-gui}"
if [ "$#" -gt 0 ]; then shift; fi
exec "$python_bin" -m trafficcast scenario "$action" "$@"
