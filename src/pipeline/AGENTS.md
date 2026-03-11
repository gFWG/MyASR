# PIPELINE ARCHITECTURE

## OVERVIEW
The pipeline manages real-time audio acquisition, voice activity detection, and batch speech recognition. It uses a multi-threaded architecture with thread-safe queues and Qt signals for inter-stage communication.

## STRUCTURE
- `orchestrator.py`: Coordinator that creates workers, manages queues, and wires signals.
- `vad_worker.py`: QThread consuming audio chunks to produce `SpeechSegment` objects.
- `asr_worker.py`: QThread performing batched ASR on segments to produce `ASRResult`.
- `types.py`: Frozen dataclasses (`SpeechSegment`, `ASRResult`) for type-safe data transfer.
- `perf.py`: Utilities for timing pipeline stages and collecting metrics.

## DATA FLOW
1. **Capture**: `WasapiLoopbackCapture` (Windows-only) feeds raw PCM into `audio_queue`.
2. **VAD**: `VadWorker` reads from `audio_queue`, runs Silero VAD, and puts results in `segment_queue`.
3. **ASR**: `AsrWorker` collects batch of segments from `segment_queue`, flushes to Qwen-ASR.
4. **Signal**: `asr_ready` signal emitted with `ASRResult` for UI consumption.

## CONVENTIONS
- **QThread Workers**: Each stage is a worker thread. Communication is via `queue.Queue` or Qt signals.
- **Non-blocking Puts**: Workers use `put_nowait()`. If a queue is full, data is dropped to prevent pipeline stalls.
- **Frozen Dataclasses**: All inter-thread data structures are immutable.
- **Batching**: ASR is performed in batches (default size 4 or 500ms timeout) for efficiency.

## ANTI-PATTERNS
- **No Direct Calls**: Never call worker methods directly from other threads. Use signals.
- **No Blocking**: Do not perform blocking operations in the orchestrator or UI thread.
- **No Streaming ASR**: The pipeline is designed for batch processing after VAD segmentation.

## NOTES
- Processing speed must exceed acquisition speed to maintain real-time performance.
- Orchestrator currently hardwires WASAPI for system audio loopback on Windows 11.
