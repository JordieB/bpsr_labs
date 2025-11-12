# Standalone BP Timer Uploader Design

## Overview

The standalone client ingests Blue Protocol Star Resonance combat traffic, extracts boss health telemetry, and delivers structured reports to BP Timer without relying on `bpsr-logs`. The implementation is organized as a modular pipeline:

```
WinDivert (live) / JSONL samples (replay)
          │
          ▼
    client.capture
          │ raw TCP payloads
          ▼
    client.frames
          │ parsed RPC frames
          ▼
    client.decode
          │ decoded protobuf messages
          ▼
    client.extract_boss
          │ BP Timer events (start/tick/end)
          ▼
    client.publish → BP Timer / mock server
```

## Components

- **`client.config`** – Loads runtime options from environment variables and optional `.env` files. Exposes `ClientConfig` with retry/batch logging parameters.
- **`client.capture`** – WinDivert wrapper that reassembles TCP payloads. Provides an offline helper to mimic WinDivert output when replaying fixtures.
- **`client.frames`** – Wraps the existing `FrameReader` to expose a simple iterator that yields `ParsedFrame` dataclasses.
- **`client.decode`** – Builds on `CombatDecoderV2`, filtering for combat RPCs and returning normalized `DecodedMessage` structures.
- **`client.extract_boss`** – Maintains per-monster state, derives HP percentages, and emits `BossEvent` objects aligned with BP Timer semantics.
- **`client.publish`** – HTTP client with exponential backoff, optional dry-run logging, batching, and metrics collection.
- **`client.run`** – CLI entry point orchestrating live capture or offline replay (`python -m client.run`).
- **`offline_test`** – Contains `replay.py`, `mock_bptimer.py`, and sample fixtures. Enables end-to-end validation without game traffic.

## Assumptions & Limitations

- Only combat RPCs decoded by the existing descriptor set are processed. Unknown service UIDs are ignored.
- Boss identification is driven by the canonical mapping from BP Timer. Unmapped `monster_id` values will still emit events but without `boss_name`.
- HP resets are inferred when the observed percentage jumps upward by more than 5%. This heuristic may need tuning once live data is available.
- Channel numbers are not validated locally. The upstream API enforces per-map channel ranges.
- Live capture requires administrative privileges and the WinDivert driver. When unavailable, the client exits with a descriptive error.

## Metrics & Observability

- Structured logs (JSON compatible) are emitted via Python's logging module.
- A `metrics.json` file summarises processed frames, decoded messages, emitted events, and successful publishes.
- `--dry-run` mode surfaces would-be payloads without hitting the network, facilitating offline verification.

## Future Enhancements

- Adaptive batching and deduplication to align with BP Timer rate limits once documented.
- Additional heuristics for multi-phase encounters (e.g., per-phase IDs or HP multipliers).
- PyInstaller spec for packaging into a Windows executable (stub configuration prepared but not part of this MVP).
