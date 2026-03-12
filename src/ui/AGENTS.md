# UI LAYER KNOWLEDGE BASE

## OVERVIEW

PySide6 UI layer — transparent frameless overlay, hover tooltips, settings, tray management, and learning history. Follows Microsoft Design System principles with semi-transparent rounded-corner widgets.

## STRUCTURE

| File | Role |
|------|------|
| `overlay.py` | Primary transparent QWidget with `WindowStaysOnTop`, `WA_TranslucentBackground`. |
| `tooltip.py` | Floating `TooltipPopup` for JLPT hits. Emits `record_triggered` for history. |
| `highlight.py` | `HighlightRenderer` builds rich HTML from analysis with JLPT color-coding. |
| `settings.py` | `SettingsDialog` for app config (JLPT level, VAD, UI colors, opacity). |
| `tray.py` | `SystemTrayManager` with programmatic icon and context menu. |
| `learning_panel.py` | History browser with search, date filters, and pagination. |
| `sentence_detail.py` | `SentenceDetailDialog` for viewing saved sentence annotations. |

## SIGNAL MAP

| Component | Signal | Purpose |
|-----------|--------|---------|
| `OverlayWindow` | `highlight_hovered(hit, pos)` | Triggered on mouse hover over highlighted text. |
| `TooltipPopup` | `record_triggered(type, id)` | Emitted when a highlight is first shown in a sentence. |
| `SettingsDialog` | `config_changed(config)` | Broadcasts updated `AppConfig` to the application. |
| `SystemTrayManager` | `settings_requested` | User clicked 'Settings' in tray. |
| `SystemTrayManager` | `history_requested` | User clicked 'Learning History' in tray. |
| `SystemTrayManager` | `toggle_overlay` | User clicked 'Show/Hide Overlay' in tray. |

## CONVENTIONS

- **Main wiring**: `src/main.py` connects all inter-component signals (e.g., `OverlayWindow.highlight_hovered` -> `TooltipPopup.show_for_*`).
- **Transparency**: Overlay uses `WA_TranslucentBackground` and `setWindowOpacity`.
- **Styling**: Rich HTML text in `QTextBrowser` handles color-coded JLPT levels (N1–N5).
- **Navigation**: Overlay supports history navigation via translucent arrow buttons.

## NOTES

- UI state (width, height) is persisted to `config.json` via `QTimer` on resize.
- `TooltipPopup` performs deduplication to avoid redundant database records.
