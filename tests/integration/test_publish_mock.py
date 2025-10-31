"""Contract tests for publishing against the mock BP Timer API."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from client.config import ClientConfig
from client.extract_boss import BossEvent
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


@pytest.fixture()
def publisher(monkeypatch):
    config = ClientConfig.load({"BPTIMER_BASE_URL": "http://testserver"})
    transport_client = httpx.Client(transport=httpx.MockTransport(_send), base_url="http://testserver")
    pub = BPTimerPublisher(config, client=transport_client)
    yield pub
    pub.close()


def _event(hp: float = 80.0) -> BossEvent:
    return BossEvent(
        event_type="tick",
        monster_id=80006,
        boss_name="Golden Juggernaut",
        hp_pct=hp,
        timestamp_ms=1710000000,
        channel=101,
        map_id=1101,
        instance_id="run-1",
    )


def test_publish_success(publisher: BPTimerPublisher) -> None:
    results = publisher.publish([_event(75.0)])
    assert len(results) == 1
    assert results[0].status_code == 200
    assert results[0].response_body["success"] is True


def test_publish_rejects_bad_api_key(monkeypatch) -> None:
    config = ClientConfig.load(
        {
            "BPTIMER_BASE_URL": "http://testserver",
            "BPTIMER_API_KEY": "deny-key",
        }
    )
    transport_client = httpx.Client(transport=httpx.MockTransport(_send), base_url="http://testserver")
    publisher = BPTimerPublisher(config, client=transport_client)
    try:
        results = publisher.publish([_event(60.0)])
        assert results[0].status_code == 403
        assert "Invalid" in (results[0].error or "") or results[0].response_body is not None
    finally:
        publisher.close()
