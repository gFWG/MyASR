The existing code running in Windows 11 encounters following bug/error/warning:

1. Any modification to "Settings-Model" is not saved.

The following improvements are proposed:

1. “Settings-Model” should support custom parsing formats(e.g. <tr></tr>), with the default being empty (returning the full output).

2. Supports two overlay display modes, which can be switched in Settings:
    - "Both" mode: Displays both the ASR result and LLM response in a single overlay.
    - "Single" mode: Displays only ASR result or LLM response, use shortcut keys to switch between them.

3. Supports context switching: Press a key to switch between the previous/next sentence.

4. Add shortcut key functionality and bind it in settings. Shortcut keys support the following functions:
    - "previous sentence": Switch to the previous sentence in the context.
    - "next sentence": Switch to the next sentence in the context.
    - "toggle display mode": Switch between "Both" and "Single" overlay display modes