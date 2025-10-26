"""Frame parsing utilities for BPSR captures."""

from __future__ import annotations

import io
import struct
from collections import Counter
from dataclasses import dataclass
from typing import Generator, Iterable, Iterator, Optional

import zstandard

__all__ = [
    "NotifyFrame",
    "FrameReader",
]

_HEADER_SIZE = 6
_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
_NOTIFY_FRAGMENT = 0x0002
_FRAMEDOWN_FRAGMENT = 0x0006


@dataclass
class NotifyFrame:
    """Decoded Notify frame contents."""

    service_uid: int
    stub_id: int
    method_id: int
    payload: bytes
    was_compressed: bool
    offset: int


class FrameReader:
    """Incrementally parses raw capture bytes into Notify frames.

    The parser is resilient to malformed data by sliding a single byte at a time
    until a plausible header is located. Nested FrameDown fragments are parsed
    recursively, and zstd compression is handled with the streaming API when the
    payload starts with the zstd magic header.
    """

    def __init__(self) -> None:
        self.bytes_scanned: int = 0
        self.frames_parsed: int = 0
        self.resync_events: int = 0
        self.notify_frames: int = 0
        self.fragment_histogram: Counter[int] = Counter()
        self.zstd_flag_without_magic: int = 0

    def iter_notify_frames(self, data: bytes) -> Iterator[NotifyFrame]:
        """Yield :class:`NotifyFrame` objects from the provided capture bytes."""

        self.bytes_scanned += len(data)
        yield from self._parse_stream(memoryview(data))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _parse_stream(self, view: memoryview) -> Iterator[NotifyFrame]:
        offset = 0
        length = len(view)
        while offset + _HEADER_SIZE <= length:
            frame_len = struct.unpack_from(">I", view, offset)[0]
            pkt_type = struct.unpack_from(">H", view, offset + 4)[0]
            fragment_type = pkt_type & 0x7FFF
            is_zstd = bool(pkt_type & 0x8000)

            if frame_len < _HEADER_SIZE:
                offset += 1
                self.resync_events += 1
                continue

            end = offset + frame_len
            if end > length:
                offset += 1
                self.resync_events += 1
                continue

            body = view[offset + _HEADER_SIZE : end]
            self.frames_parsed += 1
            self.fragment_histogram[fragment_type] += 1

            if fragment_type == _NOTIFY_FRAGMENT:
                notify = self._parse_notify(bytes(body), is_zstd, offset)
                if notify is not None:
                    self.notify_frames += 1
                    yield notify
            elif fragment_type == _FRAMEDOWN_FRAGMENT:
                # FrameDown bodies begin with an additional u32 server sequence id
                if len(body) >= 4:
                    nested_payload = bytes(body[4:])
                    nested_payload, _ = self._maybe_decompress(nested_payload, is_zstd)
                    if nested_payload:
                        yield from self._parse_stream(memoryview(nested_payload))
                else:
                    # malformed FrameDown payload, attempt to resync
                    self.resync_events += 1
            # Other fragment types are ignored for this study

            offset = end

    def _parse_notify(self, body: bytes, is_zstd: bool, frame_offset: int) -> Optional[NotifyFrame]:
        if len(body) < 16:
            self.resync_events += 1
            return None

        service_uid = struct.unpack_from(">Q", body, 0)[0]
        stub_id = struct.unpack_from(">I", body, 8)[0]
        method_id = struct.unpack_from(">I", body, 12)[0]
        payload = body[16:]
        payload, was_decompressed = self._maybe_decompress(payload, is_zstd)
        return NotifyFrame(
            service_uid=service_uid,
            stub_id=stub_id,
            method_id=method_id,
            payload=payload,
            was_compressed=was_decompressed,
            offset=frame_offset,
        )

    def _maybe_decompress(self, data: bytes, flagged: bool) -> tuple[bytes, bool]:
        if not flagged or not data:
            return data, False
        if not data.startswith(_ZSTD_MAGIC):
            self.zstd_flag_without_magic += 1
            return data, False

        # Limit decompression size to prevent resource exhaustion
        max_decompressed_size = 10 * 1024 * 1024  # 10MB limit
        try:
            decompressor = zstandard.ZstdDecompressor(max_window_size=2**23)  # 8MB window
            with decompressor.stream_reader(io.BytesIO(data)) as reader:
                chunks: list[bytes] = []
                total_size = 0
                while True:
                    chunk = reader.read(16384)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > max_decompressed_size:
                        self.resync_events += 1  # Count as resync for oversized decompression
                        return data, False
                    chunks.append(chunk)
        except zstandard.ZstdError:
            self.resync_events += 1
            return data, False
        return b"".join(chunks), True
