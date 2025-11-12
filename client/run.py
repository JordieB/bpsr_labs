"""CLI entry point for the standalone BP Timer uploader."""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import List

from .config import ClientConfig
from .decode import DecodedMessage, MessageDecoder
from .extract_boss import BossEvent, BossFightExtractor
from .frames import FrameParser
from .publish import BPTimerPublisher

logger = logging.getLogger(__name__)

_DEFAULT_MOCK_URL = "http://127.0.0.1:8000"


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _load_replay_messages(path: Path) -> List[DecodedMessage]:
    messages: List[DecodedMessage] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        messages.append(
            DecodedMessage(
                method_id=int(data.get("method_id", 0)),
                message_type=data.get("message_type", "mock"),
                data=data.get("data", {}),
            )
        )
    return messages


def _write_metrics(path: Path, metrics: dict) -> None:
    path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")


def run_live(config: ClientConfig) -> None:
    from .capture import WinDivertCapture

    parser = FrameParser()
    decoder = MessageDecoder()
    extractor = BossFightExtractor()
    publisher = BPTimerPublisher(config)
    metrics = {"frames": 0, "decoded": 0, "events": 0, "posted": 0}
    try:
        with WinDivertCapture(config.capture_filter) as capture:
            logger.info("Starting live capture. Press Ctrl+C to stop.")
            for _key, payload in capture.iter_payloads():
                for frame in parser.parse_bytes(payload):
                    metrics["frames"] += 1
                    for message in decoder.decode(frame):
                        metrics["decoded"] += 1
                        events = extractor.process(message)
                        if not events:
                            continue
                        metrics["events"] += len(events)
                        results = publisher.publish(events)
                        metrics["posted"] += sum(1 for r in results if r.status_code in {0, 200})
    finally:
        publisher.close()
        _write_metrics(config.metrics_path, metrics)


def run_replay(config: ClientConfig, input_path: Path) -> None:
    extractor = BossFightExtractor()
    publisher = BPTimerPublisher(config)
    metrics = {"frames": 0, "decoded": 0, "events": 0, "posted": 0}
    try:
        messages = _load_replay_messages(input_path)
        for message in messages:
            metrics["decoded"] += 1
            events = extractor.process(message)
            if not events:
                continue
            metrics["events"] += len(events)
            results = publisher.publish(events)
            metrics["posted"] += sum(1 for r in results if r.status_code in {0, 200})
    finally:
        publisher.close()
        _write_metrics(config.metrics_path, metrics)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Standalone BP Timer uploader")
    parser.add_argument("--mode", choices=["live", "replay"], required=True)
    parser.add_argument("--input", type=str, help="Path to sample JSONL file for replay mode")
    parser.add_argument("--target", choices=["bptimer", "mock"], default="mock")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads without sending")
    args = parser.parse_args(argv)

    config = ClientConfig.load()
    if args.dry_run:
        config.dry_run = True
    if args.target == "mock":
        config.base_url = os.getenv("MOCK_BPTIMER_URL", _DEFAULT_MOCK_URL)
    _setup_logging(config.log_level)

    print("This tool sends boss HP telemetry to BP Timer. Ensure you have consent to upload combat data.")

    if args.mode == "live":
        try:
            run_live(config)
        except RuntimeError as exc:
            logger.error("Live capture failed: %s", exc)
    else:
        if not args.input:
            raise SystemExit("--input is required for replay mode")
        input_path = Path(args.input)
        if not input_path.exists():
            raise SystemExit(f"Input file not found: {input_path}")
        run_replay(config, input_path)


if __name__ == "__main__":
    main()
