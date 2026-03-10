Existing bugs running in Windows 11:

1. (Fatal) Shortcuts do not work, and the following error is thrown in the console:
'''
2026-03-09 23:00:47,003 pynput.keyboard.GlobalHotKeys ERROR Unhandled exception in listener callback
Traceback (most recent call last):
  File "D:\miniconda3\envs\myasr\Lib\site-packages\pynput\_util\__init__.py", line 230, in inner
    return f(self, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\miniconda3\envs\myasr\Lib\site-packages\pynput\keyboard\_win32.py", line 329, in _process
    self.on_press(key, injected)
  File "D:\miniconda3\envs\myasr\Lib\site-packages\pynput\_util\__init__.py", line 146, in inner
    if f(*args) is False:
       ^^^^^^^^
  File "D:\miniconda3\envs\myasr\Lib\site-packages\pynput\keyboard\__init__.py", line 237, in _on_press
    hotkey.press(self.canonical(key))
  File "D:\miniconda3\envs\myasr\Lib\site-packages\pynput\keyboard\__init__.py", line 194, in press
    self._on_activate()
  File "D:\github\MyASR\src\ui\shortcuts.py", line 106, in _callback
    QMetaObject.invokeMethod(self, slot_name.encode(), Qt.ConnectionType.QueuedConnection)
ValueError: 'PySide6.QtCore.QMetaObject.invokeMethod' called with wrong argument values:
  PySide6.QtCore.QMetaObject.invokeMethod(<src.ui.shortcuts.GlobalShortcutManager(0x1de170b5710) at 0x000001DE289D1740>, b'_emit_toggle_display', <ConnectionType.QueuedConnection: 2>)
Found signature:
  PySide6.QtCore.QMetaObject.invokeMethod(object: PySide6.QtCore.QObject, member: bytes | bytearray | memoryview, type: PySide6.QtCore.Qt.ConnectionType, /, val0: PySide6.QtCore.QGenericArgumentHolder = {}, val1: PySide6.QtCore.QGenericArgumentHolder = {}, val2: PySide6.QtCore.QGenericArgumentHolder = {}, val3: PySide6.QtCore.QGenericArgumentHolder = {}, val4: PySide6.QtCore.QGenericArgumentHolder = {}, val5: PySide6.QtCore.QGenericArgumentHolder = {}, val6: PySide6.QtCore.QGenericArgumentHolder = {}, val7: PySide6.QtCore.QGenericArgumentHolder = {}, val8: PySide6.QtCore.QGenericArgumentHolder = {}, val9: PySide6.QtCore.QGenericArgumentHolder = {})
Traceback (most recent call last):
  File "D:\github\MyASR\src\main.py", line 142, in _on_config_changed
    overlay.on_config_changed(new_config)
  File "D:\github\MyASR\src\ui\overlay.py", line 247, in on_config_changed
    self._shortcut_mgr.update_shortcuts(config)
  File "D:\github\MyASR\src\ui\shortcuts.py", line 143, in update_shortcuts
    self.stop()
  File "D:\github\MyASR\src\ui\shortcuts.py", line 137, in stop
    self._hotkeys.join()
  File "D:\miniconda3\envs\myasr\Lib\site-packages\pynput\_util\__init__.py", line 305, in join
    six.reraise(exc_type, exc_value, exc_traceback)
  File "D:\miniconda3\envs\myasr\Lib\site-packages\six.py", line 723, in reraise
    raise value.with_traceback(tb)
  File "D:\miniconda3\envs\myasr\Lib\site-packages\pynput\_util\__init__.py", line 230, in inner
    return f(self, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\miniconda3\envs\myasr\Lib\site-packages\pynput\keyboard\_win32.py", line 329, in _process
    self.on_press(key, injected)
  File "D:\miniconda3\envs\myasr\Lib\site-packages\pynput\_util\__init__.py", line 146, in inner
    if f(*args) is False:
       ^^^^^^^^
  File "D:\miniconda3\envs\myasr\Lib\site-packages\pynput\keyboard\__init__.py", line 237, in _on_press
    hotkey.press(self.canonical(key))
  File "D:\miniconda3\envs\myasr\Lib\site-packages\pynput\keyboard\__init__.py", line 194, in press
    self._on_activate()
  File "D:\github\MyASR\src\ui\shortcuts.py", line 106, in _callback
    QMetaObject.invokeMethod(self, slot_name.encode(), Qt.ConnectionType.QueuedConnection)
ValueError: 'PySide6.QtCore.QMetaObject.invokeMethod' called with wrong argument values:
  PySide6.QtCore.QMetaObject.invokeMethod(<src.ui.shortcuts.GlobalShortcutManager(0x1de170b5710) at 0x000001DE289D1740>, b'_emit_toggle_display', <ConnectionType.QueuedConnection: 2>)
Found signature:
  PySide6.QtCore.QMetaObject.invokeMethod(object: PySide6.QtCore.QObject, member: bytes | bytearray | memoryview, type: PySide6.QtCore.Qt.ConnectionType, /, val0: PySide6.QtCore.QGenericArgumentHolder = {}, val1: PySide6.QtCore.QGenericArgumentHolder = {}, val2: PySide6.QtCore.QGenericArgumentHolder = {}, val3: PySide6.QtCore.QGenericArgumentHolder = {}, val4: PySide6.QtCore.QGenericArgumentHolder = {}, val5: PySide6.QtCore.QGenericArgumentHolder = {}, val6: PySide6.QtCore.QGenericArgumentHolder = {}, val7: PySide6.QtCore.QGenericArgumentHolder = {}, val8: PySide6.QtCore.QGenericArgumentHolder = {}, val9: PySide6.QtCore.QGenericArgumentHolder = {})
'''

Possible bugs running in Windows 11:

1. The component for checking regular expressions in "Parse Format" is not functioning. A red text prompt stating “Invalid Regex!” should appear below the input field after saving if the regex is invalid, but currently no prompt appears even for invalid regexes.

The following improvements are proposed:

1. When switching to single mode, the overlay should shrink accordingly, as only one text display box is required.

2. In the Settings > Shortcuts interface, a button to reset to default values should be added.

3. All four corners of the overlay should be resizable, not just the bottom-right corner.

4. In the Settings > Appearance interface, add an interactive feature to set colors for each JLPT level.

Checklist:

1. [x] Fix the fatal bug causing shortcuts to not work in Windows 11.
2. [x] Investigate and fix the issue with regex validation in the "Parse Format" component.
3. [x] Implement the proposed improvements to the overlay and settings interface.
4. [x] Test the application thoroughly to ensure all bugs are fixed and improvements are working as intended.
5. [x] No mypy/ruff errors should be present in the codebase after the changes.
6. [x] Update documentation to reflect any changes made to the application.

