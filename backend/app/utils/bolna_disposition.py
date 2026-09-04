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

import re
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

# Client-review ranking: real 40s+ conversations first, short/weak labels below.
LISTEN_MIN_DURATION_SECONDS = 40
_INVITE_TURN_RE = re.compile(
    r"interested in attending|are you interested in attending|would you be attending|"
    r"include hona|aane mein ruchi",
    re.I,
)
_CONFIRM_TURN_RE = re.compile(
    r"\b(yes|yeah|yep|yup|haan|sure|okay|ok|i will|i'll come|i can come|coming|"
    r"aaunga|aaungi|aaenge|definitely|interested|will attend|will come|attending|"
    r"send .{0,24}(link|details)|whatsapp|ticket|register|book)\b",
    re.I,
)
_DECLINE_TURN_RE = re.compile(
    r"\b(no|not interested|nahi|won't|wont|cannot|can't|not coming|not attending|"
    r"don't want|do not want)\b",
    re.I,
)
_ASK_TURN_HINTS = (
    "whatsapp",
    "ticket",
    "register",
    "booking",
    "link",
    "details",
    "i can come",
    "i will come",
    "i'll come",
)


def is_attendance_disposition(value: Any) -> bool:
    return str(value or "").strip().lower() in {"attending", "not attending", "not-attending"}


def _user_turns_after_invite(transcript: Any) -> list[str]:
    after: list[str] = []
    seen_invite = False
    for raw_line in str(transcript or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _INVITE_TURN_RE.search(line):
            seen_invite = True
        low = line.lower()
        if not (low.startswith("user:") or low.startswith("customer:")):
            continue
        text = re.sub(r"^(user|customer)\s*:\s*", "", line, flags=re.I).strip()
        if seen_invite and text:
            after.append(text)
    return after


def _user_turn_count(transcript: Any) -> int:
    n = 0
    for raw_line in str(transcript or "").splitlines():
        low = raw_line.strip().lower()
        if low.startswith("user:") or low.startswith("customer:"):
            n += 1
    return n


def call_match_quality(doc: Any) -> str:
    """``strong`` = 40s+ transcript with a real yes/no after the invite; else ``review``."""
    if not isinstance(doc, dict):
        return "review"
    try:
        duration = int(doc.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration < LISTEN_MIN_DURATION_SECONDS:
        return "review"

    after = _user_turns_after_invite(doc.get("transcript"))
    after_text = " ".join(after).lower()
    stored = str(doc.get("disposition") or "").strip()
    extracted = doc.get("extracted_data") or doc.get("extractedData")
    label = stored or extract_bolna_disposition(extracted)
    key = label.lower().replace("_", " ").replace("-", " ")

    if key == "attending":
        asked = any(hint in after_text for hint in _ASK_TURN_HINTS)
        confirmed = bool(_CONFIRM_TURN_RE.search(after_text))
        if asked or confirmed:
            return "strong"
        if duration >= 50 and (_user_turn_count(doc.get("transcript")) >= 3 or len(after) >= 2):
            return "strong"
        return "review"

    if key == "not attending":
        if _DECLINE_TURN_RE.search(after_text) or "not interested" in after_text:
            return "strong"
        return "review"

    return "review"


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
