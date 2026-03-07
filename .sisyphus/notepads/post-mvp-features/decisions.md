# Decisions — post-mvp-features

## [2026-03-07] Session: ses_338159831ffeMBBIHplN3ISroQ

### Architecture Decisions
- Config thread safety: queue.Queue[AppConfig] approach (NOT QMetaObject.invokeMethod)
- Centering HTML: table-based (`<table align="center"><tr><td>`) NOT display:inline-block
- QSizeGrip resize: Try first, fallback to manual 8px edge detection if flags conflict
- SQLite: WAL mode, separate connections per thread
- Single SettingsDialog instance: store reference, raise_/activateWindow if visible
- Dynamic WHERE SQL: conditional clause building (safe parameterized)
- Debounced resize save: QTimer.singleShot(500ms) on resizeEvent, flush on closeEvent
- OverlayWindow: Change constructor from `__init__(self, user_level)` to `__init__(self, config: AppConfig)`
- Badge polling: TODO(F4) comment only — no timer implemented
- QuitOnLastWindowClosed: False (set BEFORE any window.show())

### Tray Review Badge
- Stub: menu item disabled with "(coming soon)" text
- update_review_badge(count) exists as stub method — never called in this feature set
