"""Fugashi-based Japanese morphological tokenizer."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import fugashi

from src.models import Token

if TYPE_CHECKING:
    from src.analysis.jlpt_vocab import VocabEntry

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
            pos2 = word.feature.pos2 or ""
            ctype = word.feature.cType or ""
            cform = word.feature.cForm or ""
            tokens.append(
                Token(
                    surface=word.surface, lemma=lemma, pos=pos, pos2=pos2, cType=ctype, cForm=cform
                )
            )
        return tokens


MAX_COMPOUND_TOKENS = 6


def merge_prefix_compounds(tokens: list[Token], vocab: dict[str, VocabEntry]) -> list[Token]:
    """Merge prefix-compound token sequences into single tokens.

    When a 接頭辞 (prefix) token starts a sequence whose surface concatenation
    matches a vocab entry, merge all tokens in the window into one Token with:
    - surface = concatenated surfaces
    - lemma = concatenated surfaces (NOT lemma concat — avoid 御世辞)
    - pos = head content word's pos (last non-prefix token's pos)
    - pos2 = head content word's pos2

    Uses greedy longest-match (tries MAX_COMPOUND_TOKENS down to 2).

    Args:
        tokens: Tokenized tokens (output of FugashiTokenizer.tokenize).
        vocab: Dict mapping lemma → VocabEntry (from JLPTVocabLookup.vocab_entries).

    Returns:
        New token list with compound sequences merged.
    """
    result: list[Token] = []
    i = 0
    while i < len(tokens):
        if tokens[i].pos == "接頭辞":
            merged = False
            # Try from longest to shortest window
            for w in range(min(MAX_COMPOUND_TOKENS, len(tokens) - i), 1, -1):
                surface = "".join(t.surface for t in tokens[i : i + w])
                if surface in vocab:
                    # Find head content word (last non-接頭辞 token in window)
                    head = tokens[i + w - 1]
                    for j in range(i + w - 1, i - 1, -1):
                        if tokens[j].pos != "接頭辞":
                            head = tokens[j]
                            break
                    result.append(
                        Token(
                            surface=surface,
                            lemma=surface,
                            pos=head.pos,
                            pos2=head.pos2,
                            cType=head.cType,
                            cForm=head.cForm,
                        )
                    )
                    i += w
                    merged = True
                    break
            if not merged:
                result.append(tokens[i])
                i += 1
        else:
            result.append(tokens[i])
            i += 1
    return result
