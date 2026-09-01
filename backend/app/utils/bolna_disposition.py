"""Resolve Attending / Not Attending from Bolna extracted_data."""
from __future__ import annotations

from typing import Any, Dict

_BOLNA_LEAF_VALUE_KEYS = ("objective", "value", "label")
_BOLNA_DIRECT_DISPOSITION_KEYS = (
    "disposition",
    "Disposition",
    "call_disposition",
    "Call Disposition",
)
_BOLNA_ATTENDANCE_VALUES = {
    "attending": "Attending",
    "not attending": "Not Attending",
    "not-attending": "Not Attending",
}

_NOT_ATTENDING_HINTS = (
    "will not attend",
    "not attending",
    "not interested",
    "declined",
    "said no",
)
_ATTENDING_HINTS = (
    "expressed interest in attending",
    "confirmed attendance",
    "will attend",
    "agreed to attend",
    "user expressed interest",
    "user confirmed",
)


def _leaf_text(node: Any) -> str:
    if isinstance(node, str) and node.strip():
        return node.strip()
    if not isinstance(node, dict):
        return ""
    for key in _BOLNA_LEAF_VALUE_KEYS:
        val = node.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _as_confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _nested_dict(extracted: Any, *path: str) -> Dict[str, Any]:
    node: Any = extracted
    for key in path:
        if not isinstance(node, dict):
            return {}
        node = node.get(key)
    return node if isinstance(node, dict) else {}


def extract_bolna_disposition(extracted: Any) -> str:
    """Pick Attending / Not Attending using confidence, not the first matching leaf.

    Bolna often writes *both* objective labels and sets confidence=0 on the loser.
    """
    if not isinstance(extracted, dict):
        return ""
    for key in _BOLNA_DIRECT_DISPOSITION_KEYS:
        text = _leaf_text(extracted.get(key))
        if text:
            return _BOLNA_ATTENDANCE_VALUES.get(text.lower(), text)

    att = _nested_dict(extracted, "Attending", "Attending") or _nested_dict(
        extracted, "General", "Attending"
    )
    natt = _nested_dict(extracted, "Attending", "Not Attending") or _nested_dict(
        extracted, "General", "Not Attending"
    )
    att_conf = _as_confidence(att.get("confidence"))
    natt_conf = _as_confidence(natt.get("confidence"))

    if att_conf >= 0.5 or natt_conf >= 0.5:
        if att_conf >= natt_conf:
            return "Attending"
        return "Not Attending"

    summary = str(
        _nested_dict(extracted, "General", "Call Summary").get("subjective") or ""
    ).lower()
    if summary:
        if any(hint in summary for hint in _NOT_ATTENDING_HINTS):
            return "Not Attending"
        if any(hint in summary for hint in _ATTENDING_HINTS):
            return "Attending"
    return ""
