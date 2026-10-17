# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Small, explicit bridge to the docs corpus; never equate opaque with accept."""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from hamkit.aprs import Message, Packet, Position, Status

Vector = dict[str, Any]


def load_vectors(path: Path, *, profile: str) -> Iterator[Vector]:
    """Read JSON or Markdown fixtures using their declared profile and byte carrier."""
    if path.suffix == ".json":
        cases = json.loads(path.read_text())
    else:
        cases = [
            json.loads(block)
            for block in re.findall(r"```json\n(.*?)\n```", path.read_text(), re.DOTALL)
        ]
    for case in cases:
        if "id" not in case or case.get("profile") != profile:
            continue
        if "packet" in case:
            raw = case["packet"].encode("latin-1")
            if len(raw) != case["packet_length_bytes"]:
                raise ValueError(f"incorrect byte length: {case['id']}")
            if "packet_hex" in case and raw != bytes.fromhex(case["packet_hex"]):
                raise ValueError(f"incorrect hex: {case['id']}")
        yield case


def semantic_fields(packet: Packet) -> Vector:
    """Only implemented semantics. Extend deliberately as codecs are added."""
    result: Vector = {
        "header": {
            "source": packet.header.source,
            "destination": packet.header.destination,
            "path": [
                {"address": h.address, "repeated_marker": h.repeated}
                for h in packet.header.path
            ],
        }
    }
    payload = packet.payload
    if isinstance(payload, Status):
        result.update(kind="status", status_text=payload.text)
    elif isinstance(payload, Message):
        result.update(
            kind="message",
            message={
                "addressee": payload.addressee,
                "addressee_raw": payload.addressee.ljust(9),
                "text": payload.text,
                "message_id": payload.message_id,
            },
        )
    elif isinstance(payload, Position):
        result.update(
            kind="position",
            format="uncompressed",
            messaging=payload.messaging,
            position={
                "latitude_deg": payload.latitude_deg,
                "longitude_deg": payload.longitude_deg,
                "ambiguity_digits": payload.ambiguity,
            },
            symbol={
                "table_id_raw": payload.symbol.table_id,
                "table": payload.symbol.table,
                "code": payload.symbol.code,
                "overlay": payload.symbol.overlay,
            },
            comment=payload.comment,
        )
    else:
        raise NotImplementedError(f"no semantic adapter for {type(payload).__name__}")
    return result
