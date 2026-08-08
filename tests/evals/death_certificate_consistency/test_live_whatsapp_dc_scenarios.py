import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.death_certificate_pipeline import pipeline as pipeline_module
from tools.death_certificate_pipeline import verify as verify_module
from tools.fake_image_detector.models import Escalation, ToolResult, Verdict


ROOT_DIR = Path(__file__).resolve().parents[3]
TEST_DC_DIR = ROOT_DIR / "tests" / "test_dc"
RUN_LIVE = os.getenv("RUN_LIVE_GEMINI_TESTS") == "1"
HAS_CREDENTIALS = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_CLOUD_PROJECT"))
SEPARATOR = "=" * 88


pytestmark = pytest.mark.skipif(
    not (RUN_LIVE and HAS_CREDENTIALS),
    reason="set RUN_LIVE_GEMINI_TESTS=1 and GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT to run live Gemini tests",
)


class FakeRequest:
    def __init__(self, payload: dict):
        self._payload = payload

    async def json(self):
        return self._payload


class ScenarioStore:
    def __init__(self):
        self.history: dict[str, list[str]] = {}
        self.media: dict[str, tuple[bytes, str]] = {}

    def add_message(self, session_id: str, role: str, text: str) -> None:
        self.history.setdefault(session_id, []).append(f"{role}: {text}")

    def history_text(self, session_id: str) -> str:
        return "\n".join(self.history.get(session_id, []))

    def save_media(self, session_id: str, image_bytes: bytes, mime_type: str) -> None:
        self.media[session_id] = (image_bytes, mime_type)

    def load_latest_media(self, session_id: str):
        return self.media.get(session_id)


async def _run_inline(func, *args, **kwargs):
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _claim_messages(*, name: str, date: str, place: str, aligned: bool) -> list[str]:
    if aligned:
        claim_name = name
        claim_date = date
        claim_place = place
    else:
        claim_name = "Unrelated Person"
        claim_date = "2020-01-01"
        claim_place = "Tangier"

    return [
        "Hello B2, I am an orphan and need help applying for GiveLight support.",
        f"My parent {claim_name} died on {claim_date} in {claim_place}.",
        "I am uploading the death certificate image now.",
    ]


def _text_payload(text: str, *, wa_id: str, message_id: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "1745012400192435",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "16179164660",
                                "phone_number_id": "1104821716055506",
                            },
                            "contacts": [{"profile": {"name": "Test User"}, "wa_id": wa_id}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": message_id,
                                    "timestamp": "1780358445",
                                    "text": {"body": text},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def _image_payload(media_id: str, *, wa_id: str, message_id: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "1745012400192435",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "16179164660",
                                "phone_number_id": "1104821716055506",
                            },
                            "contacts": [{"profile": {"name": "Test User"}, "wa_id": wa_id}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": message_id,
                                    "timestamp": "1780358447",
                                    "type": "image",
                                    "image": {"id": media_id, "mime_type": "image/png"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


class FakeAuthenticityPipeline:
    async def run(self, image_bytes, context=None):
        assert image_bytes
        assert context == {"input_type": "document"}
        return ToolResult(
            verdict=Verdict.PASS,
            risk_score=0.0,
            escalation=Escalation.AUTO_ACCEPT,
            checks=[],
        )


def _build_authenticity_pipeline():
    return FakeAuthenticityPipeline()


def _scenario_label(aligned: bool) -> str:
    return "POSITIVE / ALIGNED CLAIM" if aligned else "NEGATIVE / MISALIGNED CLAIM"


def _print_progress(capsys, *lines: str) -> None:
    with capsys.disabled():
        for line in lines:
            print(line, flush=True)


def _parse_webhook_response(response: dict) -> dict:
    response_text = response.get("response")
    if not isinstance(response_text, str):
        return response

    try:
        return {"response": json.loads(response_text)}
    except json.JSONDecodeError:
        return response


@pytest.mark.parametrize(
    ("image_name", "certificate_name", "certificate_date", "certificate_place", "aligned"),
    [
        (
            "Draft_2_Morocco1_00001_.png",
            "عمر العلوي",
            "1959-11-20",
            "جماعة أهل أنجاد، عمالة وجدة أنكاد بالمغرب",
            True,
        ),
        ("Draft_2_Morocco1_00001_.png", "Amina Hassan", "2024-05-03", "Casablanca", False),
    ],
)
async def test_live_gemini_compares_webhook_claims_to_uploaded_certificate(
    image_name,
    certificate_name,
    certificate_date,
    certificate_place,
    aligned,
    monkeypatch,
    capsys,
):
    import src.api as api_module

    image_path = TEST_DC_DIR / image_name
    assert image_path.exists(), f"missing test image: {image_path}"

    media_id = f"live-dc-{image_path.stem}-{'aligned' if aligned else 'misaligned'}"
    wa_id = "16508106640" if aligned else "16508106641"
    store = ScenarioStore()
    downloaded_media_ids = []
    chat_text_calls = []
    chat_image_calls = []
    text_webhook_responses = []
    claim_messages = _claim_messages(
        name=certificate_name,
        date=certificate_date,
        place=certificate_place,
        aligned=aligned,
    )

    async def fake_download(media_id_arg):
        downloaded_media_ids.append(media_id_arg)
        assert media_id_arg == media_id
        return image_path.read_bytes(), "image/png"

    async def fake_deliver(_payload):
        return True

    async def scenario_chat(*, text=None, image_bytes=None, image_media_type="image/jpeg", session_id=None, **_kwargs):
        assert session_id == wa_id
        if text is not None:
            chat_text_calls.append({"session_id": session_id, "text": text})
            store.add_message(session_id, "user", text)
            return "Please send the death certificate image when ready."

        assert image_bytes is not None
        chat_image_calls.append(
            {"session_id": session_id, "image_bytes": image_bytes, "image_media_type": image_media_type}
        )
        store.save_media(session_id, image_bytes, image_media_type)
        ctx = SimpleNamespace(
            deps=SimpleNamespace(
                session_id=session_id,
                store=store,
                history_text=store.history_text(session_id),
            )
        )
        _print_progress(
            capsys,
            "Gemini OCR/vision consistency check started...",
            "This step extracts certificate fields from the image and compares them to webhook text.",
        )
        tool_output = await verify_module.verify_death_certificate(ctx)
        _print_progress(capsys, "Gemini OCR/vision consistency check finished")
        return json.dumps({"death_certificate_verification": tool_output}, ensure_ascii=False, sort_keys=True)

    monkeypatch.setattr(api_module, "_WEBHOOK_SECRET", "")
    monkeypatch.setattr(api_module, "download_media", fake_download)
    monkeypatch.setattr(api_module, "chat", scenario_chat)
    monkeypatch.setattr(api_module, "run_in_threadpool", _run_inline)
    monkeypatch.setattr(pipeline_module, "_build_authenticity_pipeline", _build_authenticity_pipeline)
    monkeypatch.setattr(verify_module, "deliver_to_gl", fake_deliver)

    _print_progress(
        capsys,
        f"\n{SEPARATOR}",
        f"START LIVE WEBHOOK TEST: {_scenario_label(aligned)}",
        f"Image fixture: {image_name}",
        f"WhatsApp sender: {wa_id}",
        f"Media ID: {media_id}",
        "-" * 88,
    )

    for index, message in enumerate(claim_messages, start=1):
        _print_progress(capsys, f"Processing text webhook {index}/{len(claim_messages)}...")
        text_response = await api_module.message_endpoint(
            FakeRequest(
                _text_payload(
                    message,
                    wa_id=wa_id,
                    message_id=f"{media_id}.text.{index}",
                )
            )
        )
        text_webhook_responses.append(
            {
                "message_index": index,
                "user_message": message,
                "webhook_response": _parse_webhook_response(text_response),
            }
        )
        _print_progress(capsys, f"Finished text webhook {index}/{len(claim_messages)}")

    _print_progress(
        capsys,
        "-" * 88,
        "Processing image webhook...",
        "Waiting for live Gemini OCR/vision after the webhook routes the uploaded image to the tool.",
    )
    response = await api_module.message_endpoint(
        FakeRequest(
            _image_payload(
                media_id,
                wa_id=wa_id,
                message_id=f"{media_id}.image",
            )
        )
    )
    _print_progress(capsys, "Finished image webhook and live Gemini verification")

    result = json.loads(response["response"])["death_certificate_verification"]
    consistency_score = result["sub_scores"]["consistency"]

    report = {
        "image": image_name,
        "aligned_claim": aligned,
        "webhook_text_messages": claim_messages,
        "webhook_media_id": media_id,
        "webhook_responses_to_user": {
            "text_responses": text_webhook_responses,
            "image_response": _parse_webhook_response(response),
        },
        "score": result["score"],
        "band": result["band"],
        "consistency_score": consistency_score,
        "certificate": result["extracted_fields"],
        "matches": result["matches"],
        "mismatches": result["mismatches"],
        "uncertain_points": result["uncertain_points"],
        "flags": result["flags"],
        "summary": result["summary"],
    }
    _print_progress(
        capsys,
        "-" * 88,
        f"RESULT: {_scenario_label(aligned)}",
        "Live Gemini WhatsApp webhook death-certificate comparison",
        json.dumps(report, indent=2, ensure_ascii=False),
        f"END LIVE WEBHOOK TEST: {_scenario_label(aligned)}",
        f"{SEPARATOR}\n",
    )

    assert downloaded_media_ids == [media_id]
    assert len(chat_text_calls) == len(claim_messages)
    assert len(chat_image_calls) == 1
    assert chat_image_calls[0]["image_bytes"] == image_path.read_bytes()
    assert chat_image_calls[0]["image_media_type"] == "image/png"
    for message in claim_messages:
        assert message in store.history_text(wa_id)

    assert result["status"] == "verified"
    assert 0.0 <= consistency_score <= 1.0
    assert isinstance(result["extracted_fields"], dict)
    assert result["matches"] or result["mismatches"] or result["uncertain_points"]

    if aligned:
        assert consistency_score >= 0.5
    else:
        assert consistency_score <= 0.8
