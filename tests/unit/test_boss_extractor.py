"""Unit tests for boss event extraction."""
from __future__ import annotations

from client.decode import DecodedMessage
from client.extract_boss import BossEvent, BossFightExtractor


def _message(hp: float, timestamp: int) -> DecodedMessage:
    return DecodedMessage(
        method_id=0x2E,
        message_type="mock",
        data={
            "timestamp_ms": timestamp,
            "entities": [
                {
                    "monster_id": 80006,
                    "boss_name": "Golden Juggernaut",
                    "hp_pct": hp,
                    "channel": 101,
                    "map_id": 1101,
                    "instance_id": "run-1",
                }
            ],
        },
    )


def test_extractor_emits_start_tick_end_sequence() -> None:
    extractor = BossFightExtractor()
    events: list[BossEvent] = []
    events.extend(extractor.process(_message(99.0, 1000)))
    events.extend(extractor.process(_message(75.0, 1500)))
    events.extend(extractor.process(_message(0.0, 2000)))

    event_types = [event.event_type for event in events]
    assert event_types.count("start") == 1
    assert event_types.count("tick") >= 2
    assert event_types[-1] == "end"
    assert events[-1].hp_pct == 0.0


def test_extractor_handles_hp_reset() -> None:
    extractor = BossFightExtractor()
    extractor.process(_message(80.0, 1000))
    # HP increase triggers end + new start
    events = extractor.process(_message(90.0, 1200))
    types = [event.event_type for event in events]
    assert types == ["end", "start", "tick"]
