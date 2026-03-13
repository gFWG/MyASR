"""JLPT vocabulary lookup for Japanese learning."""

import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from src.models import Token, VocabHit

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VocabEntry:
    """Single JLPT vocabulary entry.

    Attributes:
        vocab_id: Unique identifier from the vocabulary source.
        pronunciation: Reading in katakana (pronBase).
        lemma: Dictionary form of the word.
        definition: English gloss.
        level: JLPT level 1-5 (1=N1 hardest, 5=N5 easiest).
    """

    vocab_id: int
    pronunciation: str
    lemma: str
    definition: str
    level: int


class JLPTVocabLookup:
    """Load JLPT vocabulary and perform lookups.

    Supports CSV (id,pronBase,lemma,definition,level) and legacy JSON
    ({lemma: level_int}) formats, detected by file extension.
    """

    def __init__(self, vocab_path: str) -> None:
        """Load JLPT vocabulary file.

        Args:
            vocab_path: Path to CSV or JSON vocabulary file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        path = Path(vocab_path)
        if not path.exists():
            raise FileNotFoundError(f"Vocab file not found: {vocab_path}")

        self._vocab: dict[str, VocabEntry]

        if path.suffix == ".csv":
            self._vocab = self._load_csv(path)
        else:
            self._vocab = self._load_json(path)

        logger.info("Loaded %d JLPT vocab entries from %s", len(self._vocab), vocab_path)

    @staticmethod
    def _load_csv(path: Path) -> dict[str, VocabEntry]:
        """Load vocabulary from CSV with columns id,pronBase,lemma,definition,level.

        Duplicate lemmas are resolved by keeping the easiest level (highest int).
        Rows are processed in id order; a later row overwrites only if its level
        is strictly higher than the existing entry's level.

        Args:
            path: Path to the CSV file.

        Returns:
            Dict mapping lemma → VocabEntry.
        """
        vocab: dict[str, VocabEntry] = {}
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                lemma = row["lemma"]
                level = int(row["level"][1:])  # 'N5' → 5
                entry = VocabEntry(
                    vocab_id=int(row["id"]),
                    pronunciation=row["pronBase"],
                    lemma=lemma,
                    definition=row["definition"],
                    level=level,
                )
                existing = vocab.get(lemma)
                if existing is None or level > existing.level:
                    vocab[lemma] = entry
        return vocab

    @staticmethod
    def _load_json(path: Path) -> dict[str, VocabEntry]:
        """Load legacy JSON vocabulary {lemma: level_int}.

        Args:
            path: Path to the JSON file.

        Returns:
            Dict mapping lemma → VocabEntry (with placeholder vocab_id/pronunciation/definition).
        """
        with path.open(encoding="utf-8") as f:
            raw: dict[str, int] = json.load(f)
        return {
            lemma: VocabEntry(
                vocab_id=0,
                pronunciation="",
                lemma=lemma,
                definition="",
                level=level,
            )
            for lemma, level in raw.items()
        }

    def lookup(self, lemma: str) -> int | None:
        """Return JLPT level (1-5) for a lemma, or None if not found.

        Args:
            lemma: Dictionary form of the word.

        Returns:
            JLPT level 1-5 (1=N1 hardest, 5=N5 easiest), or None.
        """
        entry = self._vocab.get(lemma)
        return entry.level if entry is not None else None

    def lookup_entry(self, lemma: str) -> VocabEntry | None:
        """Return the full VocabEntry for a lemma, or None if not found.

        Args:
            lemma: Dictionary form of the word.

        Returns:
            VocabEntry or None.
        """
        return self._vocab.get(lemma)

    def find_all_vocab(
        self, tokens: list[Token], text: str = ""
    ) -> list[VocabHit]:
        """Find all JLPT vocabulary in tokens.

        Returns ALL vocab matches with their JLPT levels, without filtering by user level.
        Display-time filtering should use SentenceResult.get_display_analysis().

        Fugashi may produce compound lemmas like '私-代名詞'; the part after '-'
        is stripped before lookup so that the base form is matched in the vocabulary.

        Args:
            tokens: List of Token objects to check.
            text: Original text for calculating character positions.

        Returns:
            List of VocabHit for all words found in vocabulary.
        """
        hits: list[VocabHit] = []
        search_start = 0
        for token in tokens:
            clean_lemma = token.lemma.split("-")[0]
            entry = self.lookup_entry(clean_lemma)
            if entry is not None:
                if text:
                    pos = text.find(token.surface, search_start)
                    if pos >= 0:
                        start_pos = pos
                        end_pos = start_pos + len(token.surface)
                        search_start = end_pos
                    else:
                        start_pos = 0
                        end_pos = 0
                else:
                    start_pos = 0
                    end_pos = 0
                hits.append(
                    VocabHit(
                        surface=token.surface,
                        lemma=token.lemma,
                        pos=token.pos,
                        jlpt_level=entry.level,
                        start_pos=start_pos,
                        end_pos=end_pos,
                        vocab_id=entry.vocab_id,
                        pronunciation=entry.pronunciation,
                        definition=entry.definition,
                    )
                )
        return hits
