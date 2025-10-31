"""Tests for client frame parsing utilities."""
from __future__ import annotations

import struct

import zstandard

from client.frames import FrameParser
from client.decode import _RELEVANT_METHODS
from bpsr_labs.packet_decoder.decoder.combat_decode import SERVICE_UID


def _make_frame(payload: bytes, method_id: int = 0x0000002E, zstd: bool = False) -> bytes:
    body = struct.pack(">QII", SERVICE_UID, 1, method_id) + payload
    pkt_type = 0x0002
    if zstd:
        pkt_type |= 0x8000
        payload = zstandard.ZstdCompressor().compress(payload)
        body = struct.pack(">QII", SERVICE_UID, 1, method_id) + payload
    frame_len = 6 + len(body)
    header = struct.pack(">IH", frame_len, pkt_type)
    return header + body


def test_frame_parser_emits_parsed_frame() -> None:
    parser = FrameParser()
    payload = b"test-payload"
    frame_bytes = _make_frame(payload)
    frames = list(parser.parse_bytes(frame_bytes))
    assert len(frames) == 1
    parsed = frames[0]
    assert parsed.payload == payload
    assert parsed.method_id in _RELEVANT_METHODS
    assert parsed.was_compressed is False


def test_frame_parser_decompresses_zstd() -> None:
    parser = FrameParser()
    raw_payload = b"compressed-data"
    # _make_frame handles compression when zstd=True
    frame_bytes = _make_frame(raw_payload, zstd=True)
    frames = list(parser.parse_bytes(frame_bytes))
    assert len(frames) == 1
    parsed = frames[0]
    assert parsed.was_compressed is True
    assert parsed.payload == raw_payload
