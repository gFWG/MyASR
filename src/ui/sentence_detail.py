"""Sentence detail dialog for viewing saved sentences with JLPT annotations.

Displays a sentence's Japanese text alongside JLPT-badged vocabulary and
grammar sections.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.db.models import AnalysisResult, HighlightGrammar, HighlightVocab, SentenceRecord
from src.ui.highlight import HighlightRenderer

logger = logging.getLogger(__name__)

_JLPT_COLORS = HighlightRenderer.JLPT_COLORS
_DEFAULT_BADGE_COLOR = "#9E9E9E"

_FONT_FAMILIES = "Segoe UI, Yu Gothic UI, Noto Sans CJK JP, sans-serif"

_EMPTY_ANALYSIS = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[])


def _badge_color(jlpt_level: int | None) -> str:
    if jlpt_level is None or jlpt_level not in _JLPT_COLORS:
        return _DEFAULT_BADGE_COLOR
    return _JLPT_COLORS[jlpt_level]["grammar"]


def _make_jlpt_badge(jlpt_level: int | None) -> QLabel:
    """Create a colored JLPT-level pill badge label (e.g. 'N3').

    Args:
        jlpt_level: Integer JLPT level 1–5, or None for unknown.

    Returns:
        A QLabel styled as a colored pill badge.
    """
    text = f"N{jlpt_level}" if jlpt_level is not None else "N?"
    color = _badge_color(jlpt_level)
    badge = QLabel(text)
    badge.setStyleSheet(
        f"background-color: {color}; color: white; font-weight: bold;"
        " padding: 2px 6px; border-radius: 3px;"
    )
    badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return badge


class SentenceDetailDialog(QDialog):
    """Detail view for a saved sentence with JLPT-annotated vocab and grammar.

    Args:
        sentence: The sentence record to display.
        vocab_hits: Vocabulary annotations stored with the sentence.
        grammar_hits: Grammar annotations stored with the sentence.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        sentence: SentenceRecord,
        vocab_hits: list[HighlightVocab],
        grammar_hits: list[HighlightGrammar],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sentence Detail")
        self.setMinimumSize(500, 400)

        self._sentence = sentence
        self._vocab_hits = vocab_hits
        self._grammar_hits = grammar_hits

        self._build_ui()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(12)

        content_layout.addWidget(self._build_header())
        content_layout.addWidget(self._build_japanese_section())

        if self._vocab_hits:
            content_layout.addWidget(self._build_vocab_group())

        if self._grammar_hits:
            content_layout.addWidget(self._build_grammar_group())

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        outer_layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        outer_layout.addLayout(btn_layout)

    def _build_header(self) -> QLabel:
        label = QLabel(self._sentence.created_at)
        label.setStyleSheet("color: #888888; font-size: 11px;")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        return label

    def _build_japanese_section(self) -> QTextBrowser:
        browser = QTextBrowser()
        browser.setReadOnly(True)
        browser.setFrameShape(QTextBrowser.Shape.NoFrame)
        browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setStyleSheet(f"font-family: {_FONT_FAMILIES}; font-size: 18px;")
        browser.setFixedHeight(60)
        browser.setOpenLinks(False)
        html_text = HighlightRenderer().build_rich_text(
            self._sentence.japanese_text,
            _EMPTY_ANALYSIS,
            user_level=5,
        )
        browser.setHtml(html_text)
        return browser

    def _build_vocab_group(self) -> QGroupBox:
        group = QGroupBox("Vocabulary")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        for vh in self._vocab_hits:
            row = QHBoxLayout()
            row.setSpacing(8)

            row.addWidget(_make_jlpt_badge(vh.jlpt_level))

            surface_label = QLabel(vh.surface)
            surface_label.setStyleSheet("font-weight: bold; font-size: 13px;")
            row.addWidget(surface_label)

            sep1 = QLabel("·")
            sep1.setStyleSheet("color: #888888;")
            row.addWidget(sep1)

            lemma_label = QLabel(vh.lemma)
            lemma_label.setStyleSheet("font-size: 13px; color: #555555;")
            row.addWidget(lemma_label)

            sep2 = QLabel("·")
            sep2.setStyleSheet("color: #888888;")
            row.addWidget(sep2)

            pos_label = QLabel(vh.pos)
            pos_label.setStyleSheet("font-size: 12px; color: #777777; font-style: italic;")
            row.addWidget(pos_label)

            if vh.pronunciation:
                pron_label = QLabel(f"[{vh.pronunciation}]")
                pron_label.setStyleSheet("font-size: 12px; color: #777777;")
                row.addWidget(pron_label)

            if vh.definition:
                sep3 = QLabel("—")
                sep3.setStyleSheet("color: #888888;")
                row.addWidget(sep3)

                def_label = QLabel(vh.definition)
                def_label.setStyleSheet("font-size: 12px; color: #555555;")
                def_label.setWordWrap(True)
                row.addWidget(def_label)

            row.addStretch()
            layout.addLayout(row)

        return group

    def _build_grammar_group(self) -> QGroupBox:
        group = QGroupBox("Grammar")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        for gh in self._grammar_hits:
            row = QHBoxLayout()
            row.setSpacing(8)

            row.addWidget(_make_jlpt_badge(gh.jlpt_level))

            pattern_label = QLabel(gh.pattern)
            pattern_label.setStyleSheet("font-weight: bold; font-size: 13px;")
            row.addWidget(pattern_label)

            if gh.description:
                sep = QLabel("—")
                sep.setStyleSheet("color: #888888;")
                row.addWidget(sep)

                desc_label = QLabel(gh.description)
                desc_label.setStyleSheet("font-size: 12px; color: #555555;")
                desc_label.setWordWrap(True)
                row.addWidget(desc_label)

            row.addStretch()
            layout.addLayout(row)

        return group
