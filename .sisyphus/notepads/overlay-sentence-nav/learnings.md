## [2026-03-11] Session: ses_324a3c746fferuqVjypB72iPXD - Initial Codebase Analysis

### Package structure
- Imports: `from src.pipeline.types import ...`, `from src.db.models import ...`
- QThread workers: constructor → run() loop with _running flag → stop() sets _running=False
- Signals: typed as `Signal(object, object)` etc., connect via `worker.signal.connect(handler)`
- queue.Queue[T] between pipeline stages, put_nowait() to emit, get(timeout=0.1) to receive

### Key files and patterns
- ASRResult: `src/pipeline/types.py` — frozen dataclass with text,segment_id,elapsed_ms,db_row_id
- SentenceResult: `src/db/models.py` — japanese_text, analysis:AnalysisResult, sentence_id:int|None, highlight_vocab_ids, highlight_grammar_ids
- AnalysisResult: tokens:list[Token], vocab_hits:list[VocabHit], grammar_hits:list[GrammarHit]
- LearningRepository: insert_sentence(record,vocab,grammar) -> tuple[int,list[int],list[int]]
- PreprocessingPipeline: process(text) -> AnalysisResult; needs AppConfig for construction
- AppConfig: dataclass with user_jlpt_level, db_path, overlay_display_mode (to remove), etc.

### OverlayWindow layout
- outer_layout (VBox, margins 8,8,8,8, spacing 2)
  - addStretch(1)
  - content_layout (HBox, no margins, spacing 4): prev_btn + _jp_browser(stretch=1) + next_btn
  - addStretch(1)
- _jp_browser: QTextBrowser with mouse tracking, viewport has event filter installed

### QThread worker pattern
```python
class FooWorker(QThread):
    signal = Signal(object)
    error_occurred = Signal(str)
    
    def __init__(self, ...):
        super().__init__()
        self._running = False
        
    def run(self):
        self._running = True
        while self._running:
            try:
                item = self._queue.get(timeout=0.1)
                # process item
                self.signal.emit(result)
            except queue.Empty:
                continue
            except Exception as e:
                self.error_occurred.emit(str(e))
    
    def stop(self):
        self._running = False
        self.quit()
        self.wait(2000)
```

### Database pattern
- Thread-local: `threading.local()`, create repo per run() invocation
- insert_sentence() returns (sentence_id, vocab_ids, grammar_ids) 

### Lazy imports
```python
import importlib  # noqa: PLC0415
```
Use `# noqa: PLC0415` for lazy imports inside functions

### Ruff conventions
- line-length=99, double quotes
- isort with src as first-party

