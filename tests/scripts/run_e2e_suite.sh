#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOCAL_OUT_DIR="${E2E_OUT_DIR:-e2e_runs/local}"

cd "$ROOT_DIR"

if [[ "${E2E_LOAD_ENV:-1}" != "0" && -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

tests/scripts/run_e2e_local.sh "$@"

RESULTS_JSON="$(find "$LOCAL_OUT_DIR" -mindepth 2 -maxdepth 2 -name results.json -print | sort | tail -n 1)"
if [[ -z "$RESULTS_JSON" ]]; then
  echo "FAIL: no e2e results.json found under ${LOCAL_OUT_DIR}" >&2
  exit 1
fi

GATE_CMD=(
  python tests/scripts/check_e2e_report.py "$RESULTS_JSON"
  --max-unknown "${E2E_MAX_UNKNOWN:-0}"
  --max-fp "${E2E_MAX_FP:-0}"
)
if [[ -n "${E2E_MAX_FN:-}" ]]; then
  GATE_CMD+=(--max-fn "$E2E_MAX_FN")
fi
if [[ -n "${E2E_MIN_ACCURACY:-}" ]]; then
  GATE_CMD+=(--min-accuracy "$E2E_MIN_ACCURACY")
fi

"${GATE_CMD[@]}"

SUMMARY_MD="$(dirname "$RESULTS_JSON")/summary.md"
echo
echo "E2E summary: ${SUMMARY_MD}"
