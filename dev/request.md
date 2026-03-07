The existing code running in Windows 11 encounters following bug/error:

1. 
'''
2026-03-07 21:28:37,809 src.pipeline WARNING Audio queue full — dropping chunk (ASR may be falling behind)
'''

2. 
'''
2026-03-07 21:28:37,816 src.pipeline ERROR Failed to write sentence to database
Traceback (most recent call last):
  File "D:\github\MyASR\src\db\repository.py", line 42, in insert_sentence
    cursor = self._conn.execute(
             ^^^^^^^^^^^^^^^^^^^
sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread. The object was created in thread id 34652 and this is thread id 17984.

During handling of the above exception, another exception occurred:

                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\github\MyASR\src\db\repository.py", line 115, in insert_sentence
    self._conn.rollback()
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\github\MyASR\src\db\repository.py", line 115, in insert_sentence
    self._conn.rollback()
sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread. The object was created in thread id 34652 and this is thread id 17984.
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
2026-03-07 21:28:49,421 src.pipeline ERROR Failed to write sentence to database
Traceback (most recent call last):
  File "D:\github\MyASR\src\db\repository.py", line 42, in insert_sentence
    cursor = self._conn.execute(
             ^^^^^^^^^^^^^^^^^^^
sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread. The object was created in thread id 34652 and this is thread id 17984.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "D:\github\MyASR\src\pipeline.py", line 137, in run
    sentence_id, vocab_ids, grammar_ids = self._repo.insert_sentence(
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\github\MyASR\src\db\repository.py", line 115, in insert_sentence
    self._conn.rollback()
sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread. The object was created in thread id 34652 and this is thread id 17984.
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
2026-03-07 21:36:07,311 src.pipeline ERROR Failed to write sentence to database
Traceback (most recent call last):
  File "D:\github\MyASR\src\db\repository.py", line 42, in insert_sentence
    cursor = self._conn.execute(
             ^^^^^^^^^^^^^^^^^^^
sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread. The object was created in thread id 34652 and this is thread id 17984.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "D:\github\MyASR\src\pipeline.py", line 137, in run
    sentence_id, vocab_ids, grammar_ids = self._repo.insert_sentence(
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\github\MyASR\src\db\repository.py", line 115, in insert_sentence
    self._conn.rollback()
sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread. The object was created in thread id 34652 and this is thread id 17984.
'''