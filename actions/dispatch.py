"""
PRIVACY68 — Shared command resolution and execution.

Both lanes (fast and API) resolve a command the same way:

    1. ask the registry whether a registered command matches the utterance
       (exact phrase first, then the priority-ordered regex list)
    2. if nothing matched, ask the intent classifier what the utterance
       means and look the intent up in the registry
    3. run the command's handler and wrap the result in the standard shape

Keeping this in one place is what makes the lanes symmetric: a new command
behaves identically no matter which lane it is declared in.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from actions.registry import CommandSpec, registry

logger = logging.getLogger("PRIVACY68.Dispatch")

#: Minimum classifier confidence before a classified intent is trusted.
#: Below this the utterance is treated as "not understood".
MIN_CONFIDENCE = 0.15

#: Minimum confidence before a classified intent is allowed to EXECUTE.
EXECUTION_CONFIDENCE = 0.60


def resolve(text: str, lane: str) -> Optional[Tuple[CommandSpec, Dict[str, str]]]:
    """
    Finds the command for `text` in `lane`.

    Returns (spec, slots) or None when the lane has nothing to offer.
    """
    if not text or not text.strip():
        return None

    # 1. Deterministic recognition — a registered command always wins.
    match = registry.match(text, lane=lane)
    if match and match.spec.handler is not None:
        return match.spec, _complete_slots(match.spec, text, match.slots)

    # 2. Semantic recognition — what does the utterance mean?
    from actions.intent_classifier import intent_classifier

    lane_name, intent, confidence = intent_classifier.classify(text)
    if lane_name != lane or confidence < EXECUTION_CONFIDENCE:
        return None

    spec = registry.spec_for_intent(intent)
    if spec is None or spec.lane != lane or spec.handler is None:
        return None

    return spec, _complete_slots(spec, text, {})


def _complete_slots(spec: CommandSpec, text: str, captured: Dict[str, str]) -> Dict[str, str]:
    """
    Fills in the arguments a matcher did not capture.

    A broad matcher ("create a folder ...") recognises the command but
    cannot see the folder name; the command's own extractor supplies it.
    """
    slots: Dict[str, str] = dict(captured)
    if not spec.slot_extractor:
        return slots

    try:
        extracted = spec.slot_extractor(text) or {}
    except Exception as exc:
        logger.debug("Slot extraction for '%s' failed: %s", spec.id, exc)
        return slots

    for key, value in extracted.items():
        if value and not slots.get(key):
            slots[key] = value
    return slots


def execute(
    spec: CommandSpec,
    slots: Dict[str, str],
    text: str,
    lane: str,
) -> Optional[Dict[str, Any]]:
    """
    Runs a command's handler and wraps the outcome in the standard shape.

    Returns None when the handler blew up, so the caller can fall through
    to the next lane instead of reporting a crash as a failed command.
    """
    from actions.registry import CommandContext

    ctx = CommandContext(
        text=text,
        slots=dict(slots),
        intent=spec.intent,
        spec=spec,
        confidence=1.0,
    )

    try:
        outcome = spec.handler(ctx)
    except Exception as exc:
        logger.error("Command '%s' failed: %s", spec.id, exc, exc_info=True)
        return None

    if not outcome:
        return None

    return {
        "handled": True,
        "tool": outcome.get("tool", spec.id),
        "method": outcome.get("method", lane),
        "success": bool(outcome.get("success")),
        "details": outcome.get("details"),
        "message": outcome.get("message", ""),
    }
