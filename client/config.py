"""Configuration loader for the standalone BP Timer client."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

_DEFAULT_ENV_PATHS = (
    Path.cwd() / ".env",
    Path(__file__).resolve().parent.parent / ".env",
)


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_json(value: str | None) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _load_env_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not path.exists() or not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


@dataclass(slots=True)
class ClientConfig:
    """Runtime configuration for the BP Timer uploader."""

    base_url: str = "https://api.bptimer.com"
    api_key: Optional[str] = None
    capture_filter: str = "tcp and tcp.PayloadLength > 0"
    log_level: str = "INFO"
    retry_max: int = 5
    retry_backoff_seconds: float = 1.0
    metrics_path: Path = field(default_factory=lambda: Path("metrics.json"))
    dry_run: bool = False
    batch_size: int = 1
    extra_headers: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, env: Optional[Dict[str, str]] = None) -> "ClientConfig":
        """Load configuration from environment variables and optional `.env` file."""

        merged_env: Dict[str, str] = {}
        for candidate in _DEFAULT_ENV_PATHS:
            merged_env.update(_load_env_file(candidate))
        if env is None:
            merged_env.update(os.environ)
        else:
            merged_env.update(env)

        config = cls()
        config.base_url = merged_env.get("BPTIMER_BASE_URL", config.base_url)
        config.api_key = merged_env.get("BPTIMER_API_KEY", config.api_key)
        config.capture_filter = merged_env.get("CAPTURE_FILTER", config.capture_filter)
        config.log_level = merged_env.get("LOG_LEVEL", config.log_level)
        config.retry_max = _parse_int(merged_env.get("RETRY_MAX"), config.retry_max)
        config.retry_backoff_seconds = float(
            merged_env.get("RETRY_BACKOFF_SECONDS", config.retry_backoff_seconds)
        )
        metrics_path = merged_env.get("METRICS_PATH")
        if metrics_path:
            config.metrics_path = Path(metrics_path)
        config.dry_run = _parse_bool(merged_env.get("DRY_RUN"), config.dry_run)
        config.batch_size = _parse_int(merged_env.get("BATCH_SIZE"), config.batch_size)
        config.extra_headers = _parse_json(merged_env.get("EXTRA_HEADERS"))
        return config


__all__ = ["ClientConfig"]
