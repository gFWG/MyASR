"""JLPT vocabulary lookup for Japanese learning."""

import json
import logging
from pathlib import Path

from src.db.models import Token, VocabHit

logger = logging.getLogger(__name__)


class JLPTVocabLookup:
    """Load JLPT vocabulary dict and perform lookups."""

    def __init__(self, vocab_path: str) -> None:
        """Load JLPT vocabulary JSON file.

        Args:
            vocab_path: Path to JSON file with format {"lemma": level_int}.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        path = Path(vocab_path)
        if not path.exists():
            raise FileNotFoundError(f"Vocab file not found: {vocab_path}")
        with path.open(encoding="utf-8") as f:
            self._vocab: dict[str, int] = json.load(f)
        logger.info("Loaded %d JLPT vocab entries from %s", len(self._vocab), vocab_path)

    def lookup(self, lemma: str) -> int | None:
        """Return JLPT level (1-5) for a lemma, or None if not found.

        Args:
            lemma: Dictionary form of the word.

        Returns:
            JLPT level 1-5 (1=N1 hardest, 5=N5 easiest), or None.
        """
        return self._vocab.get(lemma)

    def find_beyond_level(self, tokens: list[Token], user_level: int) -> list[VocabHit]:
        """Find tokens that are harder than the user's JLPT level.

        A word is "beyond level" when word_jlpt_level < user_level.
        Example: user_level=3 (N3), word at N1 → jlpt_level=1 < 3 → beyond level.
        Example: user_level=3 (N3), word at N5 → jlpt_level=5 > 3 → NOT beyond level.

        Args:
            tokens: List of Token objects to check.
            user_level: User's current JLPT level (1-5).

        Returns:
            List of VocabHit for words harder than user's level.
        """
        hits: list[VocabHit] = []
        for token in tokens:
            level = self.lookup(token.lemma)
            if level is not None and level < user_level:
                hits.append(
                    VocabHit(
                        surface=token.surface,
                        lemma=token.lemma,
                        pos=token.pos,
                        jlpt_level=level,
                        user_level=user_level,
                    )
                )
        return hits
