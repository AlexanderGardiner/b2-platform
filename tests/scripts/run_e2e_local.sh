#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-testplan"
PYTHON_BIN="${VENV_DIR}/bin/python"
OUT_DIR="${E2E_OUT_DIR:-e2e_runs/local}"

cd "$ROOT_DIR"

if [[ "${E2E_LOAD_ENV:-1}" != "0" && -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

HAD_ENABLE_E2E_DEBUG=0
ORIGINAL_ENABLE_E2E_DEBUG=""
if [[ -n "${ENABLE_E2E_DEBUG+x}" ]]; then
  HAD_ENABLE_E2E_DEBUG=1
  ORIGINAL_ENABLE_E2E_DEBUG="$ENABLE_E2E_DEBUG"
fi

restore_enable_e2e_debug() {
  if [[ "$HAD_ENABLE_E2E_DEBUG" -eq 1 ]]; then
    export ENABLE_E2E_DEBUG="$ORIGINAL_ENABLE_E2E_DEBUG"
  else
    unset ENABLE_E2E_DEBUG
  fi
}
trap restore_enable_e2e_debug EXIT

export ENABLE_E2E_DEBUG=true

if ! command -v uv >/dev/null 2>&1; then
  echo "FAIL: uv is not installed or not on PATH" >&2
  exit 1
fi

uv venv --allow-existing "$VENV_DIR"
uv pip install --python "$PYTHON_BIN" -r requirements-api.txt pytest pytest-asyncio

echo
echo "================================================================================"
echo "Running local e2e harness with structured tool debug verdicts"
echo "ENABLE_E2E_DEBUG is enabled for this local harness process only."
echo "================================================================================"
echo

"$PYTHON_BIN" scripts/e2e_cases.py --debug-tools --out-dir "$OUT_DIR" "$@"
