#!/bin/bash
# runner.sh: run a pipeline script inside conda env angelica-website.
#
# Usage:
#   ./runner.sh pipelines/reel_compose.py --project examples/ya_tienes --preview
#   ./runner.sh pipelines/reel_compose.py logs/reel_compose.log --project examples/ya_tienes --full
#
# If the second argument ends in .log, stdout/stderr append there (Locaria runner style).

set -euo pipefail

CONDA_ENV="angelica-website"
SCRIPT_PATH="${1:-}"
shift || true

if [[ -z "${SCRIPT_PATH}" ]]; then
  echo "Usage: $0 <python-script> [logfile.log] [args...]" >&2
  exit 1
fi

LOG_PATH=""
if [[ "${1:-}" == *.log ]]; then
  LOG_PATH="$1"
  shift
fi

if [[ ! -f "${SCRIPT_PATH}" ]]; then
  echo "ERROR: Script ${SCRIPT_PATH} not found" >&2
  exit 1
fi

run_python() {
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate "${CONDA_ENV}"
  python "${SCRIPT_PATH}" "$@"
}

if [[ -n "${LOG_PATH}" ]]; then
  mkdir -p "$(dirname "${LOG_PATH}")"
  echo "[$(date -u)] Starting ${SCRIPT_PATH}" >> "${LOG_PATH}"
  run_python "$@" >> "${LOG_PATH}" 2>&1
  echo "[$(date -u)] Completed ${SCRIPT_PATH}" >> "${LOG_PATH}"
else
  run_python "$@"
fi
