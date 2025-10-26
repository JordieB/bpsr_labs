"""Decode Blue Protocol trading-center listings from capture fragments."""

from __future__ import annotations

import io
import json
import struct
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, List, Optional

import zstandard
from blackboxprotobuf import decode_message  # provided via the bbpb package

from bpsr_labs.packet_decoder.decoder.item_catalog import ItemRecord, load_item_mapping


@dataclass
class Listing:
    frame_offset: int
    server_sequence: int
    price_luno: int
    quantity: int
    item_config_id: Optional[int]
    raw_entry: dict

    def to_dict(
        self, resolver: Optional[Callable[[int], Optional[ItemRecord]]] = None
    ) -> dict:
        payload = {
            "price_luno": self.price_luno,
            "quantity": self.quantity,
            "item_id": self.item_config_id,
        }
        metadata = {
            "frame_offset": self.frame_offset,
            "server_sequence": self.server_sequence,
            "raw_entry": self.raw_entry,
        }
        if resolver is not None and self.item_config_id is not None:
            resolved = resolver(self.item_config_id)
            if resolved is not None:
                payload["item_name"] = resolved.name
                if resolved.icon:
                    metadata["item_icon"] = resolved.icon
        payload["metadata"] = metadata
        return payload


_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def read_varint(data: bytes, start: int) -> tuple[int, int]:
    """Decode a protobuf-style varint from *data* starting at *start*."""

    shift = 0
    value = 0
    pos = start
    while pos < len(data):
        b = data[pos]
        value |= (b & 0x7F) << shift
        pos += 1
        if not (b & 0x80):
            return value, pos
        shift += 7
    raise ValueError("Unexpected end of buffer while decoding varint")


def maybe_decompress(data: bytes, is_zstd: bool) -> bytes:
    if not is_zstd or not data:
        return data
    if not data.startswith(_ZSTD_MAGIC):
        return data
    decompressor = zstandard.ZstdDecompressor(max_window_size=2**23)
    try:
        return decompressor.decompress(data)
    except zstandard.ZstdError:
        with decompressor.stream_reader(io.BytesIO(data)) as reader:
            return reader.read()


def iter_frames(data: bytes) -> Iterator[tuple[int, int, int, bool, bytes]]:
    """Yield (offset, length, pkt_type, is_zstd, body) tuples for each fragment."""

    offset = 0
    end = len(data)
    while offset + 6 <= end:
        length = struct.unpack_from(">I", data, offset)[0]
        if length == 0 or offset + length > end:
            offset += 1
            continue
        pkt_type = struct.unpack_from(">H", data, offset + 4)[0]
        body = data[offset + 6 : offset + length]
        is_zstd = bool(pkt_type & 0x8000)
        yield offset, length, pkt_type & 0x7FFF, is_zstd, body
        offset += length


def extract_listing_blocks(data: bytes) -> List[Listing]:
    listings: list[Listing] = []
    for frame_offset, length, fragment_type, is_zstd, body in iter_frames(data):
        if fragment_type != 0x0006:  # FrameDown
            continue
        if len(body) <= 4:
            continue
        server_seq = struct.unpack_from(">I", body, 0)[0]
        nested = maybe_decompress(body[4:], is_zstd)
        if not nested:
            continue

        idx = 0
        while idx < len(nested):
            try:
                field = nested[idx]
            except IndexError:
                break
            if field != 0x0A:  # length-delimited field no.1
                idx += 1
                continue
            try:
                msg_len, next_idx = read_varint(nested, idx + 1)
            except ValueError:
                idx += 1
                continue
            end = next_idx + msg_len
            if end > len(nested):
                break
            segment = nested[idx:end]
            idx = end

            try:
                decoded, typedef = decode_message(segment)
            except Exception:
                continue

            inner = decoded.get("1")
            if not isinstance(inner, dict):
                continue
            entries = inner.get("2")
            if not isinstance(entries, list) or not entries:
                continue

            added = 0
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                price = entry.get("1")
                quantity = entry.get("2")
                details = entry.get("3") if isinstance(entry.get("3"), dict) else None
                if (
                    not isinstance(price, int)
                    or not isinstance(quantity, int)
                    or not isinstance(details, dict)
                    or "2" not in details
                ):
                    continue
                item_id = details.get("2")
                listings.append(
                    Listing(
                        frame_offset=frame_offset,
                        server_sequence=server_seq,
                        price_luno=price,
                        quantity=quantity,
                        item_config_id=item_id if isinstance(item_id, int) else None,
                        raw_entry=entry,
                    )
                )
                added += 1

            if added:
                print(
                    f"Detected trade listing block in FrameDown @0x{frame_offset:06x} "
                    f"(server_seq={server_seq}, entries={added})"
                )
    return listings


def consolidate(
    listings: Iterable[Listing],
    resolver: Optional[Callable[[int], Optional[ItemRecord]]] = None,
) -> list[dict]:
    dedup: "OrderedDict[tuple[int, int, Optional[int]], Listing]" = OrderedDict()
    for entry in listings:
        key = (entry.item_config_id, entry.price_luno, entry.quantity)
        dedup.setdefault(key, entry)
    return [entry.to_dict(resolver=resolver) for entry in dedup.values()]


def main() -> None:
    capture_path = Path("ref/server_to_client.bin")
    data = capture_path.read_bytes()
    listings = extract_listing_blocks(data)
    if not listings:
        print("No trade listings detected")
        return

    mapping = load_item_mapping()
    if not mapping:
        print(
            "Warning: item name mapping not found; output will include item ids only.",
        )

    def resolver(item_id: int) -> Optional[ItemRecord]:
        return mapping.get(item_id)

    consolidated = consolidate(listings, resolver=resolver if mapping else None)
    print(json.dumps(consolidated, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
