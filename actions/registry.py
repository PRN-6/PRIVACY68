"""
PRIVACY68 — Declarative Command Registry.

Every command the assistant can run is described by a single `CommandSpec`:

    id          unique name of the command
    lane        which execution lane owns it (fast / api / llm)
    intent      the label the intent classifier predicts for it
    handler     the callable that performs the command
    matchers    the ways the command can be recognised (exact phrase / regex)
    examples    training phrases that teach the classifier the intent

Adding a command therefore means adding ONE spec to the catalogue. It no
longer means finding the right `if` in a growing dispatcher, and it no
longer means updating three separate tables (classifier keyword map,
dispatcher branch, slot regexes) that drift apart.

The registry is also the single source of truth for the intent taxonomy:
the classifier, the slot extractor and the lane dispatchers all read the
same specs instead of keeping private copies of the same knowledge.

Design notes
------------
* Exact matching is an O(1) dict lookup on a normalised phrase.
* Regex matching is a single, priority-ordered list of compiled patterns.
* Slot values come from the matcher that fired (named capture groups),
  so recognising a command and understanding it are one step, not two.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

# ─── Lanes ───────────────────────────────────────────────────────────────────
LANE_FAST = "fast_lane"
LANE_API = "api_lane"
LANE_LLM = "llm_lane"

#: Lanes in the order they are attempted. Lane 1 is free and instant,
#: lane 2 talks to the network, lane 3 needs a local model.
LANES: Tuple[str, ...] = (LANE_FAST, LANE_API, LANE_LLM)

# ─── Stages ──────────────────────────────────────────────────────────────────
#: Runs before anything else and may consume the utterance entirely
#: (security confirmation, greeting acknowledgement).
STAGE_INTERCEPT = "intercept"
#: Scripted multi-step workflows.
STAGE_MACRO = "macro"
#: Ordinary commands.
STAGE_EXECUTE = "execute"

STAGES: Tuple[str, ...] = (STAGE_INTERCEPT, STAGE_MACRO, STAGE_EXECUTE)

# ─── Text normalisation ──────────────────────────────────────────────────────
_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_WS_RE = re.compile(r"\s+", re.UNICODE)

_POLITE_WORDS = frozenset({
    "please", "can", "could", "would", "will", "you", "hey", "hi", "hello",
    "ok", "okay", "now", "just", "lets", "let", "us", "i", "want", "need",
    "to", "try", "also", "and", "then", "so", "well", "um", "uh", "maybe",
    "right", "yeah", "myself", "me", "go", "ahead",
})


def normalize(text: str) -> str:
    """Case-, punctuation- and whitespace-insensitive key for exact matching."""
    if not text:
        return ""
    return _WS_RE.sub(" ", _PUNCT_RE.sub(" ", text.lower())).strip()


def strip_polite_prefix(text: str) -> str:
    """Removes leading filler words ("please", "can you", "hey", ...)."""
    words = text.strip().split()
    while words and words[0].lower().strip(".!?, ") in _POLITE_WORDS:
        words.pop(0)
    return " ".join(words).strip()


# ─── Matcher ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Matcher:
    """
    One way of recognising a command.

    Either an exact `phrase` (normalised automatically) or a regex
    `pattern`. Named capture groups in the pattern bind to slots with the
    same name; `groups` renames them, and `consts` supplies fixed slot
    values (used by variant tables such as "volume up" -> `volume_up`).
    """

    phrase: Optional[str] = None
    pattern: Optional[str] = None
    consts: Tuple[Tuple[str, str], ...] = ()
    groups: Tuple[Tuple[str, str], ...] = ()
    priority: int = 0

    def __post_init__(self) -> None:
        if self.phrase is None and self.pattern is None:
            raise ValueError("Matcher needs either a phrase or a pattern")
        if self.phrase is not None:
            object.__setattr__(self, "phrase", normalize(self.phrase))

    @property
    def is_exact(self) -> bool:
        return self.phrase is not None


@dataclass(frozen=True)
class CommandSpec:
    """A single executable command."""

    id: str
    lane: str
    intent: str
    handler: Optional[Callable[["CommandContext"], Dict[str, Any]]] = None
    matchers: Tuple[Matcher, ...] = ()
    examples: Tuple[str, ...] = ()
    stage: str = STAGE_EXECUTE
    priority: int = 0
    description: str = ""
    #: Pulls the arguments out of an utterance when the matcher did not
    #: capture them itself (broad matchers such as "create a folder ...").
    slot_extractor: Optional[Callable[[str], Dict[str, str]]] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "matchers", tuple(self.matchers))
        object.__setattr__(self, "examples", tuple(self.examples))


@dataclass
class CommandContext:
    """Everything a handler needs to run a command."""

    text: str
    slots: Dict[str, str] = field(default_factory=dict)
    intent: str = ""
    spec: Optional[CommandSpec] = None
    confidence: float = 1.0
    matched_by: str = "intent"

    def slot(self, name: str, default: str = "") -> str:
        value = self.slots.get(name)
        return default if value is None else value


@dataclass
class Match:
    """The outcome of recognising a command."""

    spec: CommandSpec
    slots: Dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    matched_by: str = "pattern"

    def context(self, text: str) -> CommandContext:
        return CommandContext(
            text=text,
            slots=dict(self.slots),
            intent=self.spec.intent,
            spec=self.spec,
            confidence=self.confidence,
            matched_by=self.matched_by,
        )


class CommandRegistry:
    """
    Holds every known command and answers two questions:

      * "does this utterance match a command?"  -> `match()`
      * "which command does this intent mean?"  -> `spec_for_intent()`

    Lookups are ordered by priority, so a specific command always beats a
    generic one regardless of the order the specs were registered in.
    """

    def __init__(self) -> None:
        self._specs: Dict[str, CommandSpec] = {}
        # lane -> normalised phrase -> [(spec, matcher)]
        self._phrases: Dict[str, Dict[str, List[Tuple[CommandSpec, Matcher]]]] = {
            lane: {} for lane in LANES
        }
        # lane -> ordered [(spec, matcher, compiled_pattern)]
        self._patterns: Dict[str, List[Tuple[CommandSpec, Matcher, Any]]] = {
            lane: [] for lane in LANES
        }
        self._by_intent: Dict[str, CommandSpec] = {}

    # ── Registration ────────────────────────────────────────────────────────
    def register(self, spec: CommandSpec) -> CommandSpec:
        """Adds (or replaces) a command spec and rebuilds the indexes."""
        self._specs[spec.id] = spec

        for matcher in spec.matchers:
            if matcher.is_exact:
                bucket = self._phrases[spec.lane].setdefault(matcher.phrase, [])
                bucket.append((spec, matcher))
            else:
                try:
                    compiled = re.compile(matcher.pattern, re.IGNORECASE)
                except re.error as exc:
                    raise ValueError(
                        f"Invalid pattern for '{spec.id}': {exc}"
                    ) from exc
                self._patterns[spec.lane].append((spec, matcher, compiled))

        self._reindex()
        return spec

    def register_all(self, specs: Iterable[CommandSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def unregister(self, spec_id: str) -> None:
        """Removes a command and everything the indexes know about it."""
        self._specs.pop(spec_id, None)

        for phrases in self._phrases.values():
            for phrase in list(phrases):
                phrases[phrase] = [entry for entry in phrases[phrase] if entry[0].id != spec_id]
                if not phrases[phrase]:
                    del phrases[phrase]

        for lane, entries in self._patterns.items():
            self._patterns[lane] = [entry for entry in entries if entry[0].id != spec_id]

        self._reindex()

    def _reindex(self) -> None:
        """Sorts the pattern list by priority (highest first)."""
        for lane, entries in self._patterns.items():
            entries.sort(key=lambda e: (e[0].priority, e[1].priority), reverse=True)

        self._by_intent = {}
        for spec in self._specs.values():
            self._by_intent.setdefault(spec.intent, spec)

    # ── Queries ─────────────────────────────────────────────────────────────
    def get(self, spec_id: str) -> Optional[CommandSpec]:
        return self._specs.get(spec_id)

    def all(self) -> List[CommandSpec]:
        return list(self._specs.values())

    def specs_for_lane(self, lane: str) -> List[CommandSpec]:
        return [s for s in self._specs.values() if s.lane == lane]

    def spec_for_intent(self, intent: str) -> Optional[CommandSpec]:
        """The command that owns an intent (first registered wins)."""
        return self._by_intent.get(intent)

    def intents(self) -> List[str]:
        return sorted(self._by_intent)

    def match(self, text: str, lane: Optional[str] = None) -> Optional[Match]:
        """
        Finds the best command for `text`.

        Exact phrases are tried first (O(1)), then the priority-ordered
        regex list. `lane` restricts the search to a single lane.
        """
        if not text or not text.strip():
            return None

        lanes = (lane,) if lane else LANES

        for current in lanes:
            hit = self._match_exact(text, current)
            if hit:
                return hit

        for current in lanes:
            hit = self._match_pattern(text, current)
            if hit:
                return hit

        return None

    def _match_exact(self, text: str, lane: str) -> Optional[Match]:
        bucket = self._phrases.get(lane, {}).get(normalize(text))
        if not bucket:
            return None
        spec, matcher = max(
            bucket, key=lambda e: (e[0].priority, e[1].priority)
        )
        return Match(
            spec=spec,
            slots=dict(matcher.consts),
            confidence=1.0,
            matched_by="phrase",
        )

    def _match_pattern(self, text: str, lane: str) -> Optional[Match]:
        for spec, matcher, compiled in self._patterns.get(lane, []):
            found = compiled.search(text)
            if not found:
                continue
            return Match(
                spec=spec,
                slots=self._build_slots(matcher, found),
                confidence=0.9,
                matched_by="pattern",
            )
        return None

    @staticmethod
    def _build_slots(matcher: Matcher, found: "re.Match") -> Dict[str, str]:
        """Turns a regex match into slot values."""
        slots = dict(matcher.consts)
        groups = found.groupdict() or {}

        for group, slot in matcher.groups:
            value = groups.get(group)
            if value:
                slots[slot] = value.strip()

        for group, value in groups.items():
            if group in slots or not value:
                continue
            slots[group] = value.strip()

        return slots

    def match_spec(self, text: str, spec_id: str) -> Optional[Match]:
        """
        Finds `text` for one specific command.

        Used by the slot extractor: it needs the arguments of a known
        command, not the arguments of whatever else happened to match.
        """
        spec = self._specs.get(spec_id)
        if spec is None or not text or not text.strip():
            return None

        for candidate, matcher in self._phrases.get(spec.lane, {}).get(normalize(text), []):
            if candidate.id == spec_id:
                return Match(
                    spec=candidate,
                    slots=dict(matcher.consts),
                    confidence=1.0,
                    matched_by="phrase",
                )

        for candidate, matcher, compiled in self._patterns.get(spec.lane, []):
            if candidate.id != spec_id:
                continue
            found = compiled.search(text)
            if found:
                return Match(
                    spec=candidate,
                    slots=self._build_slots(matcher, found),
                    confidence=0.9,
                    matched_by="pattern",
                )

        return None

    # ── Training data ───────────────────────────────────────────────────────
    def training_corpus(self) -> List[Tuple[str, str]]:
        """(utterance, intent) pairs for the intent classifier."""
        corpus: List[Tuple[str, str]] = []
        seen = set()
        for spec in self._specs.values():
            for example in spec.examples:
                key = (normalize(example), spec.intent)
                if not example.strip() or key in seen:
                    continue
                seen.add(key)
                corpus.append((example.strip(), spec.intent))
        return corpus

    def intent_lane(self) -> Dict[str, str]:
        """intent -> owning lane."""
        return {intent: spec.lane for intent, spec in self._by_intent.items()}


#: The process-wide registry. Built by `actions.catalog`.
registry = CommandRegistry()
