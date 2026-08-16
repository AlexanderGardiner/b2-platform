#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-testplan"
PYTHON_BIN="${VENV_DIR}/bin/python"
OUT_DIR="${E2E_OUT_DIR:-e2e_runs/remote}"

cd "$ROOT_DIR"

if [[ "${E2E_LOAD_ENV:-1}" != "0" && -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

if [[ -z "${BASE_URL:-}" ]]; then
  echo "FAIL: set BASE_URL to the deployed service URL before running remote e2e tests" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "FAIL: uv is not installed or not on PATH" >&2
  exit 1
fi

uv venv --allow-existing "$VENV_DIR"
uv pip install --python "$PYTHON_BIN" -r requirements-api.txt pytest pytest-asyncio

echo
echo "================================================================================"
echo "Running remote e2e harness against ${BASE_URL}"
echo "Remote structured verdicts require ENABLE_E2E_DEBUG=true on the service."
echo "Remote media cases require expected.json media_id values."
echo "================================================================================"
echo

CMD=("$PYTHON_BIN" scripts/e2e_cases.py --base-url "$BASE_URL" --debug-tools --out-dir "$OUT_DIR")
if [[ -n "${WEBHOOK_SECRET:-}" ]]; then
  CMD+=(--secret "$WEBHOOK_SECRET")
fi
CMD+=("$@")

"${CMD[@]}"
