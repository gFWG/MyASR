I need to modify the translation and explanation features of the LLM.
After modification: Users select “Translation/Explanation” in “Settings.” When choosing “Translation,” users can use shortcut keys to switch between the original Japanese text and the translation. When choosing “Explanation,” users can use shortcut keys to switch between the original Japanese text and the explanation. Accordingly, different prompt templates will be used directly based on the user's settings, rather than sentence complexity. Users can customize these two sets of prompt templates in Settings.

Checklist
1. Implement the above functionality on top of the existing code
2. Completely remove components no longer needed after code modifications
3. Add new tests and ensure all tests pass
4. Synchronously update all relevant documentation