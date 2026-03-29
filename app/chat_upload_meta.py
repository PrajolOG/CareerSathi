import json
from typing import Any

UPLOAD_META_PREFIX = "__CS_UPLOAD_META__:"


def build_upload_message(
    user_text: str,
    file_name: str,
    object_name: str,
    bucket_name: str,
) -> str:
    meta = {
        "type": "image",
        "file_name": (file_name or "image").strip() or "image",
        "object_name": (object_name or "").strip(),
        "bucket_name": (bucket_name or "").strip(),
    }
    encoded_meta = json.dumps(meta, separators=(",", ":"), ensure_ascii=True)
    clean_user_text = (user_text or "").strip()

    if clean_user_text:
        return f"{UPLOAD_META_PREFIX}{encoded_meta}\n{clean_user_text}"
    return f"{UPLOAD_META_PREFIX}{encoded_meta}"


def parse_upload_message(message: str) -> tuple[dict[str, Any] | None, str]:
    text = (message or "").strip()
    if not text.startswith(UPLOAD_META_PREFIX):
        return None, text

    first_line, separator, remainder = text.partition("\n")
    raw_meta = first_line[len(UPLOAD_META_PREFIX):].strip()

    try:
        parsed_meta = json.loads(raw_meta)
    except Exception:
        return None, text

    if not isinstance(parsed_meta, dict):
        return None, text

    user_text = remainder.strip() if separator else ""
    return parsed_meta, user_text


def strip_upload_meta(message: str) -> str:
    _, clean_text = parse_upload_message(message)
    return clean_text
