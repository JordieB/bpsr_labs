"""End-to-end offline replay test using the mock server."""
from __future__ import annotations

from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from client.config import ClientConfig
from client.run import run_replay
from client.publish import BPTimerPublisher
from offline_test.mock_bptimer import app


_test_client = TestClient(app)


def _send(request: httpx.Request) -> httpx.Response:
    response = _test_client.request(
        request.method,
        request.url.path,
        headers=dict(request.headers),
        content=request.content,
    )
    return httpx.Response(
        status_code=response.status_code,
        headers=response.headers,
        content=response.content,
    )


class _TestPublisher(BPTimerPublisher):
    def __init__(self, config: ClientConfig) -> None:
        transport = httpx.MockTransport(_send)
        super().__init__(config, client=httpx.Client(transport=transport, base_url="http://testserver"))


def test_replay_to_mock(tmp_path, monkeypatch) -> None:
    sample = Path("offline_test/samples/single_boss.jsonl")
    metrics_path = tmp_path / "metrics.json"

    monkeypatch.setenv("BPTIMER_BASE_URL", "http://testserver")
    monkeypatch.setenv("METRICS_PATH", str(metrics_path))
    monkeypatch.delenv("DRY_RUN", raising=False)

    # Replace publisher factory with ASGI-backed version
    monkeypatch.setattr("client.run.BPTimerPublisher", _TestPublisher)

    config = ClientConfig.load()
    run_replay(config, sample)

    assert metrics_path.exists()
    metrics = metrics_path.read_text(encoding="utf-8")
    assert "posted" in metrics
