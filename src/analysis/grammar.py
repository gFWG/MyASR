"""Grammar pattern matching for Japanese text."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from src.db.models import GrammarHit

logger = logging.getLogger(__name__)


@dataclass
class _CompiledRule:
    """Internal: a grammar rule with pre-compiled regex."""

    rule_id: str
    pattern: re.Pattern[str]
    jlpt_level: int
    confidence_type: str
    description: str


class GrammarMatcher:
    """Match grammar patterns in Japanese text using pre-compiled regex."""

    def __init__(self, rules_path: str) -> None:
        """Load grammar rules from JSON and pre-compile regex patterns.

        Args:
            rules_path: Path to JSON file with grammar rules array.

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
            self._rules.append(
                _CompiledRule(
                    rule_id=str(rule["rule_id"]),
                    pattern=re.compile(str(rule["pattern_regex"])),
                    jlpt_level=int(str(rule["jlpt_level"])),
                    confidence_type=str(rule["confidence_type"]),
                    description=str(rule["description"]),
                )
            )
        logger.info("Loaded %d grammar rules from %s", len(self._rules), rules_path)

    def match(self, text: str, user_level: int) -> list[GrammarHit]:
        """Find grammar patterns beyond user's JLPT level in text.

        A pattern is "beyond level" when rule.jlpt_level < user_level.
        Returns all matching patterns that are beyond user's level.

        Args:
            text: Japanese text to analyze.
            user_level: User's current JLPT level (1-5).

        Returns:
            List of GrammarHit for patterns found AND beyond user's level.
        """
        if not text:
            return []
        hits: list[GrammarHit] = []
        for rule in self._rules:
            if rule.jlpt_level >= user_level:
                continue
            for m in rule.pattern.finditer(text):
                hits.append(
                    GrammarHit(
                        rule_id=rule.rule_id,
                        matched_text=m.group(),
                        jlpt_level=rule.jlpt_level,
                        confidence_type=rule.confidence_type,
                        description=rule.description,
                    )
                )
        return hits
