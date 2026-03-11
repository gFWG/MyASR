# ANALYSIS LAYER KNOWLEDGE BASE

## OVERVIEW

Japanese NLP analysis pipeline. Performs morphological analysis, JLPT vocabulary lookup, and grammar pattern matching. Japanese only by design. Accuracy prioritized over latency.

## STRUCTURE

| Module | Component | Responsibility |
|--------|-----------|----------------|
| `pipeline.py` | `PreprocessingPipeline` | Orchestrator for tokenize → vocab → grammar |
| `tokenizer.py` | `FugashiTokenizer` | MeCab wrapper (fugashi) for morphological analysis |
| `jlpt_vocab.py` | `JLPTVocabLookup` | O(1) dictionary lookup for JLPT N1-N5 vocabulary |
| `grammar.py` | `GrammarMatcher` | Regex-based detection of JLPT grammar points |

## DATA FLOW

1. **Input**: Raw Japanese text from ASR.
2. **Tokenization**: `FugashiTokenizer` splits text into tokens with surface, lemma, and POS.
3. **Vocab Lookup**: `JLPTVocabLookup` identifies words beyond user's JLPT level.
4. **Grammar Match**: `GrammarMatcher` scans text for advanced grammar patterns via regex.
5. **Output**: `AnalysisResult` DTO containing tokens and hits for UI highlighting.

## CONVENTIONS

- **Dictionary lookup**: Vocab levels N1-N5 loaded from `data/vocabulary.csv` via `JLPTVocabLookup`.
- **Regex patterns**: Grammar rules with pre-compiled regex in `data/grammar_rules.json`.
- **Level filtering**: Hits only returned if `hit.level < user_level` (lower is harder).
- **POS filtering**: Punctuation and symbols are excluded during tokenization.

## NOTES

- Uses `unidic-lite` as the default dictionary for fugashi.
- `PreprocessingPipeline` shares a single tagger instance for performance.
- Vocabulary lookup uses lemmas (dictionary form) for consistent matching.
- Grammar matching uses raw text to capture patterns across token boundaries.
