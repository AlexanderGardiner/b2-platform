from __future__ import annotations

import time
from typing import Any

import httpx

from e2e.assertions import actual_outcome, assert_case, classification, expected_outcome, latest_tool_result
from e2e.cases import Case
from e2e.local_app import register_local_media
from e2e.payloads import meta_media_payload, meta_text_payload, mime_for_path


def run_all(
    cases: list[Case],
    *,
    base_url: str,
    secret: str,
    timeout: float,
    local_mode: bool,
    debug_tools: bool,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with httpx.Client(timeout=timeout) as client:
        for case in cases:
            results.append(
                run_case(
                    client,
                    case,
                    base_url=base_url,
                    secret=secret,
                    local_mode=local_mode,
                    debug_tools=debug_tools,
                )
            )
    return results


def run_case(
    client: httpx.Client,
    case: Case,
    *,
    base_url: str,
    secret: str,
    local_mode: bool,
    debug_tools: bool,
) -> dict[str, Any]:
    headers = {"X-Webhook-Secret": secret} if secret else {}
    if debug_tools:
        headers["X-E2E-Debug"] = "true"
    turns: list[dict[str, Any]] = []
    skipped_turns: list[dict[str, str]] = []
    errors: list[str] = []
    final_response = ""
    remote_media_error: str | None = None

    if case.narrative:
        payload = meta_text_payload(wa_id=case.wa_id, body=case.narrative, message_id=f"wamid.{case.wa_id}.text")
        turn = post_turn(client, base_url, payload, headers, "narrative")
        turns.append(turn)
        final_response = response_body(turn)

    media_id = case.expected.get("media_id")
    if case.certificate_path and local_mode:
        media_id = f"media-{case.country}-{case.kind}-{case.case_id}"
        register_local_media(media_id, case.certificate_path)
    elif case.certificate_path and not media_id:
        remote_media_error = (
            "remote mode cannot send local certificate without expected.json media_id; "
            "media turn skipped"
        )
        skipped_turns.append({"label": "media", "reason": remote_media_error})

    if media_id:
        mime_type = str(case.expected.get("mime_type") or "image/jpeg")
        if case.certificate_path and local_mode:
            mime_type = mime_for_path(case.certificate_path)
        payload = meta_media_payload(
            wa_id=case.wa_id,
            media_id=str(media_id),
            mime_type=mime_type,
            message_id=f"wamid.{case.wa_id}.media",
        )
        turn = post_turn(client, base_url, payload, headers, "media")
        turns.append(turn)
        final_response = response_body(turn)

    if not turns:
        errors.append("case produced no POST turns")

    tool_result = latest_tool_result(turns)
    missing_tool_result = debug_tools and tool_result is None
    verdict_source = (
        "tool_result"
        if tool_result is not None
        else "missing_tool_result"
        if missing_tool_result
        else "response_text"
    )
    errors.extend(
        assert_case(
            case,
            turns,
            final_response,
            remote_media_error=remote_media_error,
            tool_result=tool_result,
            require_tool_result=debug_tools,
        )
    )
    expected_value = expected_outcome(case.expected)
    actual_value = (
        "unknown"
        if remote_media_error
        else actual_outcome(
            final_response,
            case.expected,
            tool_result,
            allow_response_fallback=not missing_tool_result,
        )
    )
    classified_as = classification(expected_value, actual_value)
    passed = not errors and classified_as != "UNKNOWN"

    return {
        "case": case.label,
        "country": case.country,
        "kind": case.kind,
        "case_id": case.case_id,
        "wa_id": case.wa_id,
        "path": str(case.path),
        "expected": case.expected,
        "expected_outcome": expected_value,
        "actual_outcome": actual_value,
        "classification": classified_as,
        "verdict_source": verdict_source,
        "tool_result": tool_result,
        "turns": turns,
        "skipped_turns": skipped_turns,
        "final_response": final_response,
        "errors": errors,
        "passed": passed,
    }


def post_turn(
    client: httpx.Client,
    base_url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    label: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.post(f"{base_url}/message", json=payload, headers=headers)
    latency = time.perf_counter() - started
    try:
        response_json: Any = response.json()
    except ValueError:
        response_json = None
    return {
        "label": label,
        "status_code": response.status_code,
        "latency_seconds": round(latency, 3),
        "response_json": response_json,
        "response_text": response.text,
    }


def response_body(turn: dict[str, Any]) -> str:
    response_json = turn.get("response_json")
    if isinstance(response_json, dict) and response_json.get("response") is not None:
        return str(response_json["response"])
    return str(turn.get("response_text") or "")
