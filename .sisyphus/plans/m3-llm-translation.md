# Milestone 3 — LLM Translation

## TL;DR

> **Quick Summary**: Implement OllamaClient for Japanese→Chinese translation via local Ollama REST API, then integrate it into the existing PipelineWorker to produce complete SentenceResults with translation + study-point analysis.
> 
> **Deliverables**:
> - `src/llm/ollama_client.py` — OllamaClient with prompt templates, response parsing, timeout/fallback
> - `tests/test_ollama_client.py` — Full test suite with mocked HTTP responses
> - `src/pipeline.py` (updated) — LLM stage + DB write integrated into PipelineWorker
> - `tests/test_pipeline.py` (updated) — Updated + new tests for LLM integration and DB writes
> 
> **Estimated Effort**: Short (2 tasks, ~4 files touched)
> **Parallel Execution**: YES — 2 waves (Task 3.1 standalone, then Task 3.2 depends on it)
> **Critical Path**: Task 3.1 → Task 3.2 → Final Verification

---

## Context

### Original Request
Complete all tasks under Milestone 3 (LLM Translation) as defined in `docs/tasks.md`. This adds Ollama-powered Japanese→Chinese translation to the audio processing pipeline.

### Research Findings
- **Ollama REST API**: POST `/api/generate` with `{"model": "qwen3.5:4b", "prompt": "...", "stream": false}`. Response has `"response"` field with text. Health check via GET `/api/tags`.
- **Pipeline insertion point**: `src/pipeline.py` lines 96-101 currently create SentenceResult with `chinese_translation=None` — exact placeholder for LLM integration.
- **All prerequisites exist**: LLM exceptions, AppConfig fields, `requests` in requirements.txt, empty `src/llm/__init__.py`.
- **DB conversion needed**: `LearningRepository.insert_sentence()` requires `SentenceRecord` + highlight lists — conversion from `SentenceResult` + `AnalysisResult` is non-trivial.
- **Test patterns**: `@patch("src.pipeline.X")` stacking, `MagicMock` config, `_make_*()` helpers.

### Metis Review
**Identified Gaps** (all addressed in plan):
- `vocab_hits_formatted` / `grammar_hits_formatted` string format undefined → Defined concrete format below
- SentenceResult → SentenceRecord + Highlights conversion underspecified → Added `_to_db_records()` helper requirement
- `_make_config()` in tests needs expansion for Ollama/DB fields → Explicitly required in Task 3.2
- DB connection lifecycle in PipelineWorker → Decision: accept optional `sqlite3.Connection | None` parameter
- `_parse_response` edge cases → 6 specific test cases required
- Existing tests need `@patch("src.pipeline.OllamaClient")` added → All existing tests must be updated

---

## Work Objectives

### Core Objective
Add LLM-powered Japanese→Chinese translation to the pipeline, with intelligent branching (simple → translation only, complex → translation + study points) and graceful fallback when Ollama is unavailable.

### Concrete Deliverables
- `src/llm/ollama_client.py` — New file: OllamaClient class
- `tests/test_ollama_client.py` — New file: 11+ test cases
- `src/pipeline.py` — Updated: LLM call + DB write in PipelineWorker
- `tests/test_pipeline.py` — Updated: 5 existing tests modified + 4 new tests

### Definition of Done
- [ ] `pytest tests/test_ollama_client.py -x --tb=short` → all pass
- [ ] `pytest tests/test_pipeline.py -x --tb=short` → all pass (existing + new)
- [ ] `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short` → clean

### Must Have
- OllamaClient sends correct prompts for simple vs complex sentences
- Response parsing handles both marker-based and fallback parsing
- LLM failure returns `(None, None)` — no crash, no retry
- Pipeline emits SentenceResult with translation populated on success
- Pipeline emits SentenceResult with `chinese_translation=None` on LLM failure (subtitle-only fallback)
- DB records written via LearningRepository after each sentence
- DB write failure doesn't crash the pipeline

### Must NOT Have (Guardrails)
- **No retry logic** — spec explicitly says "no queuing or retry"
- **No streaming** — use `"stream": false` for simplicity
- **No caching or batching** — not in spec
- **No health_check in pipeline run loop** — health_check is for UI status, not pipeline flow
- **No changes to SentenceResult or SentenceRecord dataclasses** — use existing models as-is
- **No changes to the signal interface** — `sentence_ready` still emits `SentenceResult`
- **No ollama-python library** — use raw `requests` HTTP client
- **No over-commenting or excessive docstrings** — Google-style docstrings for public methods only

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, conftest.py, 12+ existing test files)
- **Automated tests**: YES (Tests-with-implementation — each task includes its test file)
- **Framework**: pytest with `@patch` mocking, `MagicMock` for config/models

### QA Policy
Every task includes agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Module/Library**: Use Bash (python -c) — Import, call functions, verify behavior
- **Tests**: Use Bash (pytest) — Run test suite, verify all pass
- **Lint/Type**: Use Bash (ruff, mypy) — Verify clean output

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — standalone module):
└── Task 1: Implement OllamaClient + tests [unspecified-high]

Wave 2 (After Wave 1 — integration):
└── Task 2: Integrate LLM into pipeline + update tests [deep]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 2 → F1-F4
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | None | 2, F1-F4 | 1 |
| 2 | 1 | F1-F4 | 2 |
| F1-F4 | 1, 2 | None | FINAL |

### Agent Dispatch Summary

- **Wave 1**: 1 task — T1 → `unspecified-high`
- **Wave 2**: 1 task — T2 → `deep`
- **FINAL**: 4 tasks — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. Implement OllamaClient with prompt templates, response parsing, and error handling

  **What to do**:
  - Create `src/llm/ollama_client.py` with class `OllamaClient`
  - **`__init__(self, config: AppConfig) -> None`**: Store `config.ollama_url`, `config.ollama_model`, `config.ollama_timeout_sec`. Create `logger = logging.getLogger(__name__)`.
  - **`translate(self, japanese_text: str, analysis: AnalysisResult) -> tuple[str | None, str | None]`**:
    - Call `_build_prompt()` to construct prompt based on `analysis.is_complex`
    - POST to `{ollama_url}/api/generate` with JSON body: `{"model": self._model, "prompt": prompt, "stream": false, "options": {"temperature": 0.3, "num_predict": 512}}`
    - Use `timeout=self._timeout` on the `requests.post()` call
    - On success: `response.raise_for_status()`, extract `response.json()["response"]`, call `_parse_response()`
    - On `requests.exceptions.Timeout`: log warning, return `(None, None)`
    - On `requests.exceptions.ConnectionError`: log warning, return `(None, None)`
    - On any other `requests.exceptions.RequestException` or `KeyError`/`ValueError` during parsing: log error, return `(None, None)`
  - **`_build_prompt(self, japanese_text: str, analysis: AnalysisResult) -> str`**:
    - If `analysis.is_complex` is False, use simple template:
      ```
      あなたは日本語の翻訳者です。次の日本語を中国語に翻訳してください。翻訳のみを出力し、他の内容は出力しないでください。

      日本語：{japanese_text}
      ```
    - If `analysis.is_complex` is True, use complex template:
      ```
      あなたは日本語教師です。次の日本語を中国語に翻訳し、学習者向けの考点解析を提供してください。

      日本語：{japanese_text}

      前処理結果：
      - 超纲词汇：{vocab_hits_formatted}
      - 命中语法：{grammar_hits_formatted}

      以下の形式で回答してください：
      翻訳：<中国語翻訳>
      解析：<考点解析（超纲词汇・語法の説明を含む）>
      ```
    - **Formatting rules** (from Metis review):
      - `vocab_hits_formatted`: Join VocabHits as `"{surface}({lemma}, N{jlpt_level})"` separated by `"、"`. Example: `"猫(ねこ, N3)、概念(がいねん, N1)"`
      - `grammar_hits_formatted`: Join GrammarHits as `"{matched_text}(N{jlpt_level}, {description})"` separated by `"、"`. Example: `"～にとって(N2, ...にとって)、～ざるを得ない(N1, 不得不...)"`
      - If no hits for either, use `"なし"`
  - **`_parse_response(self, response_text: str, is_complex: bool) -> tuple[str, str | None]`**:
    - If `is_complex` is False: return `(response_text.strip(), None)`
    - If `is_complex` is True:
      - Try to split on `"翻訳："` and `"解析："` markers
      - If both markers found: extract translation (text between 翻訳： and 解析：) and explanation (text after 解析：), strip both
      - If only `"翻訳："` found but no `"解析："`: extract translation after marker, explanation = None
      - If no markers found (fallback): return `(response_text.strip(), None)` — treat whole response as translation
      - If response_text is empty or whitespace-only: return `("", None)`
  - **`health_check(self) -> bool`**:
    - GET `{ollama_url}/api/tags` with `timeout=5`
    - Return `True` if status 200, `False` on any exception
  - Create `tests/test_ollama_client.py` with these test cases (use `@patch("src.llm.ollama_client.requests")` or `@patch("requests.post")`/`@patch("requests.get")`):
    1. `test_translate_simple_returns_translation_only` — mock POST returning `{"response": "这是测试翻译"}`, pass `is_complex=False` AnalysisResult, assert returns `("这是测试翻译", None)`
    2. `test_translate_complex_returns_translation_and_explanation` — mock POST returning `{"response": "翻訳：复杂句子的翻译\n解析：这里使用了N1语法..."}`, pass `is_complex=True` AnalysisResult, assert returns `("复杂句子的翻译", "这里使用了N1语法...")`
    3. `test_translate_returns_none_tuple_on_timeout` — mock POST raising `requests.exceptions.Timeout`, assert returns `(None, None)`
    4. `test_translate_returns_none_tuple_on_connection_error` — mock POST raising `requests.exceptions.ConnectionError`, assert returns `(None, None)`
    5. `test_build_prompt_simple_uses_simple_template` — call `_build_prompt` with `is_complex=False` AnalysisResult, assert output contains `"翻訳のみを出力"` and `japanese_text`
    6. `test_build_prompt_complex_includes_formatted_hits` — create AnalysisResult with VocabHit(surface="概念", lemma="がいねん", ...) and GrammarHit(matched_text="～にとって", ...), call `_build_prompt`, assert output contains formatted strings
    7. `test_parse_response_complex_with_both_markers` — input `"翻訳：翻译结果\n解析：语法解析"`, assert returns `("翻译结果", "语法解析")`
    8. `test_parse_response_complex_with_only_translation_marker` — input `"翻訳：只有翻译没有解析"`, assert returns `("只有翻译没有解析", None)`
    9. `test_parse_response_complex_without_markers_fallback` — input `"直接的翻译文本"`, assert returns `("直接的翻译文本", None)`
    10. `test_parse_response_empty_string` — input `""`, assert returns `("", None)`
    11. `test_health_check_true_when_reachable` — mock GET returning 200, assert returns `True`
    12. `test_health_check_false_when_unreachable` — mock GET raising `ConnectionError`, assert returns `False`
  - Follow project import style: `import logging`, `import requests`, `from src.config import AppConfig`, `from src.db.models import AnalysisResult, VocabHit, GrammarHit`, `from src.exceptions import LLMError, LLMTimeoutError, LLMUnavailableError`
  - Use `logger = logging.getLogger(__name__)` with lazy formatting (`logger.warning("Ollama timeout after %ss", self._timeout)`)

  **Must NOT do**:
  - No retry logic, no queuing, no caching, no batching
  - No streaming (`stream: false` always)
  - No `ollama` Python library — use raw `requests`
  - No `print()` — use `logging` only
  - No over-commenting. Google-style docstrings for public methods only.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Scoped module with clear API contract, HTTP client patterns, substantial test suite — not trivial but not architecturally complex
  - **Skills**: `[]`
    - No special skills needed — standard Python HTTP client implementation
  - **Skills Evaluated but Omitted**:
    - `playwright`: Not relevant — no browser interaction

  **Parallelization**:
  - **Can Run In Parallel**: NO (Wave 1, only task)
  - **Parallel Group**: Wave 1 (standalone)
  - **Blocks**: Task 2, F1-F4
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL — executor has NO context from this interview):

  **Pattern References** (existing code to follow):
  - `src/analysis/pipeline.py` — Similar module structure: class with `__init__(config)`, processing methods, logging pattern
  - `src/asr/qwen_asr.py` — Error handling pattern: catch specific exceptions, log, re-raise custom exceptions
  - `tests/test_qwen_asr.py` — Test pattern for mocking external services

  **API/Type References** (contracts to implement against):
  - `src/db/models.py:72-86` — `AnalysisResult` (line 72: fields: tokens, vocab_hits, grammar_hits, complexity_score, is_complex), `VocabHit` (line 54: surface, lemma, pos, jlpt_level, user_level), `GrammarHit` (line 63: rule_id, matched_text, jlpt_level, confidence_type, description), `SentenceResult` (line 81: japanese_text, chinese_translation, explanation, analysis, created_at)
  - `src/config.py:20-22` — `AppConfig.ollama_url` (str, default `"http://localhost:11434"`), `AppConfig.ollama_model` (str, default `"qwen3.5:4b"`), `AppConfig.ollama_timeout_sec` (float, default `30.0`)
  - `src/exceptions.py:28-36` — `LLMError(MyASRError)` line 28, `LLMTimeoutError(LLMError)` line 32, `LLMUnavailableError(LLMError)` line 36

  **External References** (libraries and frameworks):
  - Ollama REST API: POST `/api/generate` with `{"model": "...", "prompt": "...", "stream": false, "options": {"temperature": 0.3, "num_predict": 512}}`. Response: `{"response": "<text>", "done": true}`. Health: GET `/api/tags` returns 200.
  - `requests` library: `requests.post(url, json=body, timeout=sec)`, `requests.get(url, timeout=sec)`, exceptions: `requests.exceptions.Timeout`, `requests.exceptions.ConnectionError`, `requests.exceptions.RequestException`

  **Spec References** (prompt templates and parsing rules):
  - `docs/api-data.md` — Contains exact prompt templates (simple: lines ~100-105, complex: lines ~107-120), request JSON format, response parsing rules (split on `翻訳：`/`解析：` markers)
  - `docs/architecture.md` — LLM branching logic: simple→translate only, complex→translate+analysis, unavailable→subtitle-only fallback. "No queuing or retry" rule.

  **WHY Each Reference Matters**:
  - `src/db/models.py` — You need exact field names for AnalysisResult/VocabHit/GrammarHit to build prompts and access `is_complex`
  - `src/config.py` — You need exact attribute names for AppConfig to initialize the client
  - `src/exceptions.py` — You must import and use these exact exception classes, not create new ones
  - `docs/api-data.md` — Contains the verbatim prompt templates to implement as string constants
  - `docs/architecture.md` — Defines the fallback behavior rules you must follow

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: OllamaClient module imports cleanly and mypy passes
    Tool: Bash
    Preconditions: src/llm/ollama_client.py created
    Steps:
      1. Run: python -c "from src.llm.ollama_client import OllamaClient; print('OK')"
      2. Run: mypy src/llm/ollama_client.py --no-error-summary
      3. Run: ruff check src/llm/ollama_client.py
      4. Run: ruff format --check src/llm/ollama_client.py
    Expected Result: All 4 commands exit 0, "OK" printed for step 1
    Failure Indicators: ImportError, mypy errors, ruff violations
    Evidence: .sisyphus/evidence/task-1-import-and-lint.txt

  Scenario: All 12 OllamaClient tests pass
    Tool: Bash
    Preconditions: tests/test_ollama_client.py created with all test cases
    Steps:
      1. Run: pytest tests/test_ollama_client.py -v --tb=short 2>&1
      2. Verify output contains "12 passed" (or more)
      3. Verify no warnings about unclosed resources
    Expected Result: All tests pass, 0 failures, 0 errors
    Failure Indicators: Any FAILED or ERROR in output
    Evidence: .sisyphus/evidence/task-1-tests.txt

  Scenario: OllamaClient gracefully handles unavailable server
    Tool: Bash
    Preconditions: Ollama is NOT running (or use a wrong port)
    Steps:
      1. Run: python -c "
         from src.llm.ollama_client import OllamaClient
         from src.config import AppConfig
         cfg = AppConfig(ollama_url='http://localhost:99999')
         client = OllamaClient(cfg)
         result = client.translate('テスト', __import__('src.db.models', fromlist=['AnalysisResult']).AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[], complexity_score=0.0, is_complex=False))
         assert result == (None, None), f'Expected (None, None), got {result}'
         print('Graceful fallback OK')
         "
    Expected Result: Prints "Graceful fallback OK", no exception raised
    Failure Indicators: Unhandled exception, crash, non-(None, None) return
    Evidence: .sisyphus/evidence/task-1-fallback.txt
  ```

  **Evidence to Capture:**
  - [ ] `task-1-import-and-lint.txt` — Import + mypy + ruff output
  - [ ] `task-1-tests.txt` — Full pytest output
  - [ ] `task-1-fallback.txt` — Graceful fallback verification

  **Commit**: YES
  - Message: `feat(llm): implement OllamaClient with prompt templates and response parsing`
  - Files: `src/llm/ollama_client.py`, `tests/test_ollama_client.py`
  - Pre-commit: `pytest tests/test_ollama_client.py -x && mypy src/llm/ollama_client.py`

- [ ] 2. Integrate LLM translation and DB writes into PipelineWorker

  **What to do**:
  - **Update `src/pipeline.py`**:
    - Add imports: `from src.llm.ollama_client import OllamaClient`, `from src.db.schema import init_db`, `from src.db.repository import LearningRepository`, `from src.db.models import SentenceRecord, HighlightVocab, HighlightGrammar`, `import sqlite3`
    - Update `PipelineWorker.__init__` signature to accept optional DB connection: `def __init__(self, config: AppConfig, db_conn: sqlite3.Connection | None = None, parent: Any = None) -> None`
    - In `__init__`: create `self._llm = OllamaClient(config)`. If `db_conn` is not None, create `self._repo = LearningRepository(db_conn)`, else `self._repo = None`.
    - In `run()`, after `analysis = self._preprocessing.process(text)` (around line 90), insert LLM call:
      ```python
      translation, explanation = self._llm.translate(text, analysis)
      ```
    - Update SentenceResult creation (lines 96-101) to use the LLM results:
      ```python
      result = SentenceResult(
          japanese_text=text,
          chinese_translation=translation,
          explanation=explanation,
          analysis=analysis,
      )
      ```
    - After `self.sentence_ready.emit(result)`, add DB write:
      ```python
      if self._repo is not None:
          try:
              record, vocab_highlights, grammar_highlights = self._to_db_records(result)
              self._repo.insert_sentence(record, vocab_highlights, grammar_highlights)
          except Exception:
              logger.exception("Failed to write sentence to database")
      ```
    - **Add `_to_db_records` helper method**:
      ```python
      def _to_db_records(self, result: SentenceResult) -> tuple[SentenceRecord, list[HighlightVocab], list[HighlightGrammar]]:
      ```
      - Convert `SentenceResult` → `SentenceRecord`:
        - `id=None` (pre-insert)
        - `japanese_text=result.japanese_text`
        - `chinese_translation=result.chinese_translation`
        - `explanation=result.explanation`
        - `complexity_score=result.analysis.complexity_score`
        - `is_complex=result.analysis.is_complex`
        - `source_context=None`
        - `created_at=result.created_at.isoformat()`
      - Convert `list[VocabHit]` → `list[HighlightVocab]`:
        - For each `vh` in `result.analysis.vocab_hits`: `HighlightVocab(id=None, sentence_id=0, surface=vh.surface, lemma=vh.lemma, pos=vh.pos, jlpt_level=vh.jlpt_level, is_beyond_level=True, tooltip_shown=False)`
      - Convert `list[GrammarHit]` → `list[HighlightGrammar]`:
        - For each `gh` in `result.analysis.grammar_hits`: `HighlightGrammar(id=None, sentence_id=0, rule_id=gh.rule_id, pattern=gh.matched_text, jlpt_level=gh.jlpt_level, confidence_type=gh.confidence_type, description=gh.description, is_beyond_level=True, tooltip_shown=False)`
      - `sentence_id=0` is a placeholder — `LearningRepository.insert_sentence()` uses `cursor.lastrowid` internally
  - **Update `tests/test_pipeline.py`**:
    - Add `@patch("src.pipeline.OllamaClient")` to ALL 5 existing test functions. In each, configure mock: `mock_llm_cls.return_value.translate.return_value = (None, None)` (default: LLM returns nothing, preserving existing behavior)
    - Update `_make_config()` helper to explicitly set: `cfg.ollama_url = "http://localhost:11434"`, `cfg.ollama_model = "qwen3.5:4b"`, `cfg.ollama_timeout_sec = 30.0`, `cfg.db_path = ":memory:"`, `cfg.user_jlpt_level = 3`
    - Add new test: `test_pipeline_populates_translation_on_llm_success`:
      - Mock OllamaClient.translate returning `("中文翻译", "语法解析")`
      - Process a segment through the pipeline
      - Assert emitted SentenceResult has `chinese_translation="中文翻译"` and `explanation="语法解析"`
    - Add new test: `test_pipeline_emits_with_none_on_llm_failure`:
      - Mock OllamaClient.translate returning `(None, None)`
      - Process a segment
      - Assert emitted SentenceResult has `chinese_translation=None` and `explanation=None`
    - Add new test: `test_pipeline_writes_to_db_on_success`:
      - Create in-memory DB with `init_db(":memory:")`
      - Pass connection to PipelineWorker
      - Mock OllamaClient.translate returning `("翻译", None)`
      - Process a segment
      - Assert `LearningRepository.insert_sentence` was called (or query DB directly)
    - Add new test: `test_pipeline_still_emits_when_db_write_fails`:
      - Mock LearningRepository.insert_sentence raising `Exception("DB error")`
      - Process a segment
      - Assert SentenceResult was still emitted (pipeline didn't crash)
    - Add new test: `test_to_db_records_converts_correctly`:
      - Create a known SentenceResult with populated analysis (VocabHits, GrammarHits)
      - Call `_to_db_records()`
      - Assert SentenceRecord fields match: japanese_text, chinese_translation, complexity_score, is_complex, created_at format
      - Assert HighlightVocab count matches VocabHit count, fields mapped correctly
      - Assert HighlightGrammar count matches GrammarHit count, fields mapped correctly

  **Must NOT do**:
  - No changes to SentenceResult or SentenceRecord dataclasses
  - No changes to the `sentence_ready` signal signature
  - No health_check calls in the pipeline run loop
  - No blocking on DB writes — wrap in try/except, log, continue
  - No changes to audio/VAD/ASR initialization or flow

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Modifying existing pipeline with multiple integration points (LLM, DB, conversion logic), updating 5 existing tests + adding 5 new tests, requires careful understanding of existing signal flow and mock patterns
  - **Skills**: `[]`
    - No special skills needed — Python pipeline integration and pytest
  - **Skills Evaluated but Omitted**:
    - `playwright`: Not relevant — no browser interaction

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (sequential after Wave 1)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 1

  **References** (CRITICAL — executor has NO context from this interview):

  **Pattern References** (existing code to follow):
  - `src/pipeline.py:21-130` — FULL FILE. PipelineWorker class you are modifying. Study the entire flow: `__init__` (line 31), `run()` (line 50, especially lines 85-105 where preprocessing→SentenceResult happens), `stop()` (line 108), `_cleanup()` (line 117). The LLM call inserts between line 90 (preprocessing) and line 96 (SentenceResult creation).
  - `src/pipeline.py:85-105` — CRITICAL SECTION. Current flow: `text = self._asr.transcribe(segment.samples)` → `analysis = self._preprocessing.process(text)` → `result = SentenceResult(japanese_text=text, chinese_translation=None, explanation=None, analysis=analysis)` → `self.sentence_ready.emit(result)`. Your LLM call goes between preprocessing and SentenceResult.
  - `tests/test_pipeline.py:1-260` — FULL FILE. All 5 existing tests and helper functions. You must add `@patch("src.pipeline.OllamaClient")` to each. Study the `_make_config()`, `_make_analysis_result()`, `_make_audio_segment()` helpers and the signal capture pattern.

  **API/Type References** (contracts to implement against):
  - `src/db/models.py:10-45` — `SentenceRecord` dataclass (id, japanese_text, chinese_translation, explanation, complexity_score, is_complex, source_context, created_at). Used for DB writes.
  - `src/db/models.py:46-86` — `HighlightVocab` and `HighlightGrammar` dataclasses. Needed for `_to_db_records()` conversion.
  - `src/db/models.py:72-86` — `AnalysisResult` and `SentenceResult`. Your LLM results populate SentenceResult fields.
  - `src/db/repository.py:24` — `LearningRepository.insert_sentence(record: SentenceRecord, vocab: list[HighlightVocab], grammar: list[HighlightGrammar]) -> int`. This is what you call after emit.
  - `src/db/schema.py` — `init_db(db_path: str) -> sqlite3.Connection`. Used to create DB connection for tests.
  - `src/llm/ollama_client.py` (created in Task 1) — `OllamaClient.__init__(config: AppConfig)`, `OllamaClient.translate(japanese_text: str, analysis: AnalysisResult) -> tuple[str | None, str | None]`

  **WHY Each Reference Matters**:
  - `src/pipeline.py` full file — You're modifying this file. You MUST read the entire file to understand the flow before making changes.
  - `tests/test_pipeline.py` full file — You're modifying ALL existing tests. Read every test to understand what mocks exist and how signals are captured.
  - `src/db/models.py` SentenceRecord/HighlightVocab/HighlightGrammar — You need exact field names and types for the `_to_db_records()` conversion. Getting a field name wrong will cause silent data corruption.
  - `src/db/repository.py` insert_sentence — You need the exact signature to call it correctly in the pipeline.

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Updated pipeline module imports cleanly and mypy passes
    Tool: Bash
    Preconditions: src/pipeline.py updated with LLM + DB integration
    Steps:
      1. Run: python -c "from src.pipeline import PipelineWorker; print('OK')"
      2. Run: mypy src/pipeline.py --no-error-summary
      3. Run: ruff check src/pipeline.py
      4. Run: ruff format --check src/pipeline.py
    Expected Result: All 4 commands exit 0
    Failure Indicators: ImportError, mypy errors, ruff violations
    Evidence: .sisyphus/evidence/task-2-import-and-lint.txt

  Scenario: All existing pipeline tests still pass (backward compatibility)
    Tool: Bash
    Preconditions: tests/test_pipeline.py updated with OllamaClient mocks on all tests
    Steps:
      1. Run: pytest tests/test_pipeline.py -v -k "not (llm_success or llm_failure or db_on_success or db_write_fails or to_db_records)" --tb=short 2>&1
      2. Verify all 5 original tests pass
    Expected Result: 5 passed, 0 failed
    Failure Indicators: Any FAILED or ERROR in original tests
    Evidence: .sisyphus/evidence/task-2-existing-tests.txt

  Scenario: All new pipeline tests pass (LLM integration + DB writes)
    Tool: Bash
    Preconditions: New test functions added to tests/test_pipeline.py
    Steps:
      1. Run: pytest tests/test_pipeline.py -v --tb=short 2>&1
      2. Verify output contains at least "10 passed" (5 existing + 5 new)
    Expected Result: All tests pass, 0 failures, 0 errors
    Failure Indicators: Any FAILED or ERROR
    Evidence: .sisyphus/evidence/task-2-all-tests.txt

  Scenario: Full milestone verification passes
    Tool: Bash
    Preconditions: Both Task 1 and Task 2 complete
    Steps:
      1. Run: ruff check . 2>&1
      2. Run: ruff format --check . 2>&1
      3. Run: mypy . 2>&1
      4. Run: pytest -x --tb=short 2>&1
    Expected Result: All 4 commands exit 0, all tests pass
    Failure Indicators: Any lint/type/test failure
    Evidence: .sisyphus/evidence/task-2-full-milestone.txt

  Scenario: Pipeline gracefully handles LLM unavailable (fallback path)
    Tool: Bash
    Preconditions: Pipeline updated, Ollama NOT running
    Steps:
      1. Run: python -c "
         from unittest.mock import MagicMock, patch
         from src.pipeline import PipelineWorker
         from src.config import AppConfig
         from src.db.models import AnalysisResult, AudioSegment, SentenceResult
         import numpy as np
         cfg = AppConfig(ollama_url='http://localhost:99999')
         worker = PipelineWorker(cfg, db_conn=None)
         # Manually test the LLM fallback path
         analysis = AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[], complexity_score=0.0, is_complex=False)
         result = worker._llm.translate('テスト', analysis)
         assert result == (None, None), f'Expected (None, None), got {result}'
         print('Pipeline LLM fallback OK')
         "
    Expected Result: Prints "Pipeline LLM fallback OK", no crash
    Failure Indicators: Unhandled exception
    Evidence: .sisyphus/evidence/task-2-pipeline-fallback.txt
  ```

  **Evidence to Capture:**
  - [ ] `task-2-import-and-lint.txt` — Import + mypy + ruff output
  - [ ] `task-2-existing-tests.txt` — Original 5 tests still passing
  - [ ] `task-2-all-tests.txt` — Full pytest output (10+ tests)
  - [ ] `task-2-full-milestone.txt` — Full milestone verification
  - [ ] `task-2-pipeline-fallback.txt` — LLM fallback verification

  **Commit**: YES
  - Message: `feat(pipeline): integrate LLM translation and DB writes into PipelineWorker`
  - Files: `src/pipeline.py`, `tests/test_pipeline.py`
  - Pre-commit: `pytest tests/test_pipeline.py -x && mypy src/pipeline.py`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read `.sisyphus/plans/m3-llm-translation.md` end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short`. Review `src/llm/ollama_client.py` and changes to `src/pipeline.py` for: `as any`/`@ts-ignore` equivalents (`# type: ignore` without justification), empty `except:`, `print()` instead of `logging`, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic variable names.
  Output: `Ruff [PASS/FAIL] | Mypy [PASS/FAIL] | Pytest [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Execute ALL QA scenarios from Tasks 1 and 2 — follow exact steps, capture evidence. Test cross-task integration: OllamaClient used through pipeline path. Test edge cases: empty string input, very long text, malformed LLM response. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (`git diff`). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task 1 touching Task 2's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Task 1**: `feat(llm): implement OllamaClient with prompt templates and response parsing` — `src/llm/ollama_client.py`, `tests/test_ollama_client.py`; pre-commit: `pytest tests/test_ollama_client.py -x && mypy src/llm/ollama_client.py`
- **Task 2**: `feat(pipeline): integrate LLM translation and DB writes into PipelineWorker` — `src/pipeline.py`, `tests/test_pipeline.py`; pre-commit: `pytest tests/test_pipeline.py -x && mypy src/pipeline.py`

---

## Success Criteria

### Verification Commands
```bash
# Task 3.1 — OllamaClient
pytest tests/test_ollama_client.py -x --tb=short  # Expected: 11+ tests pass

# Task 3.2 — Pipeline integration
pytest tests/test_pipeline.py -x --tb=short  # Expected: 9+ tests pass (5 existing + 4 new)

# Full milestone
ruff check . && ruff format --check . && mypy . && pytest -x --tb=short  # Expected: all clean
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] mypy clean
- [ ] ruff clean
