# Decisions — pipeline-perf

## [2026-03-08] Session Start

### Key Architecture Decisions (from plan)
1. Pipeline types as frozen stdlib dataclasses (NOT pydantic)
2. Each worker is a QThread subclass with injected dependencies (testability)
3. Queue maxsizes: audio_queue=1000, segment_queue=20, text_queue=50, result_queue=50
4. AsyncOllamaClient uses httpx with streaming, LRU cache maxsize=256
5. num_predict reduced 512→200, timeout 30s→15s
6. VAD stays on CPU (no GPU sharing with ASR)
7. asyncio event loop created inside LLMWorker.run() — not shared
8. Old src/pipeline.py deleted after Task 10 orchestrator is complete
9. WASAPI optimization: resample_poly preferred over scipy.signal.resample (polyphase faster for 3:1 ratio 48k→16k)
10. soxr is optional (fall back to scipy if unavailable)
