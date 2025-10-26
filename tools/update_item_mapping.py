#!/usr/bin/env python3
"""Regenerate the item id → name mapping from Star Resonance data dumps."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bpsr_labs.packet_decoder.decoder.item_catalog import (
    ItemRecord,
    build_mapping_from_sources,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_SOURCE_ROOTS: tuple[Path, ...] = (Path("ref/StarResonanceData"),)
DEFAULT_PATTERNS: tuple[str, ...] = (
    "item_name_map.json",
    "ItemTable.json",
    "itemtable.json",
)


def _iter_candidate_files(sources: Sequence[Path]) -> Iterable[Path]:
    for source in sources:
        if source.is_file():
            yield source
            continue
        if not source.exists():
            LOGGER.debug("Skipping missing source %s", source)
            continue
        if not source.is_dir():
            LOGGER.debug("Skipping non-file, non-directory source %s", source)
            continue
        for pattern in DEFAULT_PATTERNS:
            for match in sorted(source.rglob(pattern)):
                if match.is_file():
                    yield match


def _serialize(mapping: dict[int, ItemRecord], indent: int | None) -> str:
    serializable: OrderedDict[str, dict[str, str]] = OrderedDict()
    for item_id in sorted(mapping):
        record = mapping[item_id]
        entry: dict[str, str] = {"name": record.name}
        if record.icon:
            entry["icon"] = record.icon
        serializable[str(item_id)] = entry
    return json.dumps(serializable, ensure_ascii=False, indent=indent) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        "-s",
        action="append",
        type=Path,
        help="Directory or file to scan for Star Resonance item tables.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/game-data/item_name_map.json"),
        help="Destination path for the generated mapping (default: %(default)s).",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indentation level for the JSON output (default: %(default)s).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress informational logging output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    logging.basicConfig(level=logging.INFO if not args.quiet else logging.WARNING)

    source_roots = tuple(args.source) if args.source else DEFAULT_SOURCE_ROOTS
    candidates = list(_iter_candidate_files(source_roots))
    if not candidates:
        LOGGER.error("No candidate files discovered under: %s", ", ".join(str(p) for p in source_roots))
        return 1

    LOGGER.info("Discovered %d candidate file(s)", len(candidates))
    mapping = build_mapping_from_sources(candidates)
    if not mapping:
        LOGGER.error("Failed to construct mapping from candidates. Check source data integrity.")
        return 1

    LOGGER.info("Compiled %d unique item entries", len(mapping))

    output_path: Path = args.output
    if output_path.exists() and output_path.is_dir():
        LOGGER.error("Output path %s is a directory", output_path)
        return 1
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = _serialize(mapping, indent=args.indent)
    output_path.write_text(payload, encoding="utf-8")
    LOGGER.info("Wrote mapping to %s", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
