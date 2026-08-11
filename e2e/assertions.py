from __future__ import annotations

from typing import Any, Literal

from e2e.cases import Case

Outcome = Literal["accept", "reject", "unknown"]
TOOL_NAME = "death_certificate_verification"
MISSING_TOOL_RESULT_ERROR = (
    "--debug-tools requested but no death_certificate_verification tool result was returned; "
    "check ENABLE_E2E_DEBUG and tool invocation"
)

DEFAULT_ACCEPT_INDICATORS = (
    "forwarded to givelight",
    "verification passed",
    "verified",
    "approved",
    "accepted",
    "eligible",
)
DEFAULT_REJECT_INDICATORS = (
    "human review",
    "did not meet",
    "flagged",
    "cannot verify",
    "can't verify",
    "no document",
    "verification failed",
    "not eligible",
    "rejected",
)


def expected_outcome(expected: dict[str, Any]) -> Literal["accept", "reject"]:
    configured = expected.get("expected_outcome")
    if configured in {"accept", "reject"}:
        return configured
    if "should_pass" in expected:
        return "accept" if bool(expected["should_pass"]) else "reject"
    return "accept"


def actual_outcome(
    final_response: str,
    expected: dict[str, Any],
    tool_result: dict[str, Any] | None = None,
    *,
    allow_response_fallback: bool = True,
) -> Outcome:
    if tool_result is not None:
        accepted = tool_result.get("accepted")
        if accepted is True:
            return "accept"
        if accepted is False:
            return "reject"
        return "unknown"

    if not allow_response_fallback:
        return "unknown"

    response = final_response.lower()
    accept_indicators = _indicators(expected, "accept_indicators", DEFAULT_ACCEPT_INDICATORS)
    reject_indicators = _indicators(expected, "reject_indicators", DEFAULT_REJECT_INDICATORS)

    accept_match = any(indicator in response for indicator in accept_indicators)
    reject_match = any(indicator in response for indicator in reject_indicators)
    if accept_match == reject_match:
        return "unknown"
    return "accept" if accept_match else "reject"


def classification(expected_value: str, actual_value: str) -> str:
    if actual_value == "unknown":
        return "UNKNOWN"
    if expected_value == "accept" and actual_value == "accept":
        return "TP"
    if expected_value == "reject" and actual_value == "reject":
        return "TN"
    if expected_value == "reject" and actual_value == "accept":
        return "FP"
    if expected_value == "accept" and actual_value == "reject":
        return "FN"
    return "UNKNOWN"


def assert_case(
    case: Case,
    turns: list[dict[str, Any]],
    final_response: str,
    *,
    remote_media_error: str | None = None,
    tool_result: dict[str, Any] | None = None,
    require_tool_result: bool = False,
) -> list[str]:
    expected = case.expected
    http_status = int(expected.get("http_status", 200))
    min_response_chars = int(expected.get("min_response_chars", 1))
    errors: list[str] = []

    if remote_media_error:
        errors.append(remote_media_error)

    if require_tool_result and tool_result is None:
        errors.append(MISSING_TOOL_RESULT_ERROR)

    for turn in turns:
        if turn["status_code"] != http_status:
            errors.append(f"{turn['label']} HTTP {turn['status_code']} != expected {http_status}")

    if len(final_response) < min_response_chars:
        errors.append(f"final response has {len(final_response)} chars; expected at least {min_response_chars}")

    for needle in expected.get("response_contains", []):
        if str(needle) not in final_response:
            errors.append(f"final response missing required substring: {needle!r}")

    any_needles = [str(value) for value in expected.get("response_contains_any", [])]
    if any_needles and not any(needle in final_response for needle in any_needles):
        errors.append(f"final response missing any of: {any_needles!r}")

    for needle in expected.get("response_not_contains", []):
        if str(needle) in final_response:
            errors.append(f"final response contains forbidden substring: {needle!r}")

    expected_value = expected_outcome(expected)
    actual_value = actual_outcome(
        final_response,
        expected,
        tool_result,
        allow_response_fallback=not require_tool_result,
    )
    if actual_value == "unknown":
        errors.append("actual outcome is unknown; update indicators or inspect response")
    elif actual_value != expected_value:
        errors.append(f"actual outcome {actual_value!r} != expected {expected_value!r}")

    return errors


def latest_tool_result(turns: list[dict[str, Any]]) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for turn in turns:
        response_json = turn.get("response_json")
        if not isinstance(response_json, dict):
            continue
        debug = response_json.get("debug")
        if not isinstance(debug, dict):
            continue
        tool_results = debug.get("tool_results")
        if not isinstance(tool_results, list):
            continue
        for result in tool_results:
            if isinstance(result, dict) and result.get("tool") == TOOL_NAME:
                latest = result
    return latest


def _indicators(expected: dict[str, Any], key: str, defaults: tuple[str, ...]) -> list[str]:
    values = expected.get(key)
    if values is None:
        return list(defaults)
    if not isinstance(values, list):
        raise ValueError(f"{key} must be a list when provided")
    return [str(value).lower() for value in values]
