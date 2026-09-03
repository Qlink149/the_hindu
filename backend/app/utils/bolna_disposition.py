"""Resolve Attending / Not Attending from Bolna extracted_data.

Hindu- Pre Event nests both leaves under category ``Attending``:

    extracted_data.Attending.Attending
    extracted_data.Attending.Not Attending

Hindu On Day Version 3.0 uses matching category names for the same questions:

    extracted_data.Attending.Attending
    extracted_data.Not Attending.Not Attending

Both also keep Call Summary under ``General``.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

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

# Category keys Bolna has used for the Hindu attendance extractions.
_BOLNA_CATEGORY_KEYS = ("Attending", "Not Attending", "General")

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


def _find_named_leaf(extracted: Any, leaf_name: str) -> Dict[str, Any]:
    """Find an extraction leaf by name under known or arbitrary categories."""
    if not isinstance(extracted, dict):
        return {}
    for category in _BOLNA_CATEGORY_KEYS:
        node = _nested_dict(extracted, category, leaf_name)
        if node:
            return node
    for group in extracted.values():
        if not isinstance(group, dict):
            continue
        node = group.get(leaf_name)
        if isinstance(node, dict):
            return node
    return {}


def bolna_leaf_paths(leaf_name: str) -> Tuple[str, ...]:
    """Dotted Mongo paths for a named Bolna extraction leaf (objective/value)."""
    paths = []
    for category in _BOLNA_CATEGORY_KEYS:
        prefix = f"extracted_data.{category}.{leaf_name}"
        paths.append(f"{prefix}.objective")
        paths.append(f"{prefix}.value")
    return tuple(paths)


def bolna_confidence_paths(leaf_name: str) -> Tuple[str, ...]:
    return tuple(
        f"extracted_data.{category}.{leaf_name}.confidence"
        for category in _BOLNA_CATEGORY_KEYS
    )


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

    att = _find_named_leaf(extracted, "Attending")
    natt = _find_named_leaf(extracted, "Not Attending")
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
