"""TDD RED phase: failing tests for conjugation chain extension.

When a verb token (動詞) is identified as a VocabHit, the chain extension
algorithm extends the surface form by consuming subsequent 助動詞 tokens and
te-form bridge tokens (て/で surface on 助詞/接続助詞). It conservatively
STOPS at 動詞/非自立可能 (auxiliary verbs like いる, しまう) and non-助動詞
particles (ん, ば, etc.).

These tests define the expected behaviour BEFORE any implementation exists —
all should FAIL until chain extension is added to the pipeline.

Acceptance criteria covered:
    AC4  – 続けさせる produces a single chained VocabHit
    AC5  – 走っています stops conservatively at い/動詞/非自立可能 (surface="走って")
    AC6  – 食べる映画 — chain stops at 映画/名詞 (surface="食べる")
    AC7  – unmatched verb + 助動詞 yields NO phantom VocabHit
    AC10 – pipeline latency < 50ms for a chain sentence (5-iteration avg)
    EC chain tests for 食べられない, 食べてしまう, 食べたんだけど, 食べれば
"""

import time

import pytest

from src.analysis.pipeline import PreprocessingPipeline
from src.models import AnalysisResult


@pytest.fixture(scope="module")
def pipeline() -> PreprocessingPipeline:
    """Shared pipeline instance — expensive to construct, reused across tests."""
    return PreprocessingPipeline()


# ---------------------------------------------------------------------------
# AC4 – 続けさせる full chain
# ---------------------------------------------------------------------------


def test_ac4_tsuzukesaseru_full_chain(pipeline: PreprocessingPipeline) -> None:
    """AC4: 続けさせる must produce a VocabHit with surface='続けさせる', lemma='続ける'."""
    result: AnalysisResult = pipeline.process("続けさせる")
    hit = next((h for h in result.vocab_hits if h.lemma == "続ける"), None)
    assert hit is not None, (
        f"Expected VocabHit with lemma='続ける' but got: "
        f"{[(h.surface, h.lemma) for h in result.vocab_hits]}"
    )
    assert hit.surface == "続けさせる", (
        f"Expected chain surface '続けさせる' but got '{hit.surface}'"
    )


def test_ac4_tsuzukesaseru_span_matches_text(pipeline: PreprocessingPipeline) -> None:
    """AC4: VocabHit positions must span the full chained surface in source text."""
    text = "続けさせる"
    result: AnalysisResult = pipeline.process(text)
    hit = next((h for h in result.vocab_hits if h.lemma == "続ける"), None)
    assert hit is not None, "No VocabHit with lemma='続ける' found"
    assert text[hit.start_pos : hit.end_pos] == "続けさせる", (
        f"text[{hit.start_pos}:{hit.end_pos}] = '{text[hit.start_pos : hit.end_pos]}' "
        f"!= '続けさせる'"
    )


# ---------------------------------------------------------------------------
# AC5 – 走っています conservative stop
# ---------------------------------------------------------------------------


def test_ac5_conservative_hashiteimasu(pipeline: PreprocessingPipeline) -> None:
    """AC5: 走っています must stop at い/動詞/非自立可能; surface='走って', lemma='走る'."""
    result: AnalysisResult = pipeline.process("走っています")
    hit = next((h for h in result.vocab_hits if h.lemma == "走る"), None)
    assert hit is not None, (
        f"Expected VocabHit with lemma='走る' but got: "
        f"{[(h.surface, h.lemma) for h in result.vocab_hits]}"
    )
    assert hit.surface == "走って", (
        f"Expected conservative surface '走って' (stops before い/動詞/非自立可能) "
        f"but got '{hit.surface}'"
    )


# ---------------------------------------------------------------------------
# AC6 – 食べる映画 — no extension past 名詞
# ---------------------------------------------------------------------------


def test_ac6_taberumovie_no_extension(pipeline: PreprocessingPipeline) -> None:
    """AC6: 食べられない映画 — chain extends to '食べられない' then stops at 映画/名詞."""
    result: AnalysisResult = pipeline.process("食べられない映画")
    hit = next((h for h in result.vocab_hits if h.lemma == "食べる"), None)
    assert hit is not None, (
        f"Expected VocabHit with lemma='食べる' in '食べられない映画', got: "
        f"{[(h.surface, h.lemma) for h in result.vocab_hits]}"
    )
    assert hit.surface == "食べられない", (
        f"Expected chain surface '食べられない' (stops before 映画/名詞) but got '{hit.surface}'"
    )


# ---------------------------------------------------------------------------
# AC7 – no phantom VocabHit for unmatched verb + 助動詞
# ---------------------------------------------------------------------------


def test_ac7_unmatched_verb_no_phantom_hit(pipeline: PreprocessingPipeline) -> None:
    """AC7: 歩かせる — 歩く not in vocab → no VocabHit with lemma='歩く' or surface matching."""
    result: AnalysisResult = pipeline.process("歩かせる")
    aruku_hits = [h for h in result.vocab_hits if h.lemma == "歩く"]
    assert len(aruku_hits) == 0, (
        f"No phantom VocabHit expected for 歩かせる (歩く not in N1-N5), "
        f"got: {[(h.surface, h.lemma) for h in aruku_hits]}"
    )


def test_no_vocab_hit_for_unmatched_chain(pipeline: PreprocessingPipeline) -> None:
    """Chain extension must never create a VocabHit when head verb has no vocab entry."""
    result: AnalysisResult = pipeline.process("歩かせる")
    surfaces = [h.surface for h in result.vocab_hits]
    # Neither the base form nor the chained form should appear
    assert "歩かせる" not in surfaces, (
        f"Phantom chain surface '歩かせる' should not appear in vocab_hits: {surfaces}"
    )
    assert "歩か" not in surfaces, (
        f"Phantom surface '歩か' should not appear in vocab_hits: {surfaces}"
    )


# ---------------------------------------------------------------------------
# Chain tests — 食べられない
# ---------------------------------------------------------------------------


def test_taberarenai_three_token_chain(pipeline: PreprocessingPipeline) -> None:
    """食べられない: chain extends via られ/助動詞 + ない/助動詞; surface='食べられない'."""
    result: AnalysisResult = pipeline.process("食べられない")
    hit = next((h for h in result.vocab_hits if h.lemma == "食べる"), None)
    assert hit is not None, (
        f"Expected VocabHit with lemma='食べる' in '食べられない', got: "
        f"{[(h.surface, h.lemma) for h in result.vocab_hits]}"
    )
    assert hit.surface == "食べられない", (
        f"Expected full 3-token chain '食べられない' but got '{hit.surface}'"
    )


# ---------------------------------------------------------------------------
# Chain tests — 食べてしまう (conservative)
# ---------------------------------------------------------------------------


def test_conservative_tabeteshimau(pipeline: PreprocessingPipeline) -> None:
    """食べてしまう: te-form bridge, STOP at しまう/動詞/非自立可能; surface='食べて'."""
    result: AnalysisResult = pipeline.process("食べてしまう")
    hit = next((h for h in result.vocab_hits if h.lemma == "食べる"), None)
    assert hit is not None, (
        f"Expected VocabHit with lemma='食べる' in '食べてしまう', got: "
        f"{[(h.surface, h.lemma) for h in result.vocab_hits]}"
    )
    assert hit.surface == "食べて", (
        f"Expected conservative surface '食べて' (stop before しまう/動詞/非自立可能) "
        f"but got '{hit.surface}'"
    )


# ---------------------------------------------------------------------------
# Chain tests — 食べたんだけど (conservative)
# ---------------------------------------------------------------------------


def test_conservative_tabetandakedo(pipeline: PreprocessingPipeline) -> None:
    """食べたんだけど: chain extends via た/助動詞, stops at ん/助詞/準体助詞; surface='食べた'."""
    result: AnalysisResult = pipeline.process("食べたんだけど")
    hit = next((h for h in result.vocab_hits if h.lemma == "食べる"), None)
    assert hit is not None, (
        f"Expected VocabHit with lemma='食べる' in '食べたんだけど', got: "
        f"{[(h.surface, h.lemma) for h in result.vocab_hits]}"
    )
    assert hit.surface == "食べた", (
        f"Expected chain '食べた' (stops at ん/助詞/準体助詞) but got '{hit.surface}'"
    )


# ---------------------------------------------------------------------------
# Chain tests — 食べれば (conservative: ば/助詞/接続 is not て/で, no extension)
# ---------------------------------------------------------------------------


def test_conservative_tabereba(pipeline: PreprocessingPipeline) -> None:
    """食べれば in context: 続けさせる chain must exist AND 食べれ must not extend past ば."""
    result: AnalysisResult = pipeline.process("食べれば続けさせる")
    tsuzuke_hit = next((h for h in result.vocab_hits if h.lemma == "続ける"), None)
    assert tsuzuke_hit is not None, (
        f"Expected VocabHit with lemma='続ける' in '食べれば続けさせる', got: "
        f"{[(h.surface, h.lemma) for h in result.vocab_hits]}"
    )
    assert tsuzuke_hit.surface == "続けさせる", (
        f"Expected chain surface '続けさせる' but got '{tsuzuke_hit.surface}'"
    )
    tabere_hit = next((h for h in result.vocab_hits if h.lemma == "食べる"), None)
    assert tabere_hit is not None, "Expected VocabHit with lemma='食べる'"
    assert tabere_hit.surface == "食べれ", (
        f"Expected '食べれ' (ば/助詞/接続 not consumed) but got '{tabere_hit.surface}'"
    )


# ---------------------------------------------------------------------------
# Lemma invariant — chain never mutates lemma
# ---------------------------------------------------------------------------


def test_lemma_unchanged_after_chain(pipeline: PreprocessingPipeline) -> None:
    """VocabHit.lemma must remain the base form (続ける) after chain extends surface."""
    result: AnalysisResult = pipeline.process("続けさせる")
    hit = next((h for h in result.vocab_hits if h.lemma == "続ける"), None)
    assert hit is not None, "Expected a VocabHit with lemma='続ける'"
    assert hit.surface == "続けさせる", (
        f"Expected chained surface '続けさせる' (chain extension must have run) "
        f"but got '{hit.surface}'"
    )
    assert hit.lemma == "続ける", (
        f"VocabHit.lemma must stay '続ける' (base form), not '{hit.lemma}'"
    )


# ---------------------------------------------------------------------------
# AC10 – pipeline latency for chain sentence < 50ms avg
# ---------------------------------------------------------------------------


def test_ac10_pipeline_latency(pipeline: PreprocessingPipeline) -> None:
    """AC10: chain extension must produce correct surface AND stay under 50ms avg."""
    text = "続けさせる"
    iterations = 5
    elapsed_ms = []
    last_result: AnalysisResult | None = None
    for _ in range(iterations):
        start = time.perf_counter()
        last_result = pipeline.process(text)
        elapsed_ms.append((time.perf_counter() - start) * 1000)
    assert last_result is not None
    hit = next((h for h in last_result.vocab_hits if h.lemma == "続ける"), None)
    assert hit is not None, "Chain extension must produce VocabHit with lemma='続ける'"
    assert hit.surface == "続けさせる", (
        f"Chain extension must run: expected surface '続けさせる' but got '{hit.surface}'"
    )
    avg_ms = sum(elapsed_ms) / iterations
    assert avg_ms < 50.0, (
        f"Pipeline avg latency {avg_ms:.1f}ms exceeds 50ms limit. "
        f"Per-run: {[f'{ms:.1f}' for ms in elapsed_ms]}"
    )
