"""Stable identity contract for raw sensor measurements."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

EVENT_ID_VERSION = "v1"


def _normalized_timestamp(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return str(value).strip()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return str(int(parsed.timestamp() * 1000))


def _normalized_number(value: Any) -> str:
    if value is None:
        return ""
    normalized = Decimal(str(value)).normalize()
    return format(normalized, "f")


def derive_event_id(payload: Mapping[str, Any]) -> str:
    """Return an opaque, repeatable ID for the same physical measurement."""

    supplied = str(payload.get("eventId") or "").strip()
    if supplied:
        return supplied

    canonical = "\n".join(
        [
            EVENT_ID_VERSION,
            str(payload.get("farmId") or "").strip(),
            str(payload.get("sensorId") or "").strip(),
            str(payload.get("sensorType") or "").strip(),
            _normalized_timestamp(payload.get("timestamp")),
            _normalized_number(payload.get("value")),
            str(payload.get("unit") or "").strip(),
        ]
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"evt-{digest}"
