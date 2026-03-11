from PySide6.QtWidgets import QLabel

from src.db.models import HighlightVocab, SentenceRecord
from src.ui.sentence_detail import SentenceDetailDialog


def test_sentence_detail_vocab_rendering(qapp):
    sentence = SentenceRecord(
        id=1, japanese_text="テスト", source_context="test", created_at="2026-01-01 12:00:00"
    )

    vocab_hits = [
        HighlightVocab(
            id=1,
            sentence_id=1,
            surface="猫",
            lemma="猫",
            pos="Noun",
            jlpt_level=5,
            is_beyond_level=False,
            tooltip_shown=False,
            vocab_id=10,
            pronunciation="ネコ",
            definition="Cat",
        )
    ]

    dialog = SentenceDetailDialog(sentence, vocab_hits, [])

    labels = dialog.findChildren(QLabel)
    texts = [label.text() for label in labels]

    assert "[ネコ]" in texts, "Pronunciation should be displayed"
    assert "Cat" in texts, "Definition should be displayed"


def test_sentence_detail_vocab_empty_fields(qapp):
    sentence = SentenceRecord(
        id=1, japanese_text="テスト", source_context="test", created_at="2026-01-01 12:00:00"
    )

    vocab_hits = [
        HighlightVocab(
            id=1,
            sentence_id=1,
            surface="猫",
            lemma="猫",
            pos="Noun",
            jlpt_level=5,
            is_beyond_level=False,
            tooltip_shown=False,
            vocab_id=10,
            pronunciation="",
            definition="",
        )
    ]

    dialog = SentenceDetailDialog(sentence, vocab_hits, [])

    labels = dialog.findChildren(QLabel)
    texts = [label.text() for label in labels]

    assert "[]" not in texts, "Empty pronunciation should not be displayed as []"
    assert "—" not in texts, "Separator shouldn't be displayed if definition is empty"
