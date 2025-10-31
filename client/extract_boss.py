"""Boss HP extraction logic for BP Timer publishing."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from .decode import DecodedMessage

_DEFAULT_MAPPING_PATH = Path(__file__).resolve().parent.parent / "data" / "bptimer" / "boss_mapping.json"


@dataclass(slots=True)
class BossEvent:
    event_type: str  # start|tick|end
    monster_id: int
    boss_name: Optional[str]
    hp_pct: float
    timestamp_ms: int
    channel: Optional[int]
    map_id: Optional[int]
    instance_id: Optional[str]


@dataclass(slots=True)
class _BossState:
    monster_id: int
    boss_name: Optional[str]
    last_hp_pct: float = 100.0
    channel: Optional[int] = None
    map_id: Optional[int] = None
    instance_id: Optional[str] = None
    active: bool = False
    last_timestamp_ms: int = 0


class BossFightExtractor:
    """Track boss encounters and emit BP Timer compatible events."""

    def __init__(
        self,
        mapping_path: Path | None = None,
        tick_threshold: float = 0.5,
    ) -> None:
        mapping_file = mapping_path or _DEFAULT_MAPPING_PATH
        if not mapping_file.exists():
            raise FileNotFoundError(f"Boss mapping not found: {mapping_file}")
        self._boss_mapping = {
            int(key): value for key, value in json.loads(mapping_file.read_text(encoding="utf-8")).items()
        }
        self._states: Dict[int, _BossState] = {}
        self._tick_threshold = tick_threshold

    def reset(self) -> None:
        self._states.clear()

    def process(self, message: DecodedMessage) -> List[BossEvent]:
        events: List[BossEvent] = []
        timestamp_ms = self._extract_timestamp(message)
        for entity in self._iter_entities(message.data):
            monster_id = entity.get("monster_id")
            if monster_id is None:
                continue
            hp_pct = self._calculate_hp_pct(entity)
            if hp_pct is None:
                continue
            channel = entity.get("channel")
            map_id = entity.get("map_id")
            instance_id = entity.get("instance_id")
            boss_name = entity.get("boss_name") or self._boss_mapping.get(monster_id)

            state = self._states.get(monster_id)
            if state is None:
                state = _BossState(
                    monster_id=monster_id,
                    boss_name=boss_name,
                    channel=channel,
                    map_id=map_id,
                    instance_id=instance_id,
                )
                self._states[monster_id] = state

            # Update metadata if new info arrives
            if boss_name and not state.boss_name:
                state.boss_name = boss_name
            if channel:
                state.channel = channel
            if map_id:
                state.map_id = map_id
            if instance_id:
                state.instance_id = instance_id

            # Determine encounter transitions
            if not state.active and hp_pct < 100.0:
                events.append(
                    self._make_event(
                        "start",
                        state,
                        hp_pct,
                        timestamp_ms,
                    )
                )
                state.active = True
            elif state.active and hp_pct > state.last_hp_pct + 5:
                # Treat large HP increase as reset/start
                events.append(
                    self._make_event(
                        "end",
                        state,
                        state.last_hp_pct,
                        timestamp_ms,
                    )
                )
                events.append(
                    self._make_event(
                        "start",
                        state,
                        hp_pct,
                        timestamp_ms,
                    )
                )
            elif not state.active and hp_pct >= 100.0:
                # Idle entity - skip
                state.last_hp_pct = hp_pct
                state.last_timestamp_ms = timestamp_ms
                continue

            if state.active and abs(hp_pct - state.last_hp_pct) >= self._tick_threshold:
                events.append(
                    self._make_event(
                        "tick",
                        state,
                        hp_pct,
                        timestamp_ms,
                    )
                )

            if state.active and hp_pct <= 0.0:
                events.append(
                    self._make_event(
                        "end",
                        state,
                        0.0,
                        timestamp_ms,
                    )
                )
                state.active = False

            state.last_hp_pct = hp_pct
            state.last_timestamp_ms = timestamp_ms

        return events

    def _make_event(self, event_type: str, state: _BossState, hp_pct: float, timestamp_ms: int) -> BossEvent:
        return BossEvent(
            event_type=event_type,
            monster_id=state.monster_id,
            boss_name=state.boss_name,
            hp_pct=round(hp_pct, 2),
            timestamp_ms=timestamp_ms,
            channel=state.channel,
            map_id=state.map_id,
            instance_id=state.instance_id,
        )

    def _extract_timestamp(self, message: DecodedMessage) -> int:
        data = message.data
        for key in ("server_time_ms", "timestamp_ms", "server_time", "time"):
            value = data.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
        return int(time.time() * 1000)

    def _iter_entities(self, data: Dict) -> Iterator[Dict]:
        candidates = []
        for key in ("entities", "entity", "updates", "actors", "objects"):
            value = data.get(key)
            if isinstance(value, list):
                candidates.extend(value)
        if not candidates and isinstance(data, dict):
            candidates.append(data)
        for entity in candidates:
            if isinstance(entity, dict):
                normalised = self._normalise_entity(entity)
                if normalised:
                    yield normalised

    def _normalise_entity(self, entity: Dict) -> Optional[Dict]:
        result: Dict[str, Optional[int | float | str]] = {}
        monster_id = entity.get("monster_id") or entity.get("mob_id")
        if monster_id is None:
            info = entity.get("info") or entity.get("common_info")
            if isinstance(info, dict):
                monster_id = info.get("monster_id") or info.get("id")
        if monster_id is None:
            return None
        try:
            monster_id = int(monster_id)
        except (TypeError, ValueError):
            return None
        result["monster_id"] = monster_id

        for name_key in ("boss_name", "name", "display_name"):
            value = entity.get(name_key)
            if isinstance(value, str):
                result["boss_name"] = value
                break

        for channel_key in ("channel", "line", "channel_number"):
            value = entity.get(channel_key)
            if isinstance(value, int):
                result["channel"] = value
                break

        for map_key in ("map_id", "map", "zone_id"):
            value = entity.get(map_key)
            if isinstance(value, int):
                result["map_id"] = value
                break

        instance = entity.get("instance_id") or entity.get("instance")
        if isinstance(instance, str):
            result["instance_id"] = instance

        life = entity.get("life") or entity.get("hp") or entity.get("health")
        if isinstance(life, dict):
            result["_hp"] = life
        elif isinstance(entity.get("hp_pct"), (int, float)):
            result["hp_pct"] = float(entity["hp_pct"])
        elif isinstance(entity.get("hp_percent"), (int, float)):
            result["hp_pct"] = float(entity["hp_percent"])

        if "_hp" not in result and isinstance(entity.get("life"), (int, float)):
            result["hp_pct"] = float(entity["life"])

        return result

    def _calculate_hp_pct(self, entity: Dict) -> Optional[float]:
        if "hp_pct" in entity and isinstance(entity["hp_pct"], float):
            return max(0.0, min(100.0, entity["hp_pct"]))
        life = entity.get("_hp")
        if isinstance(life, dict):
            current = life.get("current") or life.get("current_hp") or life.get("hp")
            maximum = life.get("max") or life.get("max_hp") or life.get("max_hp_value")
            try:
                current_f = float(current)
                maximum_f = float(maximum)
            except (TypeError, ValueError):
                return None
            if maximum_f <= 0:
                return None
            return max(0.0, min(100.0, (current_f / maximum_f) * 100.0))
        return None


__all__ = ["BossEvent", "BossFightExtractor"]
