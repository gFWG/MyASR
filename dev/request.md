Existing bugs running in Windows 11:

1. When exiting the program, the following error is thrown in the console:
'''
asyncio ERROR Task was destroyed but it is pending!
task: <Task pending name='Task-144' coro=<<async_generator_athrow without __name__>()>>
'''

2. The shortcut to switch Previous/Next sentence is not working.

Possible bugs running in Windows 11:

1. Two files (data\myasr.db-shm, data\myasr.db-wal) are generated and never deleted.

The following improvements are proposed:

1. Shortcut keys should be placed in a separate tab within the settings.

2. Shortcut keys should be bound to keyboard buttons rather than manually inputting key combinations.

3. For all settings with only two options(e.g. LLM Mode, Display Mode..), a toggle button should be used instead of a dropdown list.

4. The settings interface does not close automatically after pressing the "Save" button.

5. If the "Parse Format" is an invaild regex, a red text prompt stating “Invalid Regex!” should appear below the input field after saving.

6. The shortcut to toggle display should only take effect whrn the "Display Mode" is set to "single" and it should not change the display mode to "single" if it is currently set to "both".