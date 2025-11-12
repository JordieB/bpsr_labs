"""Offline replay helper for BP Timer uploader."""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from client.config import ClientConfig
from client.run import _setup_logging, run_replay

_DEFAULT_SAMPLES = Path(__file__).resolve().parent / "samples" / "single_boss.jsonl"
_DEFAULT_MOCK_URL = "http://127.0.0.1:8000"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Replay captured frames into the BP Timer pipeline")
    parser.add_argument("--input", type=str, default=str(_DEFAULT_SAMPLES), help="JSONL sample file to replay")
    parser.add_argument("--target", choices=["mock", "bptimer"], default="mock")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    config = ClientConfig.load()
    if args.dry_run:
        config.dry_run = True
    if args.target == "mock":
        config.base_url = os.getenv("MOCK_BPTIMER_URL", _DEFAULT_MOCK_URL)
    _setup_logging(config.log_level)
    run_replay(config, Path(args.input))


if __name__ == "__main__":
    main()
