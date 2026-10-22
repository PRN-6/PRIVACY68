"""
PRIVACY68 Compound Command Planner.

Splits a single spoken utterance that contains MULTIPLE independent commands
into ordered clauses, so "mute the volume and open chrome" runs BOTH actions
instead of only the first one the classifier happens to match.

Why this exists
---------------
The 3-lane classifier returns exactly ONE intent for a whole utterance. A
compound utterance therefore collapsed to a single action and the remaining
clauses were silently dropped. This module adds the missing planning step.

How the split is decided (deterministic, no LLM, works offline)
---------------------------------------------------------------
English commands are IMPERATIVE and VERB-HEADED. A conjunction only separates
two commands when BOTH sides of it read as a command on their own:

    "mute the volume and open chrome"    -> split  (mute=verb, open=verb)
    "search for cats and dogs"            -> no split ('dogs' is not a verb)
    "create a folder called Cats and Dogs"-> no split ('Dogs' is a name)

The rules, in order:

  1. LEAD VERB — the clause starts (after any politeness) with a command
     verb. This is the primary signal: a clause beginning with a noun is an
     argument or a continuation, not a command.
  2. CLASSIFIED — the classifier must recognise the clause and be reasonably
     confident about it, so a garbled fragment is never executed on its own.
  3. DESTRUCTIVE GUARD — if a clause destroys something ("delete", "remove"),
     it and the clause after it must both be confident, otherwise the
     conjunction probably belongs to the destructive argument
     ("delete tmp and build folders" is ONE delete, not two commands).

Two constructions get special handling:

  * BROWSER CONTINUATION — "open chrome and search for X" is one browser
     workflow, so it is re-merged and the existing compound_browser API lane
     handles it exactly as it did before (one window, one search).
  * ELIDED VERB — "open chrome, brave, and edge" applies the verb to every
     name in the list, so the verb is restored for the later names.

This is deliberately conservative: a wrong split could open the wrong app or
delete the wrong file, so the planner only splits when it is certain. When in
doubt it returns None and the utterance is handled as a single command,
exactly as before.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("PRIVACY68.CommandPlanner")


# ─── Conjunction boundaries ─────────────────────────────────────────────────
# Ordered longest-first so "and then" / "and also" win over a bare "and".
_SPLIT_PATTERN = re.compile(
    r"\s*(?:,\s*|\band\s+then\b|\bthen\b|\band\s+also\b|\balso\b|\band\b)\s*",
    re.IGNORECASE,
)

_WORD_RE = re.compile(r"[a-zA-Z]+")

# Words that may precede a command without being part of it.
# "can you please open chrome" -> lead verb is "open", not "can".
_POLITE_PREFIXES = frozenset({
    "can", "could", "would", "please", "hey", "hi", "hello", "ok", "okay",
    "now", "just", "lets", "let", "us", "i", "want", "need", "to", "try",
    "also", "and", "then", "so", "well", "um", "uh", "maybe", "right",
    "yeah", "myself", "me",
})

# Two-word phrases whose first word is NOT a command verb in that position.
# "search for open source projects" -> "open" here is an adjective.
_NON_IMPERATIVE_BIGRAMS = frozenset({
    ("open", "source"),
    ("build", "output"),
    ("build", "artifact"),
    ("open", "ended"),
    ("close", "up"),
})

# ─── Command verbs ──────────────────────────────────────────────────────────
# The lexicon of verbs that can HEAD a command. A clause whose first
# meaningful word is not in here is an argument or a continuation.
COMMAND_VERBS = frozenset({
    # system / hardware
    "lock", "unlock", "mute", "unmute", "increase", "decrease", "turn", "raise",
    "lower", "louder", "quieter", "volume", "screenshot", "capture", "press",
    "hit", "restore", "maximize", "minimize", "toggle", "focus", "refresh",
    "reload", "restart", "brightness", "zoom", "kill", "quit", "exit",
    "show", "hide", "close", "take", "screen", "save", "play",
    # apps / navigation
    "open", "launch", "start", "go", "switch", "navigate", "visit", "browse",
    "install", "uninstall", "run", "execute",
    # files & folders
    "create", "make", "add", "new", "rename", "change", "delete", "remove",
    "clear", "copy", "paste", "move", "export", "import",
    # input
    "type", "write", "dictate", "say", "read", "select", "send",
    # search / info
    "search", "look", "find", "check", "get", "fetch", "download", "upload",
    "explain", "generate", "summarize", "calculate", "convert", "translate",
    "draw", "describe", "compare", "list",
    # dev
    "push", "pull", "commit", "merge", "rebase", "enable", "disable", "configure",
    "deploy", "test", "debug",
})

# Verbs that are only a command when a specific kind of object follows.
# "new folder assets" creates a folder; "new and final.txt" is the tail of
# a file name, not a command.
_VERB_REQUIRES_OBJECT: Dict[str, frozenset] = {
    "new": frozenset({"folder", "file", "document", "window", "tab", "note", "project"}),
    "add": frozenset({"file", "folder", "note", "tab", "item", "text", "project"}),
}

# The classifier must be reasonably sure of a clause before it is executed on
# its own. Below this the planner declines to split and the whole utterance is
# handled as one command.
_MIN_CLAUSE_CONFIDENCE = 0.20

# A destructive clause, and the clause right after it, must both be confident.
_MIN_DESTRUCTIVE_CONFIDENCE = 0.60

# Verbs that destroy something. A conjunction after one of these is ambiguous
# ("delete tmp and build folders"), so we demand extra confidence.
_DESTRUCTIVE_VERBS = frozenset({
    "delete", "remove", "clear", "erase", "trash", "wipe", "format", "uninstall",
})

# Lead verbs that open an application, and lead verbs that continue inside a
# browser. "open chrome" + "search for X" is one browser workflow.
_APP_OPEN_VERBS = frozenset({"open", "launch", "start"})
_BROWSER_CONTINUATION_VERBS = frozenset({
    "search", "look", "find", "go", "navigate", "visit", "browse", "google",
    "play", "listen",
})

# A clause that is only an application NAME ("brave", "edge") inherits the
# previous clause's verb ("open chrome, brave, and edge").
_MIN_APP_NAME_CONFIDENCE = 0.40

# Words that introduce a NAME. After one of these, the following words are
# part of the name and must never be treated as a new command:
# "create a folder called Cats and Dogs" -> "Dogs" belongs to the name.
_NAME_INTRODUCERS = ("called", "named", "titled", "entitled")

# Intents that mean "the classifier did not understand this".
_UNKNOWN_INTENTS = frozenset({"unknown"})


class _Clause:
    """One candidate command clause plus everything we learned about it."""

    __slots__ = ("text", "intent", "confidence", "lead_verb", "words")

    def __init__(self, text: str, intent: str, confidence: float, lead_verb: Optional[str]):
        self.text = text
        self.intent = intent
        self.confidence = confidence
        self.lead_verb = lead_verb
        self.words = [w.lower() for w in _WORD_RE.findall(text)]

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"_Clause({self.text!r}, {self.intent}, {self.confidence:.2f}, {self.lead_verb!r})"


def _classify(text: str) -> Tuple[str, float]:
    """Returns (intent, confidence) for a clause, or ('unknown', 0.0) on error."""
    from actions.intent_classifier import intent_classifier

    try:
        _, intent, confidence = intent_classifier.classify(text)
    except Exception as e:  # pragma: no cover - defensive
        logger.debug(f"CommandPlanner: classification failed for '{text}': {e}")
        return "unknown", 0.0
    return intent, confidence


def _lead_verb(clause: str) -> Optional[str]:
    """
    The command verb that heads this clause, or None if it is not a command.

    Politeness words are skipped ("can you please open chrome" -> "open"), and
    known non-imperative bigrams are rejected ("open source" -> None).
    """
    words = [w.lower() for w in _WORD_RE.findall(clause)]
    idx = 0
    while idx < len(words) and words[idx] in _POLITE_PREFIXES:
        idx += 1
    if idx >= len(words):
        return None
    if idx + 1 < len(words) and (words[idx], words[idx + 1]) in _NON_IMPERATIVE_BIGRAMS:
        return None
    verb = words[idx]
    if verb not in COMMAND_VERBS:
        return None

    # A few verbs only head a command when the right kind of object follows.
    required = _VERB_REQUIRES_OBJECT.get(verb)
    if required:
        following = words[idx + 1] if idx + 1 < len(words) else ""
        if not any(following.startswith(noun) for noun in required):
            return None

    return verb


def _candidate_split(text: str) -> List[str]:
    """Split on conjunctions, returning non-empty stripped clauses."""
    return [
        p.strip(" ,.;!?")
        for p in _SPLIT_PATTERN.split(text)
        if p and p.strip(" ,.;!?")
    ]


def _analyse(clause: str) -> _Clause:
    """Classify a clause and work out its lead verb."""
    intent, confidence = _classify(clause)
    return _Clause(clause, intent, confidence, _lead_verb(clause))


def _is_executable(clause: _Clause) -> bool:
    """True if this clause is independently actionable on its own."""
    if clause.intent in _UNKNOWN_INTENTS:
        return False
    if clause.lead_verb is None:
        return False
    return clause.confidence >= _MIN_CLAUSE_CONFIDENCE


def _expand_app_name_lists(clauses: List[_Clause]) -> List[_Clause]:
    """
    Restore an elided verb in a list of application names.

    "open chrome, brave, and edge" is three commands: the verb applies to
    every item in the list. "open chrome and brave" is the same construction
    spoken without the comma.

    Only expanded when the fragment is short, is not itself a command, is not
    part of a name introduced by "called"/"named", and the classifier
    confidently recognises it as an application or site.
    """
    expanded: List[_Clause] = []
    for clause in clauses:
        if expanded:
            previous = expanded[-1]
            previous_low = previous.text.lower()
            introduces_name = any(word in previous_low for word in _NAME_INTRODUCERS)
            if (
                previous.lead_verb in _APP_OPEN_VERBS
                and not introduces_name
                and clause.lead_verb is None
                and 1 <= len(clause.words) <= 2
            ):
                intent, confidence = _classify(f"open {clause.text}")
                if (
                    intent in ("open_application", "open_website")
                    and confidence >= _MIN_APP_NAME_CONFIDENCE
                ):
                    expanded.append(_analyse(f"open {clause.text}"))
                    continue
        expanded.append(clause)
    return expanded


def _merge_browser_continuations(clauses: List[_Clause]) -> List[_Clause]:
    """
    Re-merge "open <browser>" + "<search>" into a single browser workflow.

    The API lane already knows how to run "open chrome and search for X" as
    one compound_browser action (one window, one search). Splitting it would
    open two browsers, so it is left intact.
    """
    merged: List[_Clause] = []
    for clause in clauses:
        if merged:
            previous = merged[-1]
            if (
                previous.lead_verb in _APP_OPEN_VERBS
                and previous.intent in ("open_application", "open_website")
                and clause.lead_verb in _BROWSER_CONTINUATION_VERBS
                and clause.intent in ("web_search", "compound_browser", "open_website")
            ):
                merged[-1] = _analyse(f"{previous.text} and {clause.text}")
                continue
        merged.append(clause)
    return merged


def _destructive_boundary_is_safe(clauses: List[_Clause]) -> bool:
    """
    Guard against destructive clauses swallowing the conjunction.

    "delete tmp and build folders" is ONE delete of a folder called
    "tmp and build folders" — not "delete tmp" followed by "open build
    folders". Only split when both sides are confident.
    """
    for index, clause in enumerate(clauses):
        if clause.lead_verb not in _DESTRUCTIVE_VERBS:
            continue
        if clause.confidence < _MIN_DESTRUCTIVE_CONFIDENCE:
            return False
        if index + 1 < len(clauses) and clauses[index + 1].confidence < _MIN_DESTRUCTIVE_CONFIDENCE:
            return False
    return True


def split_compound_command(text: str) -> Optional[List[str]]:
    """
    Splits a compound utterance into independent command clauses.

    Returns a list of clauses if the utterance genuinely contains multiple
    commands, or None if it should be treated as a single command.

    None means "do not split" — the caller must handle the utterance as one
    command, exactly as before.
    """
    if not text or not text.strip():
        return None

    raw_clauses = _candidate_split(text)
    if len(raw_clauses) < 2:
        return None

    clauses = [_analyse(c) for c in raw_clauses]
    clauses = _expand_app_name_lists(clauses)
    clauses = _merge_browser_continuations(clauses)

    if len(clauses) < 2:
        return None

    for clause in clauses:
        if not _is_executable(clause):
            logger.debug(f"CommandPlanner: '{clause.text}' is not an independent command — not a split.")
            return None

    if not _destructive_boundary_is_safe(clauses):
        logger.debug("CommandPlanner: destructive clause is not confident enough to split — not a split.")
        return None

    result = [c.text for c in clauses]
    logger.info(f"CommandPlanner: split '{text}' into {result}")
    return result


def is_compound(text: str) -> bool:
    """Convenience predicate: does this utterance contain multiple commands?"""
    return split_compound_command(text) is not None
