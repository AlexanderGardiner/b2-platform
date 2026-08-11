from __future__ import annotations

import mimetypes
import time
from pathlib import Path
from typing import Any


def meta_text_payload(*, wa_id: str, body: str, message_id: str) -> dict[str, Any]:
    return meta_payload(
        wa_id=wa_id,
        message={
            "from": wa_id,
            "id": message_id,
            "timestamp": str(int(time.time())),
            "type": "text",
            "text": {"body": body},
        },
    )


def meta_media_payload(
    *,
    wa_id: str,
    media_id: str,
    mime_type: str,
    message_id: str,
) -> dict[str, Any]:
    media_type = "document" if mime_type == "application/pdf" else "image"
    return meta_payload(
        wa_id=wa_id,
        message={
            "from": wa_id,
            "id": message_id,
            "timestamp": str(int(time.time())),
            "type": media_type,
            media_type: {"id": media_id, "mime_type": mime_type},
        },
    )


def meta_payload(*, wa_id: str, message: dict[str, Any]) -> dict[str, Any]:
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
                            "contacts": [{"profile": {"name": "E2E User"}, "wa_id": wa_id}],
                            "messages": [message],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def mime_for_path(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "application/pdf"
    guessed = mimetypes.guess_type(path.name)[0]
    return guessed or "image/jpeg"

