"""HTTP publisher for BP Timer ingestion API."""
from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import httpx

from .config import ClientConfig
from .extract_boss import BossEvent

logger = logging.getLogger(__name__)

_ENDPOINT = "/api/create-hp-report"


@dataclass(slots=True)
class PublishResult:
    event: BossEvent
    status_code: int
    response_body: Optional[Dict]
    error: Optional[str] = None


class BPTimerPublisher:
    """Publish boss events to BP Timer with retries and backoff."""

    def __init__(self, config: ClientConfig, client: httpx.Client | None = None) -> None:
        self._config = config
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["X-API-Key"] = config.api_key
        headers.update({k: str(v) for k, v in config.extra_headers.items()})
        if client is not None:
            self._client = client
            self._owns_client = False
            self._client.headers.update(headers)
        else:
            self._client = httpx.Client(base_url=config.base_url, headers=headers, timeout=10.0)
            self._owns_client = True

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def publish(self, events: Iterable[BossEvent]) -> List[PublishResult]:
        results: List[PublishResult] = []
        batch: List[BossEvent] = []
        for event in events:
            batch.append(event)
            if len(batch) >= max(1, self._config.batch_size):
                results.extend(self._flush(batch))
                batch = []
        if batch:
            results.extend(self._flush(batch))
        return results

    def _flush(self, events: List[BossEvent]) -> List[PublishResult]:
        results: List[PublishResult] = []
        for event in events:
            payload = self._build_payload(event)
            if self._config.dry_run:
                logger.info("DRY-RUN would POST %s", json.dumps(payload, ensure_ascii=False))
                results.append(PublishResult(event=event, status_code=0, response_body=None))
                continue
            attempt = 0
            while True:
                attempt += 1
                try:
                    response = self._client.post(_ENDPOINT, json=payload)
                except httpx.HTTPError as exc:  # pragma: no cover - network errors are hard to simulate
                    error = str(exc)
                    logger.warning("Request failed: %s", error)
                    if attempt > self._config.retry_max:
                        results.append(
                            PublishResult(event=event, status_code=0, response_body=None, error=error)
                        )
                        break
                    self._backoff(attempt)
                    continue
                if response.status_code >= 500 or response.status_code == 429:
                    if attempt > self._config.retry_max:
                        results.append(
                            PublishResult(
                                event=event,
                                status_code=response.status_code,
                                response_body=self._safe_json(response),
                                error=f"Server error after {attempt} attempts",
                            )
                        )
                        break
                    logger.warning("Server responded with %s, retrying", response.status_code)
                    self._backoff(attempt)
                    continue
                results.append(
                    PublishResult(
                        event=event,
                        status_code=response.status_code,
                        response_body=self._safe_json(response),
                        error=None if response.is_success else response.text,
                    )
                )
                break
        return results

    def _build_payload(self, event: BossEvent) -> Dict[str, float | int | str]:
        line = event.channel or 1
        payload: Dict[str, float | int | str] = {
            "monster_id": event.monster_id,
            "hp_pct": round(event.hp_pct, 2),
            "line": line,
        }
        if event.instance_id:
            payload["instance_id"] = event.instance_id
        if event.map_id is not None:
            payload["map_id"] = event.map_id
        if event.boss_name:
            payload["boss_name"] = event.boss_name
        payload["event_type"] = event.event_type
        payload["timestamp_ms"] = event.timestamp_ms
        return payload

    @staticmethod
    def _safe_json(response: httpx.Response) -> Optional[Dict]:
        try:
            data = response.json()
        except ValueError:
            return None
        if isinstance(data, dict):
            return data
        return None

    def _backoff(self, attempt: int) -> None:
        delay = self._config.retry_backoff_seconds * (2 ** (attempt - 1))
        jitter = random.uniform(0.1, 0.5)
        time.sleep(delay + jitter)


__all__ = ["BPTimerPublisher", "PublishResult"]
