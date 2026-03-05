# Milestone 0 — Project Scaffolding

## TL;DR

> **Quick Summary**: Set up the MyASR project foundation — tooling config, directory structure, exception hierarchy, and config module with tests.
> 
> **Deliverables**:
> - `.gitignore` updated to standard Python gitignore (currently blocks `.toml`/`.txt`/`.json`)
> - `pyproject.toml` with ruff, mypy, pytest config
> - `requirements.txt` + `requirements-dev.txt`
> - All `src/` subpackage `__init__.py` files (7 packages + root)
> - `tests/__init__.py`
> - `data/.gitkeep`
> - `src/exceptions.py` with full exception hierarchy
> - `src/config.py` with `AppConfig` dataclass + load/save
> - `tests/test_config.py`
> 
> **Estimated Effort**: Quick
> **Parallel Execution**: YES — 2 waves (Wave 1: 3 parallel tasks, Wave 2: verification)
> **Critical Path**: Task 1 (.gitignore fix) → Tasks 2-4 parallel → Task 5 verification

---

## Context

### Original Request
Complete all tasks under Milestone 0 from `docs/tasks.md`: Task 0.1 (project structure + tooling), Task 0.2 (exceptions), Task 0.3 (config module).

### Interview Summary
**Key Discussions**:
- Config file path: `data/config.json` (default, created at runtime — NOT committed)
- Test strategy: Tests-after (not TDD)
- Dev dependencies: Separate `requirements-dev.txt` file

**Research Findings**:
- Project is blank slate — only `docs/`, `AGENTS.md`, `.gitignore`, `.vscode/` exist
- Architecture docs confirm 7 subpackages: `audio`, `vad`, `asr`, `analysis`, `llm`, `ui`, `db` (no standalone `grammar` package)
- Current `.gitignore` uses whitelist (`*.*`, `!*.md`, `!*.py`) which blocks `.toml`, `.txt`, `.json`, `.gitkeep` — must fix first

### Metis Review
**Identified Gaps** (addressed):
- `.gitignore` blocks non-Python files → Added as prerequisite step in Task 1
- `src/grammar/` not a standalone package → Confirmed 7 packages only, no `grammar/`
- `load_config` must handle missing file + partial JSON → Added to acceptance criteria
- `save_config` must create parent `data/` directory if missing → Added to implementation spec
- All `__init__.py` must be empty (no re-exports, no `__all__`) → Added as explicit guardrail

---

## Work Objectives

### Core Objective
Establish the complete project scaffolding so that all subsequent milestone tasks can be built on a solid, lint-clean, type-checked foundation.

### Concrete Deliverables
- Updated `.gitignore` (standard Python, not whitelist)
- `pyproject.toml` (ruff + mypy + pytest config only)
- `requirements.txt` (runtime deps, no version pins)
- `requirements-dev.txt` (dev deps, no version pins)
- `src/__init__.py` + 7 subpackage `__init__.py` files (all empty)
- `tests/__init__.py` (empty)
- `data/.gitkeep` (empty marker)
- `src/exceptions.py` (exception hierarchy)
- `src/config.py` (`AppConfig` dataclass + load/save)
- `tests/test_config.py` (config tests)

### Definition of Done
- [ ] `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short` passes
- [ ] All `src/` subpackages importable via `import src.audio`, `import src.vad`, etc.
- [ ] Exception hierarchy verifiable via subclass checks
- [ ] Config load/save round-trips correctly, handles missing file + partial JSON

### Must Have
- `.gitignore` fixed BEFORE creating any non-Python files
- Empty `__init__.py` files (zero content)
- Exception classes with only docstrings (bare subclasses)
- `AppConfig` as plain `@dataclass` with field defaults
- `load_config` handles: missing file → defaults, partial JSON → merge with defaults
- `save_config` creates parent directory if needed
- Tests use `tmp_path` fixture (no hardcoded paths)

### Must NOT Have (Guardrails)
- **No `src/grammar/` package** — grammar lives under `src/analysis/grammar.py` (created in M1)
- **No re-exports, `__all__`, or docstrings in `__init__.py`** — all must be completely empty
- **No version pins** in `requirements.txt` or `requirements-dev.txt` — bare package names only
- **No `[project]` or `[build-system]` sections** in `pyproject.toml` — tool config only
- **No validation logic** in `AppConfig` — no `__post_init__`, no pydantic, no range checks
- **No custom `__init__` methods** on exception classes — bare subclasses with docstring + `pass`
- **No logging configuration**, CLI parsing, or entry points
- **No `__main__.py`** — entry point is M4
- **No `conftest.py`** or shared test fixtures — tests are self-contained
- **No test subdirectories** under `tests/` — flat structure for M0
- **No `data/config.json` committed** — only `data/.gitkeep` is committed; config created at runtime
- **No over-documentation** — Google-style docstrings where needed, nothing excessive

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO (being created in Task 0.1)
- **Automated tests**: YES (tests-after, not TDD)
- **Framework**: pytest (configured in pyproject.toml)

### QA Policy
Every task includes agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **All tasks**: Use Bash — run commands, verify imports, check tool output
- **Task 4 (config tests)**: Use Bash (pytest) — run test suite, verify pass/fail

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — all 4 tasks can run in parallel):
├── Task 1: Fix .gitignore + create pyproject.toml + requirements files [quick]
├── Task 2: Create all __init__.py files + data/.gitkeep [quick]
├── Task 3: Create exception hierarchy [quick]
└── Task 4: Create config module + tests [quick]

NOTE: Tasks 2-4 all create files under src/ and tests/ which Task 1 doesn't touch.
      Task 1 fixes .gitignore and creates pyproject.toml + requirements*.txt.
      These are independent file sets — all 4 can run simultaneously.

Wave FINAL (After ALL tasks — verification):
├── Task F1: Full lint/type/test verification [quick]
├── Task F2: Import verification + hierarchy check [quick]
└── Task F3: Scope fidelity check [deep]

Critical Path: All Wave 1 tasks → Wave FINAL
Parallel Speedup: All 4 implementation tasks run simultaneously
Max Concurrent: 4 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 (.gitignore + tooling) | — | F1, F2, F3 |
| 2 (__init__.py + data/) | — | F1, F2, F3 |
| 3 (exceptions) | — | F1, F2, F3 |
| 4 (config + tests) | — | F1, F2, F3 |
| F1 (lint/type/test) | 1, 2, 3, 4 | — |
| F2 (import verification) | 1, 2, 3, 4 | — |
| F3 (scope fidelity) | 1, 2, 3, 4 | — |

### Agent Dispatch Summary

- **Wave 1**: **4 tasks** — T1 → `quick`, T2 → `quick`, T3 → `quick`, T4 → `quick`
- **Wave FINAL**: **3 tasks** — F1 → `quick`, F2 → `quick`, F3 → `deep`

---

## TODOs

- [ ] 1. Fix .gitignore and create tooling config files

  **What to do**:
  - Replace the current `.gitignore` (which uses `*.*` / `!*.md` / `!*.py` whitelist that blocks `.toml`, `.txt`, `.json`, `.gitkeep`) with a standard Python `.gitignore`:
    ```
    # Python
    __pycache__/
    *.py[cod]
    *$py.class
    *.egg-info/
    dist/
    build/
    *.egg

    # Virtual environments
    .venv/
    venv/

    # IDE
    .idea/

    # Model weights and audio (large binary files)
    *.onnx
    *.pt
    *.bin
    *.wav
    *.mp3
    *.flac

    # Runtime data
    data/myasr.db
    data/config.json

    # OS
    .DS_Store
    Thumbs.db
    ```
  - Create `pyproject.toml` with ONLY these sections:
    ```toml
    [tool.ruff]
    line-length = 99
    target-version = "py312"

    [tool.ruff.format]
    quote-style = "double"

    [tool.ruff.lint]
    select = ["E", "F", "W", "I"]

    [tool.ruff.lint.isort]
    known-first-party = ["src"]

    [tool.mypy]
    python_version = "3.12"
    strict = true
    warn_return_any = true
    warn_unused_configs = true
    disallow_untyped_defs = true

    [tool.pytest.ini_options]
    testpaths = ["tests"]
    pythonpath = ["."]
    ```
  - Create `requirements.txt`:
    ```
    torch
    torchaudio
    sounddevice
    silero-vad
    fugashi
    unidic-lite
    jreadability
    PySide6
    requests
    numpy
    ```
  - Create `requirements-dev.txt`:
    ```
    ruff
    mypy
    pytest
    pytest-mock
    ```

  **Must NOT do**:
  - Do NOT add `[project]` or `[build-system]` to pyproject.toml
  - Do NOT add version pins to requirements files
  - Do NOT add any entry points or packaging metadata
  - Do NOT keep the old whitelist `.gitignore` approach

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple file creation with known content, no complex logic
  - **Skills**: []
    - No special skills needed — pure file creation
  - **Skills Evaluated but Omitted**:
    - `git-master`: Not needed — just creating files, no git operations beyond .gitignore

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: F1, F2, F3
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL):

  **Pattern References**:
  - `AGENTS.md` lines about "Formatter/Linter: ruff", "Line length: 99 characters", "Quotes: Double quotes", "Type checker: mypy in strict mode" — These define the exact ruff/mypy settings to use
  - `.gitignore` (current file) — Must be REPLACED entirely, not appended to

  **External References**:
  - `docs/tasks.md:14-18` — Task 0.1 specification: exact files, deps list, done criteria

  **WHY Each Reference Matters**:
  - `AGENTS.md` provides the canonical code style config that pyproject.toml must encode
  - Current `.gitignore` must be read to understand the problem (whitelist blocks non-py files)
  - `docs/tasks.md` is the source of truth for required dependencies

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Tooling commands run successfully
    Tool: Bash
    Preconditions: All files created, dev deps installed (ruff, mypy, pytest available)
    Steps:
      1. Run `ruff check .` — expect exit code 0
      2. Run `ruff format --check .` — expect exit code 0
      3. Run `mypy . --no-error-summary 2>&1 | head -5` — expect no errors
      4. Run `python -c "import tomllib; d = tomllib.load(open('pyproject.toml','rb')); assert 'tool' in d; assert 'ruff' in d['tool']; assert 'mypy' in d['tool']; print('OK')"`
    Expected Result: All commands exit 0, pyproject.toml parses with correct sections
    Failure Indicators: Non-zero exit, "error" in output, missing sections
    Evidence: .sisyphus/evidence/task-1-tooling-commands.txt

  Scenario: .gitignore no longer blocks essential files
    Tool: Bash
    Preconditions: .gitignore replaced, pyproject.toml and requirements.txt created
    Steps:
      1. Run `git check-ignore pyproject.toml` — expect exit code 1 (NOT ignored)
      2. Run `git check-ignore requirements.txt` — expect exit code 1 (NOT ignored)
      3. Run `git check-ignore requirements-dev.txt` — expect exit code 1 (NOT ignored)
      4. Run `git check-ignore data/.gitkeep` — expect exit code 1 (NOT ignored)
      5. Run `git check-ignore __pycache__/foo.pyc` — expect exit code 0 (IS ignored)
    Expected Result: Config files NOT ignored, pycache IS ignored
    Failure Indicators: pyproject.toml or requirements.txt showing as ignored
    Evidence: .sisyphus/evidence/task-1-gitignore-check.txt
  ```

  **Commit**: YES (groups with Tasks 2, 3, 4)
  - Message: `feat(scaffold): add project scaffolding, exceptions, and config module`
  - Files: `.gitignore`, `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`
  - Pre-commit: `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short`

- [ ] 2. Create all `__init__.py` files and `data/` directory

  **What to do**:
  - Create `src/__init__.py` — empty file (0 bytes or single newline)
  - Create `src/audio/__init__.py` — empty
  - Create `src/vad/__init__.py` — empty
  - Create `src/asr/__init__.py` — empty
  - Create `src/analysis/__init__.py` — empty
  - Create `src/llm/__init__.py` — empty
  - Create `src/ui/__init__.py` — empty
  - Create `src/db/__init__.py` — empty
  - Create `tests/__init__.py` — empty
  - Create `data/.gitkeep` — empty marker file
  - All `__init__.py` files must be COMPLETELY EMPTY. No imports, no `__all__`, no docstrings, no comments.

  **Must NOT do**:
  - Do NOT create `src/grammar/` — grammar lives under `src/analysis/grammar.py` (Milestone 1)
  - Do NOT create `src/pipeline.py` — that's Milestone 2
  - Do NOT create `src/main.py` or `src/__main__.py` — that's Milestone 4
  - Do NOT create any test subdirectories (`tests/test_audio/`, etc.) — tests are flat for M0
  - Do NOT put ANY content in `__init__.py` files — no re-exports, no `__all__`, no docstrings
  - Do NOT create `conftest.py`

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Creating empty files, no logic at all
  - **Skills**: []
    - No special skills needed
  - **Skills Evaluated but Omitted**:
    - None applicable — this is purely file creation

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: F1, F2, F3
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL):

  **Pattern References**:
  - `docs/architecture.md` module map — Canonical list of 7 subpackages: audio, vad, asr, analysis, llm, ui, db

  **WHY Each Reference Matters**:
  - Architecture doc is the source of truth for which subpackages exist — prevents creating wrong directories

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All packages are importable
    Tool: Bash
    Preconditions: All __init__.py files created
    Steps:
      1. Run `python -c "import src; import src.audio; import src.vad; import src.asr; import src.analysis; import src.llm; import src.ui; import src.db; import tests; print('All packages importable')"`
    Expected Result: Prints "All packages importable" with exit code 0
    Failure Indicators: ImportError or ModuleNotFoundError
    Evidence: .sisyphus/evidence/task-2-packages-importable.txt

  Scenario: No forbidden directories or files exist
    Tool: Bash
    Preconditions: All files created
    Steps:
      1. Run `test ! -d src/grammar && echo "No src/grammar/ - PASS" || echo "FAIL: src/grammar/ exists"`
      2. Run `test ! -f src/__main__.py && echo "No __main__.py - PASS" || echo "FAIL: __main__.py exists"`
      3. Run `test ! -f conftest.py && echo "No conftest.py - PASS" || echo "FAIL: conftest.py exists"`
      4. Run `test -f data/.gitkeep && echo "data/.gitkeep exists - PASS" || echo "FAIL: data/.gitkeep missing"`
    Expected Result: All 4 checks show PASS
    Failure Indicators: Any line containing "FAIL"
    Evidence: .sisyphus/evidence/task-2-no-forbidden-files.txt

  Scenario: All __init__.py files are empty
    Tool: Bash
    Preconditions: All __init__.py files created
    Steps:
      1. Run `find src tests -name "__init__.py" -exec sh -c 'size=$(wc -c < "$1"); if [ "$size" -gt 1 ]; then echo "FAIL: $1 has $size bytes"; fi' _ {} \;`
      2. If no output, print "All __init__.py files are empty - PASS"
    Expected Result: All __init__.py files are 0 or 1 byte (empty or single newline)
    Failure Indicators: Any "FAIL" output indicating non-empty file
    Evidence: .sisyphus/evidence/task-2-init-empty.txt
  ```

  **Commit**: YES (groups with Tasks 1, 3, 4)
  - Message: `feat(scaffold): add project scaffolding, exceptions, and config module`
  - Files: all `__init__.py` files, `data/.gitkeep`

- [ ] 3. Create exception hierarchy

  **What to do**:
  - Create `src/exceptions.py` with the following exception hierarchy:
    ```python
    class MyASRError(Exception):
        """Base exception for all MyASR errors."""

    class AudioCaptureError(MyASRError):
        """Error during audio capture."""

    class VADError(MyASRError):
        """Error during voice activity detection."""

    class ASRError(MyASRError):
        """Error during automatic speech recognition."""

    class ModelLoadError(ASRError):
        """Failed to load a model (ASR, VAD, etc.)."""

    class PreprocessingError(MyASRError):
        """Error during text preprocessing/analysis."""

    class LLMError(MyASRError):
        """Error communicating with the LLM service."""

    class LLMTimeoutError(LLMError):
        """LLM request timed out."""

    class LLMUnavailableError(LLMError):
        """LLM service is not reachable."""

    class DatabaseError(MyASRError):
        """Error during database operations."""
    ```
  - Each class body is ONLY a docstring. No `__init__`, no attributes, no methods.
  - Follow AGENTS.md style: double quotes, type annotations not needed (no methods)

  **Must NOT do**:
  - Do NOT add `__init__` methods or custom attributes to any exception class
  - Do NOT add error codes, `.to_dict()`, or `.message` attributes
  - Do NOT add `__all__` or any module-level variables
  - Do NOT create any exception not listed in the hierarchy above

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file with simple class definitions, no logic
  - **Skills**: []
    - No special skills needed
  - **Skills Evaluated but Omitted**:
    - None applicable — trivial file creation

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: F1, F2, F3
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL):

  **Pattern References**:
  - `docs/tasks.md:27-40` — Task 0.2 specification: exact class names and hierarchy
  - `AGENTS.md` "Error Handling" section — Pattern for exception classes: specific exceptions, custom exceptions in `src/exceptions.py`

  **WHY Each Reference Matters**:
  - `docs/tasks.md` provides the exact hierarchy that must be implemented 1:1
  - `AGENTS.md` shows the code style for exceptions (specific, with `from None` pattern)

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All exceptions import cleanly
    Tool: Bash
    Preconditions: src/exceptions.py created
    Steps:
      1. Run `python -c "from src.exceptions import MyASRError, AudioCaptureError, VADError, ASRError, ModelLoadError, PreprocessingError, LLMError, LLMTimeoutError, LLMUnavailableError, DatabaseError; print('All exceptions imported')"`
    Expected Result: Prints "All exceptions imported" with exit code 0
    Failure Indicators: ImportError or NameError
    Evidence: .sisyphus/evidence/task-3-exceptions-import.txt

  Scenario: Exception hierarchy is correct
    Tool: Bash
    Preconditions: src/exceptions.py created
    Steps:
      1. Run:
         ```
         python -c "
         from src.exceptions import *
         # Direct subclasses of MyASRError
         assert issubclass(AudioCaptureError, MyASRError)
         assert issubclass(VADError, MyASRError)
         assert issubclass(ASRError, MyASRError)
         assert issubclass(PreprocessingError, MyASRError)
         assert issubclass(LLMError, MyASRError)
         assert issubclass(DatabaseError, MyASRError)
         # Second-level subclasses
         assert issubclass(ModelLoadError, ASRError)
         assert issubclass(ModelLoadError, MyASRError)
         assert issubclass(LLMTimeoutError, LLMError)
         assert issubclass(LLMTimeoutError, MyASRError)
         assert issubclass(LLMUnavailableError, LLMError)
         assert issubclass(LLMUnavailableError, MyASRError)
         # NOT wrong parents
         assert not issubclass(ModelLoadError, LLMError)
         assert not issubclass(LLMTimeoutError, ASRError)
         print('Hierarchy OK')
         "
         ```
    Expected Result: Prints "Hierarchy OK" with exit code 0
    Failure Indicators: AssertionError indicating wrong parent class
    Evidence: .sisyphus/evidence/task-3-hierarchy-check.txt

  Scenario: Exception classes are bare (no custom __init__ or attributes)
    Tool: Bash
    Preconditions: src/exceptions.py created
    Steps:
      1. Run:
         ```
         python -c "
         import inspect
         from src import exceptions
         for name, cls in inspect.getmembers(exceptions, inspect.isclass):
             if issubclass(cls, Exception) and cls is not Exception:
                 # Check no __init__ defined in this class (not inherited)
                 assert '__init__' not in cls.__dict__, f'{name} has custom __init__'
                 # Check no extra methods beyond inherited
                 own_methods = [m for m in cls.__dict__ if not m.startswith('__') or m == '__init__']
                 assert len(own_methods) == 0, f'{name} has extra members: {own_methods}'
         print('All exceptions are bare subclasses')
         "
         ```
    Expected Result: Prints "All exceptions are bare subclasses" with exit code 0
    Failure Indicators: AssertionError indicating custom __init__ or extra methods
    Evidence: .sisyphus/evidence/task-3-bare-classes.txt
  ```

  **Commit**: YES (groups with Tasks 1, 2, 4)
  - Message: `feat(scaffold): add project scaffolding, exceptions, and config module`
  - Files: `src/exceptions.py`

- [ ] 4. Create config module and tests

  **What to do**:
  - Create `src/config.py`:
    - Import: `dataclasses`, `json`, `pathlib.Path`
    - Define `@dataclass` class `AppConfig` with these exact fields and defaults:
      - `user_jlpt_level: int = 3`
      - `complexity_vocab_threshold: int = 2`
      - `complexity_n1_grammar_threshold: int = 1`
      - `complexity_readability_threshold: float = 3.0`
      - `complexity_ambiguous_grammar_threshold: int = 1`
      - `ollama_url: str = "http://localhost:11434"`
      - `ollama_model: str = "qwen3.5:4b"`
      - `ollama_timeout_sec: float = 30.0`
      - `sample_rate: int = 16000`
      - `db_path: str = "data/myasr.db"`
    - Function `load_config(path: str = "data/config.json") -> AppConfig`:
      - If file doesn't exist → return `AppConfig()` (defaults)
      - If file exists → load JSON, merge with defaults (partial JSON support: missing keys get defaults)
      - If JSON is malformed → return `AppConfig()` (fall back to defaults, don't crash)
      - Pattern: `defaults = dataclasses.asdict(AppConfig()); defaults.update(loaded_json); return AppConfig(**defaults)`
    - Function `save_config(config: AppConfig, path: str = "data/config.json") -> None`:
      - Create parent directory if it doesn't exist (`Path(path).parent.mkdir(parents=True, exist_ok=True)`)
      - Write JSON with `indent=2` and `ensure_ascii=False`
  - Create `tests/test_config.py`:
    - `test_appconfig_defaults()` — verify all 10 default values match spec exactly
    - `test_load_config_missing_file(tmp_path)` — nonexistent path returns defaults
    - `test_load_config_malformed_json(tmp_path)` — invalid JSON returns defaults
    - `test_save_and_load_roundtrip(tmp_path)` — save config, load it back, verify equal
    - `test_load_config_partial_json(tmp_path)` — JSON with only `{"user_jlpt_level": 2}` returns config with level=2 and all other fields at defaults
    - `test_save_config_creates_parent_dirs(tmp_path)` — save to `tmp_path/nested/dir/config.json` succeeds

  **Must NOT do**:
  - Do NOT add `__post_init__` validation to `AppConfig`
  - Do NOT use pydantic or attrs — plain `@dataclass` only
  - Do NOT add environment variable support
  - Do NOT add CLI argument parsing
  - Do NOT add logging in this module (module-level logger is fine but don't log from load/save)
  - Do NOT create `conftest.py` — tests are self-contained using `tmp_path` fixture

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small config module + straightforward tests, clear specification
  - **Skills**: []
    - No special skills needed
  - **Skills Evaluated but Omitted**:
    - None — standard Python, no framework-specific knowledge needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: F1, F2, F3
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL):

  **Pattern References**:
  - `docs/tasks.md:42-56` — Task 0.3 specification: exact fields, defaults, function signatures
  - `docs/architecture.md` — Complexity thresholds table confirms default values
  - `docs/api-data.md` — Ollama API details confirm ollama_url and ollama_model defaults
  - `AGENTS.md` "Typing" section — All public functions MUST have type annotations, use modern syntax

  **API/Type References**:
  - `docs/api-data.md` Ollama section — Confirms URL `http://localhost:11434`, model `qwen3.5:4b`, timeout 30s

  **Test References**:
  - `AGENTS.md` "Testing" section — Use pytest, function naming `test_<what>_<condition>_<expected>`, parametrize for variants, `tmp_path` for file ops

  **WHY Each Reference Matters**:
  - `docs/tasks.md` is the source of truth for field names and defaults — must match exactly
  - `docs/architecture.md` complexity thresholds validate the default values are correct
  - `AGENTS.md` testing section ensures tests follow project conventions

  **Acceptance Criteria**:

  **If tests-after (confirmed):**
  - [ ] Test file created: `tests/test_config.py`
  - [ ] `pytest tests/test_config.py -x -v` → PASS (6 tests, 0 failures)
  - [ ] `mypy src/config.py` → Success, no issues

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Config defaults match specification exactly
    Tool: Bash
    Preconditions: src/config.py created
    Steps:
      1. Run:
         ```
         python -c "
         from src.config import AppConfig
         c = AppConfig()
         assert c.user_jlpt_level == 3, f'Expected 3, got {c.user_jlpt_level}'
         assert c.complexity_vocab_threshold == 2
         assert c.complexity_n1_grammar_threshold == 1
         assert c.complexity_readability_threshold == 3.0
         assert c.complexity_ambiguous_grammar_threshold == 1
         assert c.ollama_url == 'http://localhost:11434'
         assert c.ollama_model == 'qwen3.5:4b'
         assert c.ollama_timeout_sec == 30.0
         assert c.sample_rate == 16000
         assert c.db_path == 'data/myasr.db'
         print('All 10 defaults correct')
         "
         ```
    Expected Result: Prints "All 10 defaults correct" with exit code 0
    Failure Indicators: AssertionError with specific field mismatch
    Evidence: .sisyphus/evidence/task-4-config-defaults.txt

  Scenario: Load config handles missing file gracefully
    Tool: Bash
    Preconditions: src/config.py created, no config file at test path
    Steps:
      1. Run:
         ```
         python -c "
         from src.config import load_config
         c = load_config('/tmp/definitely_nonexistent_path_12345.json')
         assert c.user_jlpt_level == 3
         assert c.ollama_model == 'qwen3.5:4b'
         print('Missing file returns defaults OK')
         "
         ```
    Expected Result: Prints "Missing file returns defaults OK" with exit code 0
    Failure Indicators: FileNotFoundError or any exception
    Evidence: .sisyphus/evidence/task-4-missing-file.txt

  Scenario: Save and load round-trips correctly
    Tool: Bash
    Preconditions: src/config.py created
    Steps:
      1. Run:
         ```
         python -c "
         import tempfile, os
         from src.config import AppConfig, save_config, load_config
         with tempfile.TemporaryDirectory() as td:
             path = os.path.join(td, 'test_config.json')
             original = AppConfig(user_jlpt_level=1, ollama_model='test-model')
             save_config(original, path)
             loaded = load_config(path)
             assert loaded.user_jlpt_level == 1, f'Got {loaded.user_jlpt_level}'
             assert loaded.ollama_model == 'test-model', f'Got {loaded.ollama_model}'
             assert loaded.sample_rate == 16000  # default preserved
             print('Round-trip OK')
         "
         ```
    Expected Result: Prints "Round-trip OK" with exit code 0
    Failure Indicators: AssertionError or file I/O error
    Evidence: .sisyphus/evidence/task-4-roundtrip.txt

  Scenario: Full test suite passes
    Tool: Bash
    Preconditions: src/config.py and tests/test_config.py created
    Steps:
      1. Run `pytest tests/test_config.py -x -v`
    Expected Result: All 6 tests pass (0 failures)
    Failure Indicators: Any "FAILED" in output or non-zero exit
    Evidence: .sisyphus/evidence/task-4-pytest.txt
  ```

  **Commit**: YES (groups with Tasks 1, 2, 3)
  - Message: `feat(scaffold): add project scaffolding, exceptions, and config module`
  - Files: `src/config.py`, `tests/test_config.py`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 3 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Full Lint/Type/Test Verification** — `quick`

  Run the full M0 verification suite. Every check must pass with zero warnings.

  **What to do**:
  - Run `ruff check .` — must report zero issues
  - Run `ruff format --check .` — must report zero reformats needed
  - Run `mypy .` — must report zero errors (strict mode)
  - Run `pytest -x --tb=short` — must report all tests pass
  - Run `pytest --co` — must list all discovered tests

  **Acceptance Criteria**:
  ```
  ruff check . → "All checks passed!" or no output (0 exit)
  ruff format --check . → "X files already formatted" (0 exit)
  mypy . → "Success: no issues found" (0 exit)
  pytest -x --tb=short → "X passed" (0 exit)
  ```

  **Evidence**: `.sisyphus/evidence/task-F1-full-verification.txt` (combined stdout)

- [ ] F2. **Import & Hierarchy Verification** — `quick`

  Verify all packages are importable and exception hierarchy is correct.

  **What to do**:
  - Run: `python -c "import src; import src.audio; import src.vad; import src.asr; import src.analysis; import src.llm; import src.ui; import src.db; print('All packages importable')"`
  - Run: `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('pyproject.toml valid')"`
  - Run the exception hierarchy verification snippet
  - Run: `python -c "from src.config import AppConfig, load_config, save_config; c = AppConfig(); assert c.user_jlpt_level == 3; print('Config defaults OK')"`

  **Acceptance Criteria**:
  ```
  All packages importable → "All packages importable"
  pyproject.toml valid → "pyproject.toml valid"
  Exception hierarchy → "Hierarchy OK"
  Config defaults → "Config defaults OK"
  ```

  **Evidence**: `.sisyphus/evidence/task-F2-import-hierarchy.txt`

- [ ] F3. **Scope Fidelity Check** — `deep`

  Verify nothing beyond Milestone 0 scope was created and all guardrails were followed.

  **What to do**:
  - Verify NO `src/grammar/` directory exists
  - Verify NO `__main__.py` exists
  - Verify NO `conftest.py` exists
  - Verify ALL `__init__.py` files are empty (0 bytes or single newline only)
  - Verify `pyproject.toml` has NO `[project]` or `[build-system]` sections
  - Verify `requirements.txt` has NO version pins (no `==`, `>=`, `<=`, `~=`)
  - Verify exception classes have NO `__init__` methods (bare subclasses only)
  - Verify `AppConfig` has NO `__post_init__` method
  - Verify `data/config.json` does NOT exist (not committed)
  - Verify `data/.gitkeep` exists

  **Acceptance Criteria**:
  ```
  All scope checks pass with specific verification per item above.
  ```

  **Evidence**: `.sisyphus/evidence/task-F3-scope-fidelity.txt`

---

## Commit Strategy

- After ALL tasks pass Wave FINAL verification:
  - `feat(scaffold): add project scaffolding, exceptions, and config module` — all files from Tasks 1-4
  - Pre-commit: `ruff check . && ruff format --check . && mypy . && pytest -x --tb=short`

---

## Success Criteria

### Verification Commands
```bash
ruff check .                    # Expected: 0 issues
ruff format --check .           # Expected: 0 reformats
mypy .                          # Expected: Success, no issues
pytest -x --tb=short            # Expected: all tests pass
pytest --co                     # Expected: lists test_config.py tests
python -c "import src.audio; import src.vad; import src.asr; import src.analysis; import src.llm; import src.ui; import src.db"  # Expected: no error
```

### Final Checklist
- [ ] `.gitignore` tracks `.toml`, `.txt`, `.json`, `.gitkeep` files
- [ ] All `__init__.py` files are empty
- [ ] Exception hierarchy correct (subclass checks pass)
- [ ] `AppConfig` defaults match spec exactly
- [ ] `load_config` handles missing file + partial JSON
- [ ] `save_config` creates parent dirs + writes valid JSON
- [ ] All tests pass
- [ ] All linting/typing clean
