"""TDD tests for GrammarMatcher._resolve_overlaps() — RED phase.

Algorithm contract:
1. Zero-length hits (end_pos <= start_pos) filtered out.
2. Short hits (end_pos - start_pos < 2) filtered out (_MIN_MATCH_LEN = 2).
3. Sort key: (length DESC, start_pos ASC, jlpt_level ASC).
4. Greedy interval selection; strict overlap = start_a < end_b AND start_b < end_a.
5. Output sorted by start_pos ascending.

All tests MUST FAIL until _resolve_overlaps() is implemented (Task 3).
Task 1 validated: _MIN_MATCH_LEN = 2 is safe — only N4/N5 particle noise suppressed.
"""

import pytest

from src.analysis.grammar import GrammarMatcher
from src.models import GrammarHit

RULES_PATH = "data/grammar.json"


def _make_hit(
    start: int,
    end: int,
    jlpt: int = 5,
    rule_id: str = "test",
    word: str = "test",
    matched_parts: tuple[tuple[int, int], ...] = (),
) -> GrammarHit:
    return GrammarHit(
        rule_id=rule_id,
        matched_text="x" * (end - start),
        word=word,
        jlpt_level=jlpt,
        description="test rule",
        start_pos=start,
        end_pos=end,
        matched_parts=matched_parts,
    )


@pytest.fixture(scope="module")
def gm() -> GrammarMatcher:
    return GrammarMatcher(RULES_PATH)


RESOLVE_CASES: list[tuple[str, list[GrammarHit], list[tuple[int, int]]]] = [
    ("empty", [], []),
    ("single_hit", [_make_hit(0, 5)], [(0, 5)]),
    ("two_non_overlapping", [_make_hit(0, 3), _make_hit(5, 8)], [(0, 3), (5, 8)]),
    # [0,5) length=5 beats [2,4) length=2
    ("two_overlapping_longer_wins", [_make_hit(0, 5), _make_hit(2, 4)], [(0, 5)]),
    # [0,6) length=6 beats [2,5) length=3 regardless of input order
    ("longer_wins_input_order", [_make_hit(2, 5), _make_hit(0, 6)], [(0, 6)]),
    # [1,4) and [2,5) both length=3; start=1 < start=2 → [1,4) wins
    ("same_length_earlier_start_wins", [_make_hit(1, 4), _make_hit(2, 5)], [(1, 4)]),
    # jlpt=2 (N2, harder) beats jlpt=5 (N5) on identical span
    (
        "identical_span_lower_jlpt_wins",
        [_make_hit(0, 3, jlpt=5), _make_hit(0, 3, jlpt=2)],
        [(0, 3)],
    ),
    # [0,3) end=3, [3,6) start=3: strict 3<3=False → NOT overlapping
    ("adjacent_spans_both_preserved", [_make_hit(0, 3), _make_hit(3, 6)], [(0, 3), (3, 6)]),
    # [0,5)[3,8)[6,11) all len=5; greedy: keep [0,5), [3,8) overlaps, [6,11) clear → keep
    (
        "three_hits_first_third_kept",
        [_make_hit(0, 5), _make_hit(3, 8), _make_hit(6, 11)],
        [(0, 5), (6, 11)],
    ),
    # end-start=1 < _MIN_MATCH_LEN(2) → filtered
    ("min_length_filtered", [_make_hit(0, 1)], []),
    # end-start=0 (zero-length) → filtered
    ("zero_length_filtered", [_make_hit(3, 3)], []),
    ("matched_parts_preserved", [_make_hit(0, 5, matched_parts=((1, 3),))], [(0, 5)]),
    (
        "same_rule_id_non_overlapping",
        [_make_hit(0, 3, rule_id="r1"), _make_hit(5, 8, rule_id="r1")],
        [(0, 3), (5, 8)],
    ),
    # Reversed input → output sorted by start_pos ascending
    ("output_sorted_by_start_pos", [_make_hit(5, 8), _make_hit(0, 3)], [(0, 3), (5, 8)]),
    # [0,4) same length as [2,6) but earlier start → wins
    ("hit_at_start_pos_zero", [_make_hit(0, 4), _make_hit(2, 6)], [(0, 4)]),
]


@pytest.mark.parametrize(
    "case_id,input_hits,expected_spans",
    RESOLVE_CASES,
    ids=[c[0] for c in RESOLVE_CASES],
)
def test_resolve_overlaps_unit(
    gm: GrammarMatcher,
    case_id: str,
    input_hits: list[GrammarHit],
    expected_spans: list[tuple[int, int]],
) -> None:
    result = gm._resolve_overlaps(input_hits)  # type: ignore[attr-defined]
    actual = [(h.start_pos, h.end_pos) for h in result]
    assert actual == expected_spans, f"[{case_id}] got {actual}, want {expected_spans}"


def test_resolve_overlaps_matched_parts_content(gm: GrammarMatcher) -> None:
    parts = ((1, 3), (4, 6))
    result = gm._resolve_overlaps([_make_hit(0, 8, matched_parts=parts)])  # type: ignore[attr-defined]
    assert len(result) == 1
    assert result[0].matched_parts == parts


def test_resolve_overlaps_identical_span_winner_attributes(gm: GrammarMatcher) -> None:
    harder = _make_hit(0, 5, jlpt=2, rule_id="hard", word="hard_word")
    easier = _make_hit(0, 5, jlpt=5, rule_id="easy", word="easy_word")
    result = gm._resolve_overlaps([easier, harder])  # type: ignore[attr-defined]
    assert len(result) == 1
    assert result[0].jlpt_level == 2
    assert result[0].rule_id == "hard"


def test_resolve_overlaps_min_length_boundary(gm: GrammarMatcher) -> None:
    result = gm._resolve_overlaps([_make_hit(0, 2), _make_hit(5, 6)])  # type: ignore[attr-defined]
    spans = [(h.start_pos, h.end_pos) for h in result]
    assert (0, 2) in spans
    assert (5, 6) not in spans


def test_integration_koto_ni_suru_one_hit(gm: GrammarMatcher) -> None:
    hits = gm.match_all("ことにする")
    assert len(hits) == 1, (
        f"ことにする: expected 1 hit, got {len(hits)}: "
        f"{[(h.word, h.start_pos, h.end_pos) for h in hits]}"
    )


def test_integration_tekara_double_occurrence(gm: GrammarMatcher) -> None:
    sentence = "食べてから寝てから起きる"
    hits = gm.match_all(sentence)
    tekara_hits = [h for h in hits if h.matched_text == "てから"]
    assert len(tekara_hits) == 2, (
        f"Expected 2 てから hits in {sentence!r}, got {len(tekara_hits)}: "
        f"{[(h.word, h.matched_text, h.start_pos, h.end_pos) for h in hits]}"
    )


def test_integration_wake_dewa_nai_one_hit(gm: GrammarMatcher) -> None:
    hits = gm.match_all("わけではない")
    assert len(hits) == 1, (
        f"わけではない: expected 1 hit, got {len(hits)}: "
        f"{[(h.word, h.start_pos, h.end_pos) for h in hits]}"
    )


def test_integration_empty_string(gm: GrammarMatcher) -> None:
    assert gm.match_all("") == []


def test_integration_no_overlaps_in_output(gm: GrammarMatcher) -> None:
    sentences = [
        "ことにする",
        "わけではない",
        "食べてから寝てから起きる",
        "上手になるように練習している",
        "日本語を勉強しなければならないと思います",
    ]
    for sentence in sentences:
        hits = sorted(gm.match_all(sentence), key=lambda h: h.start_pos)
        for i in range(len(hits) - 1):
            a, b = hits[i], hits[i + 1]
            assert not (a.start_pos < b.end_pos and b.start_pos < a.end_pos), (
                f"Overlap in {sentence!r}: "
                f"{a.word!r}[{a.start_pos},{a.end_pos}) vs "
                f"{b.word!r}[{b.start_pos},{b.end_pos})"
            )
