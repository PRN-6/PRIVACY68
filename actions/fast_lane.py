"""
PRIVACY68 — Lane 1: the Fast Lane.

Every command in this lane runs on the local machine in milliseconds: no
network, no model, no GPU. It works on every computer, however old.

The lane does not decide what a command IS — the command catalogue does.
The lane asks the catalogue for a match, runs the matched command, and
gets out of the way. Adding a fast command means adding one entry to
`actions/catalog.py`; nothing in this file has to change.

Two kinds of fast command are handled here:

  * catalogue commands — OS controls, settings, apps, folders, dictation
  * plugin fast intents — a plugin's own phrase -> action table
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from actions.dispatch import execute, resolve
from actions.registry import LANE_FAST

logger = logging.getLogger("PRIVACY68.FastLane")


class FastLaneRouter:
    """Runs commands that need nothing but the local machine."""

    def try_execute_fast(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Runs `text` as a catalogue command.

        Returns the result dict when the command was handled, or None
        when the utterance belongs to another lane.
        """
        if not text or not text.strip():
            return None

        resolved = resolve(text, LANE_FAST)
        if resolved is None:
            return None

        spec, slots = resolved
        result = execute(spec, slots, text, LANE_FAST)
        if result:
            logger.info("[FAST LANE] '%s' -> %s", text.strip(), result.get("tool"))
        return result

    def try_execute_plugin_fast(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Runs `text` as one of a plugin's own fast intents.

        Two matching tiers:
          1. EXACT PHRASE — the plugin's `fast_intents` map (O(1) dictionary
             lookup, 100% precise).
          2. PATTERN — the plugin's `pattern_intents` regexes, which cover the
             many ways one intent can be phrased without enumerating every
             combination.
        """
        if not text or not text.strip():
            return None

        from actions.skill_manager import manager
        from plugins.manager import plugin_manager

        low = text.lower().strip(".!?, ")
        if "and then" in low or "and after" in low or "and also" in low:
            return None

        cleaned = re.sub(r'^(?:please\s*)?(?:can\s+you\s*)?', '', low).strip()

        action_name = plugin_manager.match_fast_intent(cleaned) or plugin_manager.match_fast_intent(low)

        if not action_name:
            # Exact phrasing missed — fall back to the plugins' sentence-shape
            # patterns so open-ended phrasings still route without an LLM.
            action_name = plugin_manager.match_pattern_intent(cleaned) or plugin_manager.match_pattern_intent(low)

        if action_name:
            logger.info("[FAST LANE] Matched plugin intent '%s' for '%s'", action_name, text)
            success = manager.execute_skill(action_name, text)
            return {
                "handled": True,
                "tool": action_name,
                "method": "fast_lane",
                "success": success,
                "message": f"Executed '{action_name}' via Fast Lane",
            }

        return None


fast_lane_router = FastLaneRouter()
