"""Helpers for resolving game item ids into human-readable labels."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

__all__ = [
    "ItemRecord",
    "build_mapping_from_sources",
    "load_item_mapping",
    "resolve_item_name",
]

_DEFAULT_SEARCH_LOCATIONS: tuple[Path, ...] = (
    Path("data/game-data/item_name_map.json"),
    Path("ref/StarResonanceData/item_name_map.json"),
    Path("ref/StarResonanceData/ztable/item_name_map.json"),
    Path("ref/StarResonanceData/ztable/ItemTable.json"),
)


@dataclass(frozen=True)
class ItemRecord:
    item_id: int
    name: str
    icon: Optional[str] = None


def _load_raw_mapping(path: Path) -> dict[int, ItemRecord]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)

    mapping: dict[int, ItemRecord] = {}
    if isinstance(payload, dict):
        for raw_key, value in payload.items():
            try:
                item_id = int(raw_key)
            except (TypeError, ValueError):
                continue

            if isinstance(value, dict):
                name = value.get("name") or value.get("Name")
                icon = value.get("icon") or value.get("Icon")
            else:
                name = str(value)
                icon = None

            if not isinstance(name, str) or not name:
                continue
            mapping[item_id] = ItemRecord(item_id=item_id, name=name, icon=icon)
    return mapping


def _load_from_item_table(path: Path) -> dict[int, ItemRecord]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    mapping: dict[int, ItemRecord] = {}
    if isinstance(payload, dict):
        for raw_key, value in payload.items():
            if not isinstance(value, dict):
                continue
            item_id = value.get("Id")
            name = value.get("Name")
            icon = value.get("Icon")
            if not isinstance(item_id, int) or not isinstance(name, str) or not name:
                try:
                    item_id = int(raw_key)
                except (TypeError, ValueError):
                    continue
            if not isinstance(name, str) or not name:
                continue
            mapping[int(item_id)] = ItemRecord(item_id=int(item_id), name=name, icon=icon if isinstance(icon, str) else None)
    return mapping


def build_mapping_from_sources(paths: Iterable[Path]) -> dict[int, ItemRecord]:
    """Construct a mapping from the provided candidate files.

    Unlike :func:`load_item_mapping`, this helper iterates over *all* supplied
    files and merges their contents. Later files in ``paths`` win when the same
    ``item_id`` appears multiple times.
    """

    merged: dict[int, ItemRecord] = {}
    for candidate in paths:
        if not candidate.is_file():
            continue
        try:
            if candidate.name.lower() == "itemtable.json":
                mapping = _load_from_item_table(candidate)
            else:
                mapping = _load_raw_mapping(candidate)
        except (OSError, json.JSONDecodeError):
            continue
        if not mapping:
            continue
        merged.update(mapping)
    return merged


@lru_cache(maxsize=1)
def load_item_mapping(search_paths: Iterable[Path] | None = None) -> dict[int, ItemRecord]:
    """Attempt to load an item id → :class:`ItemRecord` mapping.

    Parameters
    ----------
    search_paths:
        Optional iterable of paths to probe. When omitted, a default set of
        repository-relative locations is used.
    """

    paths = list(search_paths) if search_paths is not None else list(_DEFAULT_SEARCH_LOCATIONS)
    mapping = build_mapping_from_sources(paths)
    return mapping


def resolve_item_name(item_id: int) -> Optional[str]:
    mapping = load_item_mapping()
    record = mapping.get(item_id)
    if record is None:
        return None
    return record.name
