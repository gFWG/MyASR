import json

import pytest

from src.analysis.grammar import GrammarMatcher

RULES_PATH = "data/grammar_rules.json"


def test_grammar_matcher_loads_rules() -> None:
    gm = GrammarMatcher(RULES_PATH)
    assert len(gm._rules) > 0


def test_grammar_matcher_rule_count_matches_json() -> None:
    gm = GrammarMatcher(RULES_PATH)
    rules = json.load(open(RULES_PATH))
    assert len(gm._rules) == len(rules)


def test_match_nagara_pattern() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match("音楽を聴きながら勉強した", user_level=5)
    rule_ids = [h.rule_id for h in hits]
    assert "N3_nagara" in rule_ids


def test_match_tame_ni_pattern() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match("日本語を学ぶために毎日練習する", user_level=5)
    rule_ids = [h.rule_id for h in hits]
    assert "N3_tame_ni" in rule_ids


def test_match_ni_totte_n2_pattern() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match("私にとって大切なことだ", user_level=5)
    rule_ids = [h.rule_id for h in hits]
    assert "N2_ni_totte" in rule_ids


def test_match_user_level_1_no_hits() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match("音楽を聴きながら勉強した", user_level=1)
    assert len(hits) == 0


def test_match_user_level_3_excludes_n3() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match("音楽を聴きながら勉強した", user_level=3)
    rule_ids = [h.rule_id for h in hits]
    assert "N3_nagara" not in rule_ids


def test_match_user_level_4_includes_n3() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match("日本語を学ぶために毎日練習する", user_level=4)
    rule_ids = [h.rule_id for h in hits]
    assert "N3_tame_ni" in rule_ids


def test_match_returns_correct_fields() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match("私にとって大切なことだ", user_level=5)
    assert len(hits) >= 1
    for h in hits:
        assert h.rule_id
        assert h.matched_text
        assert 1 <= h.jlpt_level <= 5
        assert h.confidence_type in ("high", "ambiguous")
        assert h.description


def test_match_empty_text_returns_empty() -> None:
    gm = GrammarMatcher(RULES_PATH)
    assert gm.match("", user_level=5) == []


def test_match_non_japanese_returns_empty() -> None:
    gm = GrammarMatcher(RULES_PATH)
    assert gm.match("hello world", user_level=5) == []


def test_match_matched_text_is_actual_substring() -> None:
    gm = GrammarMatcher(RULES_PATH)
    text = "音楽を聴きながら勉強した"
    hits = gm.match(text, user_level=5)
    nagara_hits = [h for h in hits if h.rule_id == "N3_nagara"]
    assert len(nagara_hits) >= 1
    assert nagara_hits[0].matched_text in text


def test_match_confidence_type_propagated() -> None:
    gm = GrammarMatcher(RULES_PATH)
    hits = gm.match("私にとって大切なことだ", user_level=5)
    ni_totte_hits = [h for h in hits if h.rule_id == "N2_ni_totte"]
    assert len(ni_totte_hits) >= 1
    assert ni_totte_hits[0].confidence_type == "high"


def test_grammar_matcher_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        GrammarMatcher("/nonexistent/path/rules.json")


def test_grammar_hit_positions_are_correct() -> None:
    """Verify start_pos and end_pos correctly identify matched text substring."""
    gm = GrammarMatcher(RULES_PATH)
    text = "音楽を聴きながら勉強した"
    hits = gm.match(text, user_level=5)
    nagara_hits = [h for h in hits if h.rule_id == "N3_nagara"]
    assert len(nagara_hits) >= 1
    hit = nagara_hits[0]
    # Assert positions correctly identify the matched substring
    assert text[hit.start_pos : hit.end_pos] == hit.matched_text
    # Verify positions are non-negative and ordered
    assert 0 <= hit.start_pos < hit.end_pos <= len(text)
