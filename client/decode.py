"""Message decoding and routing helpers for boss extraction."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, Optional

from bpsr_labs.packet_decoder.decoder.combat_decode import NotifyFrame
from bpsr_labs.packet_decoder.decoder.combat_decode_v2 import CombatDecoderV2

from .frames import ParsedFrame

# Method identifiers known to carry combat state.
_RELEVANT_METHODS = {
    0x00000006,  # SyncNearEntities
    0x00000015,  # SyncContainerData
    0x00000016,  # SyncContainerDirtyData
    0x0000002B,  # SyncServerTime
    0x0000002D,  # SyncNearDeltaInfo
    0x0000002E,  # SyncToMeDeltaInfo
}


@dataclass(slots=True)
class DecodedMessage:
    method_id: int
    message_type: str
    data: Dict


class MessageDecoder:
    """Decode parsed frames using the combat protobuf descriptors."""

    def __init__(self) -> None:
        self._decoder = CombatDecoderV2()

    def decode(self, frame: ParsedFrame) -> Optional[DecodedMessage]:
        if frame.method_id not in _RELEVANT_METHODS:
            return None
        record = self._decoder.decode(
            NotifyFrame(
                service_uid=frame.service_uid,
                stub_id=frame.stub_id,
                method_id=frame.method_id,
                payload=frame.payload,
                was_compressed=frame.was_compressed,
                offset=frame.offset,
            )
        )
        if record is None:
            return None
        return DecodedMessage(
            method_id=record.method_id,
            message_type=record.message_type,
            data=record.data,
        )

    def decode_many(self, frames: Iterable[ParsedFrame]) -> Iterator[DecodedMessage]:
        for frame in frames:
            decoded = self.decode(frame)
            if decoded is not None:
                yield decoded


__all__ = ["DecodedMessage", "MessageDecoder"]
