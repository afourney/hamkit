# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Discover codec availability without confusing model coverage with support."""
from dataclasses import dataclass
from typing import Literal, TypeAlias

from . import models as m

SupportLevel: TypeAlias = Literal["implemented", "partial", "unimplemented", "raw"]


@dataclass(frozen=True)
class CodecCapability:
    model: type[m.Payload]
    decode: SupportLevel
    encode: SupportLevel
    notes: str


_CAPABILITIES: tuple[CodecCapability, ...] = (
    CodecCapability(
        m.Position,
        "partial",
        "partial",
        "Uncompressed/unambiguous only; structured extensions are not encoded. Tail is uninterpreted.",
    ),
    CodecCapability(
        m.Status,
        "partial",
        "partial",
        "Text/DHM UTC only; structured grid/symbol/beam are not encoded.",
    ),
    CodecCapability(
        m.Message,
        "partial",
        "partial",
        "Basic printable text/ID only; no reply-ack or specialized message semantics.",
    ),
    CodecCapability(
        m.Acknowledgment, "partial", "partial", "Basic ack/rej only; no reply-ack."
    ),
    CodecCapability(
        m.MicE,
        "unimplemented",
        "unimplemented",
        "Requires header; future joint encoding derives or checks destination.",
    ),
    CodecCapability(
        m.ThirdParty,
        "implemented",
        "implemented",
        "Bounded nesting; inner codec capabilities still apply.",
    ),
    CodecCapability(
        m.UserDefined,
        "implemented",
        "implemented",
        "User ID/type and arbitrary binary data; no interpretation of user data.",
    ),
    CodecCapability(
        m.Invalid,
        "implemented",
        "implemented",
        "Explicit invalid/test DTI, never a trusted position.",
    ),
    CodecCapability(
        m.Reserved,
        "unimplemented",
        "raw",
        "Explicit DTI/data construction; decoding unknown DTIs returns Opaque by default.",
    ),
    CodecCapability(
        m.Opaque,
        "raw",
        "raw",
        "Unsupported raw content only; malformed input has a separate recovery result.",
    ),
    *(
        CodecCapability(
            model,
            "unimplemented",
            "unimplemented",
            "Public representation only; wire codec raises CodecNotImplemented.",
        )
        for model in (
            m.Object,
            m.Item,
            m.Weather,
            m.Telemetry,
            m.Definition,
            m.AutoAnswer,
            m.Bulletin,
            m.NWSBulletin,
            m.Radiogram,
            m.Query,
            m.Response,
            m.Capabilities,
            m.NMEA,
            m.RawWeather,
            m.Agrelo,
            m.Maidenhead,
            m.LegacyPosition,
            m.Beacon,
            m.ExternalExtension,
        )
    ),
)


def get_capabilities() -> tuple[CodecCapability, ...]:
    """Immutable per-model capabilities; 'partial' is not a per-value guarantee."""
    return _CAPABILITIES


def capability_for(value: m.Payload | type[m.Payload]) -> CodecCapability:
    model = value if isinstance(value, type) else type(value)
    for capability in _CAPABILITIES:
        if capability.model is model:
            return capability
    raise TypeError("not a public APRS payload model")
