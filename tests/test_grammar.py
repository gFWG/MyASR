import pytest

from src.analysis.grammar import GrammarMatcher

RULES_PATH = "data/grammar.json"

TEKARA_N5_RULE_ID = "762"
YOUNI_N3_RULE_ID = "460"
TEKARA_SENTENCE = "食べてから寝る"
YOUNI_SENTENCE = "上手になるように練習している"


def test_grammar_matcher_loads_rules() -> None:
    gm = GrammarMatcher(RULES_PATH)
    assert len(gm._rules) == 831


def test_grammar_matcher_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        GrammarMatcher("/nonexistent/path/rules.json")


def test_grammar_hit_fields() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match_all(TEKARA_SENTENCE)
    assert len(hits) >= 1
    for h in hits:
        assert isinstance(h.rule_id, str) and h.rule_id
        assert isinstance(h.word, str) and h.word
        assert isinstance(h.matched_text, str) and h.matched_text
        assert isinstance(h.jlpt_level, int) and 1 <= h.jlpt_level <= 5
        assert isinstance(h.description, str) and h.description
        assert isinstance(h.start_pos, int) and h.start_pos >= 0
        assert isinstance(h.end_pos, int) and h.end_pos > h.start_pos


def test_grammar_hit_word_field_populated() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match_all(TEKARA_SENTENCE)
    tekara_hits = [h for h in hits if h.rule_id == TEKARA_N5_RULE_ID]
    assert len(tekara_hits) >= 1
    assert tekara_hits[0].word == "てから"
    assert tekara_hits[0].jlpt_level == 5


def test_match_tekara_n5() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match_all(TEKARA_SENTENCE)
    assert any(h.rule_id == TEKARA_N5_RULE_ID for h in hits)


def test_match_youni_n3() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match_all(YOUNI_SENTENCE)
    assert any(h.rule_id == YOUNI_N3_RULE_ID for h in hits)


def test_matched_text_is_substring() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match_all(TEKARA_SENTENCE)
    for h in hits:
        assert h.matched_text in TEKARA_SENTENCE


def test_positions_identify_matched_text() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match_all(TEKARA_SENTENCE)
    tekara_hits = [h for h in hits if h.rule_id == TEKARA_N5_RULE_ID]
    assert len(tekara_hits) >= 1
    hit = tekara_hits[0]
    assert TEKARA_SENTENCE[hit.start_pos : hit.end_pos] == hit.matched_text
    assert 0 <= hit.start_pos < hit.end_pos <= len(TEKARA_SENTENCE)


def test_match_all_returns_all_levels() -> None:
    """match_all returns all grammar matches regardless of level."""
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match_all(TEKARA_SENTENCE)
    # Should include N5 rule since match_all returns everything
    assert any(h.rule_id == TEKARA_N5_RULE_ID for h in hits)


def test_match_all_includes_n3_rules() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match_all(YOUNI_SENTENCE)
    assert any(h.rule_id == YOUNI_N3_RULE_ID for h in hits)


def test_match_empty_text_returns_empty() -> None:
    gm = GrammarMatcher(RULES_PATH)
    assert gm.match_all("") == []


def test_match_non_japanese_returns_empty() -> None:
    gm = GrammarMatcher(RULES_PATH)
    assert gm.match_all("hello world") == []
