# DB PACKAGE KNOWLEDGE BASE

## OVERVIEW

SQLite storage layer for learning records. Manages sentences, vocabulary hits, and grammar patterns with a repository pattern.

## STRUCTURE

- `schema.py`: SQL schema definitions and `init_db()` helper.
- `models.py`: Frozen dataclass DTOs for database records and pipeline results.
- `repository.py`: `LearningRepository` for all CRUD operations.
- `__init__.py`: Package marker.

## SCHEMA

- **sentence_records**: Primary text and source metadata.
- **highlight_vocab**: Vocabulary hits linked to sentences (FK).
- **highlight_grammar**: Grammar patterns linked to sentences (FK).
- **app_settings**: Key-value store for persistent configuration.

## MODELS

- **Record Types**: `SentenceRecord`, `HighlightVocab`, `HighlightGrammar`.
- **Pipeline Types**: `SentenceResult`, `VocabHit`, `GrammarHit` (mapped to records).
- **Other**: `AudioSegment`, `Token`, `AnalysisResult`.

## CONVENTIONS

- **Initialization**: `init_db()` enables **WAL mode** and **Foreign Keys**.
- **Location**: Default database file is at `data/myasr.db`.
- **Repository**: `LearningRepository` handles connection lifecycle and transactions.
- **CRUD**: Methods for `insert_sentence`, `search_sentences`, `get_sentences_filtered`, and `export_records` (JSON/CSV).
- **Maintenance**: `delete_before()` for record cleanup.

## NOTES

- **WAL Checkpoint**: Perform manual checkpoint on app shutdown (handled in `main.py`).
- **Cascades**: `ON DELETE CASCADE` ensures highlights are removed with sentences.
- **Performance**: Indexes on `created_at` and `sentence_id` for fast retrieval and joins.
- **Thread Safety**: One repository instance per thread recommended.
