"""Fugashi-based Japanese morphological tokenizer."""

import logging

import fugashi

from src.db.models import Token

logger = logging.getLogger(__name__)

FILTER_POS = {"補助記号", "記号"}  # POS categories to filter out (punctuation/symbols)


class FugashiTokenizer:
    """Wraps fugashi.Tagger for Japanese morphological analysis."""

    def __init__(self) -> None:
        """Initialize with fugashi.Tagger (uses unidic-lite automatically)."""
        self._tagger: fugashi.Tagger = fugashi.Tagger()

    @property
    def tagger(self) -> fugashi.Tagger:
        """Expose internal tagger for sharing with jreadability."""
        return self._tagger

    def tokenize(self, text: str) -> list[Token]:
        """Tokenize Japanese text into Token objects.

        Args:
            text: Japanese text to tokenize.

        Returns:
            List of Token objects, with punctuation/symbol tokens filtered out.
            Returns empty list for empty input.
        """
        if not text:
            return []
        tokens: list[Token] = []
        for word in self._tagger(text):
            pos = word.feature.pos1
            # Filter out punctuation and symbols
            if pos in FILTER_POS:
                continue
            # word.feature.lemma may be None for some tokens — fallback to surface
            lemma = word.feature.lemma
            if lemma is None:
                lemma = word.surface
            tokens.append(Token(surface=word.surface, lemma=lemma, pos=pos))
        return tokens
