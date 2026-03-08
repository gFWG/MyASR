# Pipeline-Perf: Issues & Gotchas

## Known Issues (to watch for)
- SileroVAD ONNX mode: onnx=True may not be supported in all versions — fallback to PyTorch
- np.concatenate in VAD: O(n²) hotspot at 31 chunks/sec
- asyncio + QThread: need to create new event loop in QThread.run(), not reuse main loop
- `requests` library → must fully replace with httpx (no leftover requests.post calls)
- sqlite3 WAL mode: must enable PRAGMA journal_mode=WAL for concurrent access
