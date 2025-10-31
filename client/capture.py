"""WinDivert capture helpers for the BP Timer client."""
from __future__ import annotations

import logging
import signal
import sys
from collections import defaultdict
from dataclasses import dataclass
from threading import Event
from typing import Dict, Iterable, Iterator, Tuple

try:
    import pydivert  # type: ignore
except Exception:  # pragma: no cover - pydivert is optional in non-Windows envs
    pydivert = None  # type: ignore


logger = logging.getLogger(__name__)

StreamKey = Tuple[str, int, str, int]


@dataclass(slots=True)
class CaptureStats:
    packets_seen: int = 0
    packets_filtered: int = 0
    streams_yielded: int = 0


class TCPStreamBuffer:
    """Simple TCP payload reassembler for ordered streams."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def push(self, data: bytes) -> bytes:
        if not data:
            return b""
        self._buffer.extend(data)
        chunk = bytes(self._buffer)
        self._buffer.clear()
        return chunk


class WinDivertCapture:
    """Context manager that yields TCP payloads captured with WinDivert."""

    def __init__(self, flt: str, graceful: bool = True) -> None:
        if pydivert is None or sys.platform != "win32":
            raise RuntimeError("WinDivert capture is only supported on Windows with pydivert installed")
        self._filter = flt
        self._handle: pydivert.WinDivert | None = None
        self._buffers: Dict[StreamKey, TCPStreamBuffer] = defaultdict(TCPStreamBuffer)
        self._shutdown = Event()
        if graceful:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        self.stats = CaptureStats()

    def _handle_signal(self, signum: int, _frame: object | None) -> None:
        logger.info("Received signal %s, stopping capture", signum)
        self._shutdown.set()
        if self._handle is not None:
            self._handle.close()

    def __enter__(self) -> "WinDivertCapture":
        logger.info("Starting WinDivert capture with filter: %s", self._filter)
        self._handle = pydivert.WinDivert(self._filter)
        self._handle.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if self._handle is not None:
            self._handle.close()
        self._shutdown.set()
        logger.info("Capture stopped")

    def iter_payloads(self) -> Iterator[Tuple[StreamKey, bytes]]:
        if self._handle is None:
            raise RuntimeError("WinDivert capture not started")
        for packet in self._handle:  # pragma: no cover - requires Windows
            if self._shutdown.is_set():
                break
            self.stats.packets_seen += 1
            if not packet.tcp:
                self.stats.packets_filtered += 1
                continue
            payload: bytes = getattr(packet.tcp, "payload", b"")  # type: ignore[attr-defined]
            if not payload:
                self.stats.packets_filtered += 1
                continue
            key: StreamKey = (
                str(packet.src_addr),
                int(packet.src_port),
                str(packet.dst_addr),
                int(packet.dst_port),
            )
            chunk = self._buffers[key].push(payload)
            if chunk:
                self.stats.streams_yielded += 1
                yield key, chunk


def iterate_tcp_payloads(data: Iterable[bytes]) -> Iterator[Tuple[StreamKey, bytes]]:
    """Utility iterator for offline pipelines mimicking WinDivert output."""

    buffer = TCPStreamBuffer()
    key: StreamKey = ("offline", 0, "offline", 0)
    for payload in data:
        chunk = buffer.push(payload)
        if chunk:
            yield key, chunk
