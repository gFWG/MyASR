"""Grammar pattern matching for Japanese text."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from src.models import GrammarHit

logger = logging.getLogger(__name__)

_MIN_MATCH_LEN: int = 2


@dataclass(frozen=True, slots=True)
class _CompiledRule:
    """Internal: a grammar rule with pre-compiled regex.

    Attributes:
        rule_id: Unique identifier for the rule.
        word: The grammar word/form being matched.
        pattern: Pre-compiled regex for matching.
        jlpt_level: JLPT level as integer 1-5 (lower = harder).
        description: Human-readable description of the grammar point.
    """

    rule_id: str
    word: str
    pattern: re.Pattern[str]
    jlpt_level: int
    description: str


class GrammarMatcher:
    """Match grammar patterns in Japanese text using pre-compiled regex."""

    def __init__(self, rules_path: str) -> None:
        """Load grammar rules from JSON and pre-compile regex patterns.

        Args:
            rules_path: Path to JSON file with grammar rules array.
                Each rule must have keys: id, re, word, description, level.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        path = Path(rules_path)
        if not path.exists():
            raise FileNotFoundError(f"Grammar rules file not found: {rules_path}")
        with path.open(encoding="utf-8") as f:
            raw_rules: list[dict[str, object]] = json.load(f)
        self._rules: list[_CompiledRule] = []
        for rule in raw_rules:
            try:
                compiled = re.compile(str(rule["re"]))
            except re.error as exc:
                logger.warning(
                    "Skipping rule id=%s (invalid regex %r): %s",
                    rule.get("id"),
                    rule.get("re"),
                    exc,
                )
                continue
            self._rules.append(
                _CompiledRule(
                    rule_id=str(rule["id"]),
                    word=str(rule["word"]),
                    pattern=compiled,
                    jlpt_level=int(str(rule["level"])[1:]),
                    description=str(rule["description"]),
                )
            )
        logger.info("Loaded %d grammar rules from %s", len(self._rules), rules_path)

    def match_all(self, text: str) -> list[GrammarHit]:
        """Find all grammar patterns in text, with overlap resolution.

        Returns ALL grammar matches with their JLPT levels, without filtering by user level.
        Display-time filtering should use SentenceResult.get_display_analysis().

        Hits are post-processed by _resolve_overlaps():
        - Hits with effective_length < _MIN_MATCH_LEN are filtered out.
          effective_length = sum of captured group lengths (matched_parts),
          or full span if no capturing groups.
        - Overlapping hits are resolved greedily (longest effective_length wins;
          ties broken by earliest start, then earliest end, then hardest JLPT).
        - Overlap detection uses matched_parts when available, otherwise full span.
        - Output is sorted by start_pos ascending.

        Args:
            text: Japanese text to analyze.

        Returns:
            List of non-overlapping GrammarHit sorted by start_pos.
        """
        if not text:
            return []
        hits: list[GrammarHit] = []
        for rule in self._rules:
            for m in rule.pattern.finditer(text):
                parts: tuple[tuple[int, int], ...] = ()
                if m.lastindex:  # has capturing groups
                    parts = tuple(
                        m.span(i) for i in range(1, m.lastindex + 1) if m.group(i) is not None
                    )
                hits.append(
                    GrammarHit(
                        rule_id=rule.rule_id,
                        word=rule.word,
                        matched_text=m.group(),
                        jlpt_level=rule.jlpt_level,
                        description=rule.description,
                        start_pos=m.start(),
                        end_pos=m.end(),
                        matched_parts=parts,
                    )
                )
        return self._resolve_overlaps(hits)

    def _resolve_overlaps(self, hits: list[GrammarHit]) -> list[GrammarHit]:
        """Filter and resolve overlapping grammar hits using matched_parts.

        Algorithm:
        1. Filter hits with effective_length < _MIN_MATCH_LEN.
           effective_length = sum of captured group lengths (matched_parts),
           or full span if no capturing groups.
        2. Sort by effective_length DESC, start_pos ASC, end_pos ASC, jlpt_level ASC
           (longest effective length first, earliest start, earliest end, hardest JLPT).
        3. Greedy interval selection based on matched_parts overlap:
           - For hits with matched_parts: check each part against all selected parts.
           - For hits without matched_parts: use full span for overlap check.
           - Any part overlaps → whole hit is suppressed.
           - Overlap is strict: start_a < end_b AND start_b < end_a.
        4. Re-sort selected hits by start_pos ascending.

        Args:
            hits: Raw grammar hits, possibly overlapping.

        Returns:
            Non-overlapping hits sorted by start_pos.
        """

        def effective_length(h: GrammarHit) -> int:
            """Calculate length based only on capturing groups, not .* content."""
            if h.matched_parts:
                return max(sum(end - start for start, end in h.matched_parts), 0)
            return max(h.end_pos - h.start_pos, 0)

        def get_parts(h: GrammarHit) -> list[tuple[int, int]]:
            """Get spans for overlap detection. Uses matched_parts if present."""
            if h.matched_parts:
                return list(h.matched_parts)
            return [(h.start_pos, h.end_pos)]

        def parts_overlap(
            parts_a: list[tuple[int, int]], parts_b: list[tuple[int, int]]
        ) -> bool:
            """Check if any span in parts_a overlaps any span in parts_b."""
            for start_a, end_a in parts_a:
                for start_b, end_b in parts_b:
                    if start_a < end_b and start_b < end_a:
                        return True
            return False

        valid = [h for h in hits if effective_length(h) >= _MIN_MATCH_LEN]
        sorted_hits = sorted(
            valid,
            key=lambda h: (-effective_length(h), h.start_pos, h.end_pos, h.jlpt_level),
        )

        selected_parts: list[tuple[int, int]] = []
        selected_hits: list[GrammarHit] = []

        for candidate in sorted_hits:
            candidate_parts = get_parts(candidate)
            if parts_overlap(candidate_parts, selected_parts):
                continue
            selected_hits.append(candidate)
            selected_parts.extend(candidate_parts)

        return sorted(selected_hits, key=lambda h: h.start_pos)
