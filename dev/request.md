The existing code running in Windows 11 encounters following bug/error/warning:

1. The overlay shows "Translation unavailable" all the time, while test connection in Settings shows "Connected".

2. Sentence segmentation is incorrect, sometimes only fragments of sentences are present, and sometimes multiple sentences are joined together.

3. Terminal shows following error/warning:
'''
'(MaxRetryError("HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /Qwen/Qwen3-ASR-0.6B/resolve/main/config.json (Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1010)')))"), '(Request ID: 3cbd652b-39f6-4077-bd19-934682689edb)')' thrown while requesting HEAD https://huggingface.co/Qwen/Qwen3-ASR-0.6B/resolve/main/config.json
2026-03-09 15:12:33,069 huggingface_hub.utils._http WARNING '(MaxRetryError("HTTPSConnectionPool(host='huggingface.co', port=443): Max retries exceeded with url: /Qwen/Qwen3-ASR-0.6B/resolve/main/config.json (Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1010)')))"), '(Request ID: 3cbd652b-39f6-4077-bd19-934682689edb)')' thrown while requesting HEAD https://huggingface.co/Qwen/Qwen3-ASR-0.6B/resolve/main/config.json
Retrying in 1s [Retry 1/5].
2026-03-09 15:12:33,070 huggingface_hub.utils._http WARNING Retrying in 1s [Retry 1/5].
'''

The following improvements are proposed:

1. “Settings-Model” should support to retrieve the model list and allow users to select the model, instead of typing the model name manually.

2. "Settings-Model" should support more common settings, such as "Streaming", "Max Tokens", "Temperature", "Thinking", "Top P", "prefill".., and allow users to edit custom arguments by themselves.

3. Find an elegant way to support more local LLM providers, such as LM Studio. User can select them by entering URL and API key (if needed) in "Settings-Model".