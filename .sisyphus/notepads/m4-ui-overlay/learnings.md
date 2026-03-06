# Learnings — m4-ui-overlay

## [2026-03-06] Session ses_33c40bd4fffeDaiupOGOk32J6z — Initial Setup

### Project Structure
- Worktree: /home/yuheng/MyASR-m4-ui-overlay (branch: m4-ui-overlay)
- Main repo: /home/yuheng/MyASR
- Python venv: /home/yuheng/MyASR/.venv or similar — use `source .venv/bin/activate`

### Source Layout
src/: __init__.py, analysis/, asr/, audio/, config.py, db/, exceptions.py, llm/, pipeline.py, ui/
src/analysis/: __init__.py, grammar.py, jlpt_vocab.py, pipeline.py, tokenizer.py
src/db/: __init__.py, models.py, repository.py, schema.py
src/ui/: __init__.py (exists, empty or minimal)
tests/: conftest.py, test_analysis_pipeline.py, test_audio_capture.py, test_config.py, test_db_repository.py, test_db_schema.py, test_grammar.py, test_integration.py, test_jlpt_vocab.py, test_ollama_client.py, test_pipeline.py, test_qwen_asr.py, test_silero_vad.py, test_tokenizer.py

### Pre-existing LSP Errors (NOT our fault, ignore):
- src/analysis/complexity.py: missing AppConfig attributes (complexity_vocab_threshold etc.) — pre-existing
- tests/test_complexity.py: constructor param error — pre-existing
- tests/test_tokenizer.py: fugashi.Tagger not found — pre-existing

### Key Config/Environment
- Testing UI: QT_QPA_PLATFORM=offscreen required for headless Qt tests
- All tools: activate venv before running python/pytest
- Ruff line length: 99, double quotes, trailing commas
- Mypy: strict mode
- Qt6 API: globalPosition().toPoint() NOT globalPos(); exec() NOT exec_()

### Wave Execution Strategy
Wave 1: Tasks 1, 2a, 2b (parallel) → then 2c (sequential after 1+2a+2b)
Wave 2: Tasks 3 and 4 (parallel) → then 5 (sequential after 3+4)  
Wave 3: Tasks 6 and 7 (parallel, 7 actually independent of 6 for creation)
Final: F1-F4 parallel verification
