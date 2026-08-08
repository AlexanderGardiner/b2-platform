#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-testplan"
PYTHON_BIN="${VENV_DIR}/bin/python"

FAILED=0

run_step() {
  local name="$1"
  shift

  printf '\n==> %s\n' "$name"
  if "$@"; then
    printf 'PASS: %s\n' "$name"
    return 0
  else
    local status=$?
    printf 'FAIL: %s (exit %s)\n' "$name" "$status"
    FAILED=1
    return "$status"
  fi
}

run_pytest_group() {
  local name="$1"
  shift

  run_step "$name" "${PYTHON_BIN}" -m pytest -q "$@"
}

cd "$ROOT_DIR" || exit 1

if ! command -v uv >/dev/null 2>&1; then
  echo "FAIL: uv is not installed or not on PATH" >&2
  exit 1
fi

if ! run_step "Create uv virtual environment" uv venv --allow-existing "$VENV_DIR"; then
  echo "Cannot continue without a virtual environment." >&2
  exit 1
fi

if ! run_step "Install API requirements and test tooling" uv pip install --python "$PYTHON_BIN" -r requirements-api.txt pytest pytest-asyncio; then
  echo "Cannot continue without installed test dependencies." >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "FAIL: Python executable not found at $PYTHON_BIN" >&2
  exit 1
fi

run_pytest_group "Dependency and agent configuration" \
  tests/unit/test_agent_config.py

run_pytest_group "Request handling API" \
  tests/unit/test_api.py \
  tests/unit/test_whatsapp_dc_scenarios.py

run_pytest_group "Agent routing" \
  tests/unit/test_chat.py

run_pytest_group "Context-aware death certificate tool call" \
  tests/unit/test_verify_flow_integration.py

run_pytest_group "Death certificate pipeline and scoring" \
  tests/unit/tools/death_certificate_pipeline

run_pytest_group "Fake image detector pipeline" \
  tests/unit/tools/fake_image_detector/test_pipeline.py \
  tests/unit/tools/fake_image_detector/test_build_pipeline.py

printf '\n'
if [[ "$FAILED" -eq 0 ]]; then
  echo "All test plan groups passed."
else
  echo "One or more test plan groups failed."
fi

exit "$FAILED"
