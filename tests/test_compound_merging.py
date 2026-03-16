"""TDD RED phase: failing tests for prefix-compound merging.

Compounds like お世辞, お願いします, ご無沙汰 are split into 2-4 tokens by fugashi
but should be merged into a single VocabHit. These tests define the expected
behaviour BEFORE any implementation exists — all should FAIL until compound
merging is added to the pipeline.

Acceptance criteria covered:
    AC1  – お世辞 produces a compound VocabHit (surface == "お世辞")
    AC2  – standalone 世辞 hit suppressed when compound found
    AC3  – ご飯 (already single token) still produces a VocabHit (regression guard)
    AC8  – compound VocabHit carries correct character positions
    AC11 – merged token appears as ONE Token in AnalysisResult.tokens
    EC1  – 4-token compound お願いします merged correctly
    EC3  – duplicate compound "お世辞お世辞" yields two distinct VocabHits
    EC6  – 3-token chained prefix ご無沙汰 merged correctly
"""

import pytest

from src.analysis.pipeline import PreprocessingPipeline
from src.models import AnalysisResult, VocabHit


@pytest.fixture(scope="module")
def pipeline() -> PreprocessingPipeline:
    """Shared pipeline instance — expensive to construct, reused across tests."""
    return PreprocessingPipeline()


# ---------------------------------------------------------------------------
# AC1 – お世辞 compound VocabHit
# ---------------------------------------------------------------------------


def test_ac1_osejji_compound_vocab_hit(pipeline: PreprocessingPipeline) -> None:
    """AC1: お世辞 must appear as a single VocabHit with surface 'お世辞'."""
    result: AnalysisResult = pipeline.process("お世辞を言う")
    surfaces = [h.surface for h in result.vocab_hits]
    assert "お世辞" in surfaces, (
        f"Expected compound surface 'お世辞' in vocab_hits, got: {surfaces}"
    )


def test_ac1_osejji_jlpt_level(pipeline: PreprocessingPipeline) -> None:
    """AC1: Compound VocabHit for お世辞 should be JLPT N1."""
    result: AnalysisResult = pipeline.process("お世辞を言う")
    hits = [h for h in result.vocab_hits if h.surface == "お世辞"]
    assert len(hits) >= 1, "No VocabHit with surface 'お世辞' found"
    assert hits[0].jlpt_level == 1, f"Expected N1 (level=1) but got {hits[0].jlpt_level}"


# ---------------------------------------------------------------------------
# AC2 – standalone 世辞 suppressed when compound found
# ---------------------------------------------------------------------------


def test_ac2_seji_standalone_suppressed(pipeline: PreprocessingPipeline) -> None:
    """AC2: When compound お世辞 is found, standalone 世辞 must NOT appear."""
    result: AnalysisResult = pipeline.process("お世辞を言う")
    standalone_seji = [h for h in result.vocab_hits if h.surface == "世辞"]
    assert len(standalone_seji) == 0, (
        f"Standalone '世辞' should be suppressed but found: {standalone_seji}"
    )


# ---------------------------------------------------------------------------
# AC3 – ご飯 unaffected (regression guard — may already pass in RED phase)
# ---------------------------------------------------------------------------


def test_ac3_gohan_single_token_vocab_hit(pipeline: PreprocessingPipeline) -> None:
    """AC3: ご飯 is already a single fugashi token — must still produce a VocabHit."""
    result: AnalysisResult = pipeline.process("ご飯を食べる")
    surfaces = [h.surface for h in result.vocab_hits]
    assert "ご飯" in surfaces, f"Expected 'ご飯' in vocab_hits, got: {surfaces}"


# ---------------------------------------------------------------------------
# AC8 – correct character positions in compound VocabHit
# ---------------------------------------------------------------------------


def test_ac8_compound_start_end_positions(pipeline: PreprocessingPipeline) -> None:
    """AC8: Compound VocabHit positions must span the full compound in source text."""
    text = "彼はお世辞を言った"
    result: AnalysisResult = pipeline.process(text)
    hits = [h for h in result.vocab_hits if h.surface == "お世辞"]
    assert len(hits) >= 1, (
        f"No VocabHit with surface 'お世辞' in: {[h.surface for h in result.vocab_hits]}"
    )
    hit: VocabHit = hits[0]
    assert hit.start_pos == 2, f"Expected start_pos=2 but got {hit.start_pos}"
    assert hit.end_pos == 5, f"Expected end_pos=5 but got {hit.end_pos}"
    assert text[hit.start_pos : hit.end_pos] == "お世辞", (
        f"text[{hit.start_pos}:{hit.end_pos}] = '{text[hit.start_pos : hit.end_pos]}' != 'お世辞'"
    )


# ---------------------------------------------------------------------------
# AC11 – merged compound appears as ONE Token in result.tokens
# ---------------------------------------------------------------------------


def test_ac11_compound_appears_as_single_token(pipeline: PreprocessingPipeline) -> None:
    """AC11: After merging, お世辞 should appear as exactly one Token in result.tokens."""
    result: AnalysisResult = pipeline.process("お世辞")
    osejji_tokens = [t for t in result.tokens if t.surface == "お世辞"]
    assert len(osejji_tokens) == 1, (
        f"Expected exactly 1 Token with surface 'お世辞', got: "
        f"{[(t.surface, t.pos) for t in result.tokens]}"
    )


def test_ac11_compound_token_pos_uses_content_word(pipeline: PreprocessingPipeline) -> None:
    """AC11: Merged Token.pos should be that of the head content word (名詞 for お世辞)."""
    result: AnalysisResult = pipeline.process("お世辞")
    osejji_tokens = [t for t in result.tokens if t.surface == "お世辞"]
    assert len(osejji_tokens) == 1, "Compound token not found"
    assert osejji_tokens[0].pos == "名詞", (
        f"Expected POS '名詞' (head content word) but got '{osejji_tokens[0].pos}'"
    )


# ---------------------------------------------------------------------------
# EC1 – 4-token compound お願いします
# ---------------------------------------------------------------------------


def test_ec1_onegaishimasu_compound(pipeline: PreprocessingPipeline) -> None:
    """EC1: 4-token compound お願いします must produce a single VocabHit."""
    result: AnalysisResult = pipeline.process("よろしくお願いします")
    surfaces = [h.surface for h in result.vocab_hits]
    assert "お願いします" in surfaces, (
        f"Expected compound 'お願いします' in vocab_hits, got: {surfaces}"
    )


def test_ec1_onegaishimasu_jlpt_level(pipeline: PreprocessingPipeline) -> None:
    """EC1: Compound お願いします VocabHit should be JLPT N1."""
    result: AnalysisResult = pipeline.process("よろしくお願いします")
    hits = [h for h in result.vocab_hits if h.surface == "お願いします"]
    assert len(hits) >= 1, "No VocabHit for お願いします found"
    assert hits[0].jlpt_level == 1, f"Expected N1 but got {hits[0].jlpt_level}"


# ---------------------------------------------------------------------------
# EC3 – duplicate compound "お世辞お世辞" → two distinct VocabHits
# ---------------------------------------------------------------------------


def test_ec3_duplicate_compound_two_hits(pipeline: PreprocessingPipeline) -> None:
    """EC3: Two occurrences of お世辞 in text should yield two distinct VocabHits."""
    text = "お世辞お世辞"
    result: AnalysisResult = pipeline.process(text)
    osejji_hits = [h for h in result.vocab_hits if h.surface == "お世辞"]
    assert len(osejji_hits) == 2, (
        f"Expected 2 VocabHits for 'お世辞' but got {len(osejji_hits)}: "
        f"{[(h.surface, h.start_pos, h.end_pos) for h in osejji_hits]}"
    )


def test_ec3_duplicate_compound_distinct_positions(pipeline: PreprocessingPipeline) -> None:
    """EC3: The two お世辞 hits must have distinct (non-overlapping) positions."""
    text = "お世辞お世辞"
    result: AnalysisResult = pipeline.process(text)
    osejji_hits = [h for h in result.vocab_hits if h.surface == "お世辞"]
    assert len(osejji_hits) == 2, "Need 2 hits to check positions"
    h0, h1 = osejji_hits[0], osejji_hits[1]
    assert h0.start_pos != h1.start_pos, "Both hits have the same start_pos"
    assert h0.end_pos <= h1.start_pos or h1.end_pos <= h0.start_pos, (
        f"Hits overlap: [{h0.start_pos},{h0.end_pos}) and [{h1.start_pos},{h1.end_pos})"
    )


# ---------------------------------------------------------------------------
# EC6 – 3-token chained prefix ご無沙汰
# ---------------------------------------------------------------------------


def test_ec6_gobusata_compound(pipeline: PreprocessingPipeline) -> None:
    """EC6: 3-token chained prefix ご無沙汰 must produce a single VocabHit."""
    result: AnalysisResult = pipeline.process("ご無沙汰しております")
    surfaces = [h.surface for h in result.vocab_hits]
    assert "ご無沙汰" in surfaces, f"Expected compound 'ご無沙汰' in vocab_hits, got: {surfaces}"


def test_ec6_gobusata_jlpt_level(pipeline: PreprocessingPipeline) -> None:
    """EC6: Compound ご無沙汰 VocabHit should be JLPT N1."""
    result: AnalysisResult = pipeline.process("ご無沙汰しております")
    hits = [h for h in result.vocab_hits if h.surface == "ご無沙汰"]
    assert len(hits) >= 1, "No VocabHit for ご無沙汰 found"
    assert hits[0].jlpt_level == 1, f"Expected N1 but got {hits[0].jlpt_level}"
