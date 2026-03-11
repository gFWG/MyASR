## [2026-03-11] Session: ses_324a3c746fferuqVjypB72iPXD - Architecture Decisions

### T1: AnalysisWorker positioning
- Placed between AsrWorker and UI; reads from text_queue that AsrWorker puts ASRResult into
- Owns its own DB interaction (create LearningRepository per run() invocation, thread-local)
- Emits SentenceResult (fully populated from DB)

### T3: Dual-browser overlay design
- _preview_browser: above content_layout (shows "browsing" sentence)
- _jp_browser: below (shows live ASR stream / history being browsed)
- _browsing=True: user is browsing history, _preview_browser shows latest, _jp_browser shows browsed sentence
- LIVE mode: only _jp_browser visible, shows latest sentence with full rendering
- BROWSE mode: both visible, _preview_browser shows latest (preview), _jp_browser shows history sentence

### T6: DB responsibility shift
- Remove DB from AsrWorker entirely; AnalysisWorker owns all DB writes
- ASRResult.db_row_id field kept but never populated (None always)
- This simplifies AsrWorker to pure ASR logic

