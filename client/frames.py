"""Frame parsing utilities built on top of the core decoder."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

from bpsr_labs.packet_decoder.decoder.framing import FrameReader, NotifyFrame


@dataclass(slots=True)
class ParsedFrame:
    service_uid: int
    stub_id: int
    method_id: int
    payload: bytes
    was_compressed: bool
    offset: int


class FrameParser:
    """Thin wrapper around :class:`FrameReader` for client consumption."""

    def __init__(self) -> None:
        self._reader = FrameReader()

    def parse_bytes(self, data: bytes) -> Iterator[ParsedFrame]:
        for frame in self._reader.iter_notify_frames(data):
            yield self._convert(frame)

    def parse_stream(self, payloads: Iterable[bytes]) -> Iterator[ParsedFrame]:
        for payload in payloads:
            for frame in self._reader.iter_notify_frames(payload):
                yield self._convert(frame)

    @staticmethod
    def _convert(frame: NotifyFrame) -> ParsedFrame:
        return ParsedFrame(
            service_uid=frame.service_uid,
            stub_id=frame.stub_id,
            method_id=frame.method_id,
            payload=frame.payload,
            was_compressed=frame.was_compressed,
            offset=frame.offset,
        )


__all__ = ["FrameParser", "ParsedFrame"]
