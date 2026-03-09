# Pipeline-Perf: Architectural Decisions

## Accepted Design Decisions (from Metis review)
- Preprocessing (fugashi) runs in ASR thread (~2ms, simpler)
- DB writes: INSERT at ASR (translation=NULL), UPDATE when LLM completes
- Threading: QThread subclass pattern (consistent with existing)
- LLM: fail fast, no retry
- VAD: inject SileroVAD (don't instantiate inside worker)

## Queue Sizes
- audio_queue → VAD: exists (maxsize=1000 currently, source of overflow)
- segment_queue (VAD→ASR): maxsize=20
- text_queue (ASR→LLM): maxsize=50
- result_queue (LLM→UI): maxsize=50

## Guards
- G1: Never block audio thread (VAD ≤32ms)
- G2: Graceful degradation: ASR text shows even if LLM fails
- G3: Shutdown order: audio → VAD → ASR → LLM (reverse of startup)
- G4: No shared mutable state — queues + signals only
- G5: Bounded queues (documented above)
- G6: Thread-safe config — no UI-thread mutation of worker state
