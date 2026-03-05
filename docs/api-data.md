# API & Data Specifications

## SQLite Database Schema

### Table: `sentence_records`

Primary learning record. One row per sentence displayed in the overlay.

```sql
CREATE TABLE sentence_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    japanese_text   TEXT    NOT NULL,
    chinese_translation TEXT,           -- NULL when LLM unavailable
    explanation     TEXT,               -- Study-point analysis, NULL for simple sentences
    complexity_score REAL  NOT NULL DEFAULT 0.0,
    is_complex      INTEGER NOT NULL DEFAULT 0,  -- 0=simple, 1=complex
    source_context  TEXT,               -- Optional: "game", "movie", etc.
    created_at      TEXT    NOT NULL    -- ISO 8601 timestamp
);

CREATE INDEX idx_sentence_created_at ON sentence_records(created_at);
```

### Table: `highlight_vocab`

Normalized vocabulary highlights. Foreign key to sentence_records.

```sql
CREATE TABLE highlight_vocab (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id     INTEGER NOT NULL REFERENCES sentence_records(id) ON DELETE CASCADE,
    surface         TEXT    NOT NULL,   -- Surface form as it appears in text
    lemma           TEXT    NOT NULL,   -- Dictionary form
    pos             TEXT    NOT NULL,   -- Part of speech (fugashi output)
    jlpt_level      INTEGER,           -- 1-5 (N1-N5), NULL if not in dictionary
    is_beyond_level INTEGER NOT NULL DEFAULT 0,  -- 1 if beyond user's current level
    tooltip_shown   INTEGER NOT NULL DEFAULT 0   -- 1 if user hovered (triggers record)
);

CREATE INDEX idx_highlight_vocab_sentence ON highlight_vocab(sentence_id);
```

### Table: `highlight_grammar`

Normalized grammar highlights. Foreign key to sentence_records.

```sql
CREATE TABLE highlight_grammar (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id     INTEGER NOT NULL REFERENCES sentence_records(id) ON DELETE CASCADE,
    rule_id         TEXT    NOT NULL,   -- Grammar rule identifier
    pattern         TEXT    NOT NULL,   -- Matched text span in the sentence
    jlpt_level      INTEGER,           -- 1-5 (N1-N5)
    confidence_type TEXT    NOT NULL,   -- "high" or "ambiguous"
    description     TEXT,              -- Brief explanation of the grammar point
    is_beyond_level INTEGER NOT NULL DEFAULT 0,
    tooltip_shown   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_highlight_grammar_sentence ON highlight_grammar(sentence_id);
```

### Table: `app_settings` (P1)

Key-value store for user preferences.

```sql
CREATE TABLE app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

## Data Entities (Python Dataclasses)

### Pipeline Data Flow

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Token:
    """Single morphological token from fugashi."""
    surface: str        # 表記形 (as written)
    lemma: str          # 原形 (dictionary form)
    pos: str            # 品詞 (part of speech)

@dataclass
class VocabHit:
    """Vocabulary item that exceeds user's JLPT level."""
    surface: str
    lemma: str
    pos: str
    jlpt_level: int     # 1-5 (N1=1, N5=5)
    user_level: int     # User's current level

@dataclass
class GrammarHit:
    """Grammar pattern match result."""
    rule_id: str
    matched_text: str   # Text span that matched
    jlpt_level: int
    confidence_type: str  # "high" | "ambiguous"
    description: str

@dataclass
class AnalysisResult:
    """Output of the preprocessing pipeline."""
    tokens: list[Token]
    vocab_hits: list[VocabHit]
    grammar_hits: list[GrammarHit]
    complexity_score: float
    is_complex: bool

@dataclass
class SentenceResult:
    """Complete result for one sentence, passed from pipeline to UI."""
    japanese_text: str
    chinese_translation: str | None     # None if LLM unavailable
    explanation: str | None             # None for simple sentences
    analysis: AnalysisResult
    created_at: datetime = field(default_factory=datetime.now)
```

### Database Models

```python
@dataclass
class SentenceRecord:
    """Maps to sentence_records table."""
    id: int | None      # None before INSERT (autoincrement)
    japanese_text: str
    chinese_translation: str | None
    explanation: str | None
    complexity_score: float
    is_complex: bool
    source_context: str | None
    created_at: str     # ISO 8601

@dataclass
class HighlightVocab:
    """Maps to highlight_vocab table."""
    id: int | None
    sentence_id: int
    surface: str
    lemma: str
    pos: str
    jlpt_level: int | None
    is_beyond_level: bool
    tooltip_shown: bool

@dataclass
class HighlightGrammar:
    """Maps to highlight_grammar table."""
    id: int | None
    sentence_id: int
    rule_id: str
    pattern: str
    jlpt_level: int | None
    confidence_type: str
    description: str | None
    is_beyond_level: bool
    tooltip_shown: bool
```

## Ollama LLM API

### Endpoint

```
POST http://localhost:11434/api/generate
```

### Simple Sentence Prompt Template

```
あなたは日本語の翻訳者です。次の日本語を中国語に翻訳してください。翻訳のみを出力し、他の内容は出力しないでください。

日本語：{japanese_text}
```

### Complex Sentence Prompt Template

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

### Request Format

```json
{
    "model": "qwen3.5:4b",
    "prompt": "<constructed from template above>",
    "stream": false,
    "options": {
        "temperature": 0.3,
        "num_predict": 512
    }
}
```

### Response Parsing

```json
{
    "response": "翻訳：...\n解析：..."
}
```

Parse `response` field. Split on `翻訳：` and `解析：` markers. If markers missing, treat entire response as translation.

## JLPT Vocabulary Dictionary Format

Source: JSON file loaded at startup.

```json
{
    "食べる": 5,
    "概念": 1,
    "勉強": 4,
    ...
}
```

Key = lemma (dictionary form), Value = JLPT level (1-5, where 1=N1, 5=N5).

## Grammar Rules Format

Source: CSV converted to JSON at build time.

```json
[
    {
        "rule_id": "N2_grammar_001",
        "pattern_regex": "にとって",
        "jlpt_level": 2,
        "confidence_type": "high",
        "description": "～にとって: 对...来说"
    },
    {
        "rule_id": "N1_grammar_042",
        "pattern_regex": "ざるを得ない",
        "jlpt_level": 1,
        "confidence_type": "high",
        "description": "～ざるを得ない: 不得不..."
    },
    {
        "rule_id": "N2_grammar_015",
        "pattern_regex": "わけではない",
        "jlpt_level": 2,
        "confidence_type": "ambiguous",
        "description": "～わけではない: 并非..."
    }
]
```

`confidence_type`:
- `"high"`: Direct match, no LLM verification needed.
- `"ambiguous"`: Match found but context-dependent; include in LLM prompt for verification.

## Highlight Color Scheme

| Level | Vocab Color | Grammar Color | Priority |
|-------|-------------|---------------|----------|
| N5 | — (never beyond-level for N5 users) | — | — |
| N4 | Light green `#C8E6C9` | Dark green `#4CAF50` | Grammar > Vocab |
| N3 | Light blue `#BBDEFB` | Dark blue `#1976D2` | Grammar > Vocab |
| N2 | Light yellow `#FFF9C4` | Dark yellow `#F9A825` | Grammar > Vocab |
| N1 | Light red `#FFCDD2` | Dark red `#D32F2F` | Grammar > Vocab |

When a text span has both vocab and grammar highlights, **grammar takes priority** (grammar color displayed).
