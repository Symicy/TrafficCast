#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
scenario_dir="$project_dir/simulation/intersection"
mkdir -p "$scenario_dir/results"
case "${1:-gui}" in
    gui) executable=sumo-gui; config=intersection.sumocfg ;;
    headless) executable=sumo; config=intersection.sumocfg ;;
    rebuild) executable=netconvert; config=intersection.netccfg ;;
    *) echo "Utilizare: bash scripts/sumo.sh [gui|headless|rebuild]" >&2; exit 1 ;;
esac
if command -v "$executable" >/dev/null 2>&1; then
    exec "$executable" -c "$scenario_dir/$config"
else
    exec flatpak run --filesystem="$scenario_dir" --command="$executable" org.eclipse.sumo -c "$scenario_dir/$config"
fi
