# BP Timer Ingestion Protocol

This document summarizes the ingestion contract implemented by Wuhee's BP Timer project as of commit `3faf648` and describes how the standalone uploader maps decoded BPSR packets to the API payload.

## Endpoint Overview

| Property | Value |
| --- | --- |
| HTTP Method | `POST` |
| Path | `/api/create-hp-report` |
| Authentication | `X-API-Key` header mapped to PocketBase `api_keys` collection |
| Success Response | `{"success": true}` |
| Error Responses | `400` (validation / duplicate), `403` (bad API key), `404` (boss/map missing), `429` (rate limited), `5xx` |

The handler is implemented in [`apps/pocketbase/pb_hooks/create-hp-report.pb.js`](../bptimer_repo/apps/pocketbase/pb_hooks/create-hp-report.pb.js). API keys are validated by [`api-key-auth.pb.js`](../bptimer_repo/apps/pocketbase/pb_hooks/api-key-auth.pb.js).

## Required Request Body Fields

| Field | Type | Notes |
| --- | --- | --- |
| `monster_id` | integer | Boss meter identifier from the game. Looked up in `BOSS_MAPPING`. |
| `hp_pct` | number | Must be between `0` and `100`. Only decreasing values are accepted per reporter within a 5 minute window. |
| `line` | integer | Channel (1-1000). Must not exceed the map's allowed channels. |

### Optional Fields (accepted by our uploader for observability)

While the upstream handler only requires the three fields above, the uploader includes additional metadata for downstream tooling:

- `boss_name`: Resolved human-readable boss name.
- `map_id`: Numeric map identifier when derivable from combat data.
- `instance_id`: Encounter instance identifier when available.
- `event_type`: One of `start`, `tick`, or `end`, indicating encounter lifecycle.
- `timestamp_ms`: Milliseconds since epoch extracted from the packet stream.

The mock server validates these optional fields but ignores them if they are absent or `null`.

## Rate Limiting & Validation Hooks

Relevant PocketBase hooks:

- [`rate-limit-bad-actors.pb.js`](../bptimer_repo/apps/pocketbase/pb_hooks/rate-limit-bad-actors.pb.js): Reporters with reputation below `-20` must wait 5 minutes between submissions unless whitelisted.
- [`prevent-duplicate-hp-reports.pb.js`](../bptimer_repo/apps/pocketbase/pb_hooks/prevent-duplicate-hp-reports.pb.js): Rejects duplicate HP values from the same reporter + boss + channel within 5 minutes and disallows HP increases.
- [`cleanup-hp-reports.pb.js`](../bptimer_repo/apps/pocketbase/pb_hooks/cleanup-hp-reports.pb.js): Periodic housekeeping of aged reports (no contract impact).
- [`create-mob-channel-status.pb.js`](../bptimer_repo/apps/pocketbase/pb_hooks/create-mob-channel-status.pb.js) and [`reset-mob-channel-status.pb.js`](../bptimer_repo/apps/pocketbase/pb_hooks/reset-mob-channel-status.pb.js): Maintain derived channel state consumed by the web frontend.

Our uploader respects these policies by:

1. Emitting monotonically decreasing HP percentages (`BossFightExtractor` drops increases except when treated as a reset).
2. Preserving per-boss state to avoid spamming unchanged ticks (configurable threshold 0.5%).
3. Replaying historical samples at natural cadence to avoid rate spikes.

## Boss Mapping

The canonical boss meter ID → name mapping lives in [`apps/pocketbase/pb_hooks/constants.js`](../bptimer_repo/apps/pocketbase/pb_hooks/constants.js). The uploader copies this mapping into `data/bptimer/boss_mapping.json` for offline usage.

## Packet → Payload Mapping

| Source (Decoded Message) | Derived Field | Notes |
| --- | --- | --- |
| `data.entities[].monster_id` | `monster_id` | The extractor tracks encounters per monster ID. |
| `data.entities[].hp_pct` or HP ratio from `life` | `hp_pct` | Converts current/max HP to percent when needed. Values are clamped to `[0, 100]`. |
| `data.entities[].channel`/`line` | `line` | Defaults to `1` if unavailable. |
| `data.entities[].map_id` | `map_id` | Optional metadata. |
| `data.entities[].instance_id` | `instance_id` | Optional metadata, passed through unchanged. |
| `message.data.timestamp_ms` or `server_time_ms` | `timestamp_ms` | Falls back to current wall clock when not present. |
| Boss mapping lookup | `boss_name` | Uses static mapping file; falls back to packet-provided name. |

The extractor emits three event types:

- `start`: First observation where HP < 100%.
- `tick`: Subsequent observations with ≥0.5% change from the previous tick.
- `end`: HP reaches 0% or the encounter resets (HP increases by >5%).

The publisher currently submits each event individually. If BP Timer adds batching support in the future the `ClientConfig.batch_size` option can be used to group events.

## Auth & Headers

- `X-API-Key`: Required for production ingestion. The mock server accepts any value except those beginning with `deny`.
- `Content-Type: application/json`: Required.
- Additional headers can be provided via `ClientConfig.extra_headers` (`EXTRA_HEADERS` env var as JSON).

## Retry Semantics

- 429 / 5xx responses trigger exponential backoff with jitter (base delay configurable via `RETRY_BACKOFF_SECONDS`).
- Network errors use the same retry loop up to `RETRY_MAX` attempts.
- Persistent failures are surfaced in the metrics file and structured logs.

## Known Gaps & Assumptions

- Encounter inference assumes a single HP bar per monster ID. Multi-phase fights that reuse IDs may require additional heuristics.
- Channel detection relies on decoded entity metadata; if the game omits channel info the uploader defaults to line `1` and logs a warning.
- Map → channel validation is performed by BP Timer; we surface 4xx responses but do not pre-validate channel counts locally.
- The `.jsonl` replay samples use decoded message fixtures rather than raw binary frames for portability. Frame parsing is still unit-tested separately.

For additional details see `docs/Design.md` and the inline module documentation under `client/`.
