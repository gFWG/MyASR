# User Stories & Acceptance Criteria

## Target User

Windows 11 user playing Japanese games or watching Japanese video content, wanting real-time subtitles, translation, and JLPT-aligned vocabulary/grammar highlights to support Japanese language learning.

---

## P0 Stories (MVP)

### US-01: System Audio Capture + VAD Segmentation

**As a user**, I want the software to capture system playback audio and automatically generate Japanese subtitles, so I don't need to manually transcribe or screenshot.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|-------|------|------|
| AC-01a | System is playing audio containing human speech | VAD detects end of a sentence | A complete audio segment is emitted and triggers ASR |
| AC-01b | System is playing BGM/sound effects only (no speech) | VAD processes the audio stream | ASR is NOT triggered (no noise-induced false positives) |
| AC-01c | Audio device is unavailable or permissions denied | App attempts to capture | Error state shown in overlay with clear message |

---

### US-02: ASR Offline Inference

**As a user**, I want captured audio to be transcribed into Japanese text using an offline model, so I get subtitles without internet dependency.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|-------|------|------|
| AC-02a | ASR model is loaded and resident in VRAM | A valid audio segment is provided | A Japanese text result is returned (or explicit failure reason) |
| AC-02b | ASR inference fails | Error occurs during inference | Overlay shows "Recognition failed" with log entry for debugging |

---

### US-03: Preprocessing Pipeline

**As a user**, I want each subtitle sentence to be analyzed for vocabulary level and grammar patterns, so the system can highlight what's beyond my current JLPT level.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|-------|------|------|
| AC-03a | A Japanese sentence is input | Preprocessing executes | Returns structured result: tokens (surface/lemma/POS), JLPT levels, grammar hits, complexity score |
| AC-03b | Preprocessing is active | Multiple sentences processed consecutively | Average latency < 50ms per sentence |

---

### US-04: LLM Translation + Analysis

**As a user**, I want each subtitle translated to Chinese, with complex sentences also getting study-point analysis, so I can understand content and learn simultaneously.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|-------|------|------|
| AC-04a | Sentence is classified as simple | LLM is called | Returns Chinese translation only (no verbose analysis) |
| AC-04b | Sentence is classified as complex | LLM is called | Returns Chinese translation + study-point analysis in a single API call |
| AC-04c | Ollama is unavailable or times out | LLM call fails | Overlay shows subtitle + preprocessing highlights only (no translation). No crash. |

---

### US-05: Overlay Display + JLPT Highlights

**As a user**, I want to see Japanese subtitles and Chinese translations in a transparent overlay with color-coded JLPT highlights, so I can spot beyond-level content at a glance.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|-------|------|------|
| AC-05a | A new sentence result arrives | UI updates | Overlay displays Japanese text (line 1) + Chinese translation (line 2) with correct highlights |
| AC-05b | Highlight color scheme | Rendering highlights | N2 vocab = light yellow, N2 grammar = dark yellow, N1 vocab = light red, N1 grammar = dark red. Grammar takes priority over vocab when overlapping. |

---

### US-06: Tooltip + Learning Record

**As a user**, I want to hover over highlighted words to see explanations and have them automatically saved to my learning records, so I build a personal study list.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|-------|------|------|
| AC-06a | User hovers over a highlighted word | Tooltip displays | Shows JLPT level + brief explanation |
| AC-06b | Tooltip is triggered for a highlight | Record write condition met | Entry written to SQLite learning record |
| AC-06c | Same highlight in same sentence | Tooltip triggered again | No duplicate record written (one write per highlight per sentence) |

---

## P1 Stories

### US-07: JLPT Level Setting

**As a user**, I want to set my current JLPT level (N5–N1) and have it take effect immediately, so different learning stages show different "beyond-level" highlights.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|-------|------|------|
| AC-07a | User opens settings and changes JLPT level | Setting saved | New level applies to all subsequent sentences immediately |

---

### US-08: Learning Record Export

**As a user**, I want to export my learning records as CSV/JSON, so I can back up data or use other review tools.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|-------|------|------|
| AC-08a | User selects export | Export executes | CSV/JSON file generated containing all record fields |

---

### US-09: Learning Panel (History)

**As a user**, I want to search and sort my learning history by time/keyword, so I can quickly review past encounters.

**Acceptance Criteria:**

| # | Given | When | Then |
|---|-------|------|------|
| AC-09a | User opens learning panel | Database has records | Record list displayed |
| AC-09b | User searches/sorts | Filter applied | Records correctly filtered and sorted |

---

## P2 Stories

### US-10: Review System

**As a user**, I want a review function that suggests sentences I should revisit based on some algorithm.

**Status**: Algorithm TBD. Placeholder for future implementation.
