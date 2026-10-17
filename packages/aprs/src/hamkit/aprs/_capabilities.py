# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Discover codec availability without confusing model coverage with support."""
from dataclasses import dataclass
from typing import Literal, TypeAlias

from . import _models as m

SupportLevel: TypeAlias = Literal["implemented", "partial", "unimplemented", "raw"]


@dataclass(frozen=True)
class CodecSupport:
    """Which directions of the wire codec exist for one payload model."""

    model: type[m.Payload]
    decode: SupportLevel
    encode: SupportLevel
    notes: str


_SUPPORT: tuple[CodecSupport, ...] = (
    CodecSupport(
        m.Position,
        "partial",
        "partial",
        "Uncompressed, unambiguous positions. Undecoded extensions stay in comment.",
    ),
    CodecSupport(
        m.Status,
        "partial",
        "partial",
        "Text and DHM UTC timestamp; structured grid/symbol/beam are not encoded.",
    ),
    CodecSupport(
        m.Message,
        "partial",
        "partial",
        "Text, message ID and reply-ack; bulletins and other specialized messages "
        "are separate families.",
    ),
    CodecSupport(
        m.Acknowledgment, "implemented", "implemented", "ack/rej including reply-ack."
    ),
    CodecSupport(
        m.MicE,
        "unimplemented",
        "unimplemented",
        "Requires the packet header: the destination carries latitude and message bits.",
    ),
    CodecSupport(
        m.ThirdParty,
        "implemented",
        "implemented",
        "Bounded nesting; inner codec support still applies.",
    ),
    CodecSupport(
        m.UserDefined,
        "implemented",
        "implemented",
        "User ID/type and arbitrary binary data; no interpretation of user data.",
    ),
    CodecSupport(
        m.Invalid,
        "implemented",
        "implemented",
        "Explicit invalid/test DTI, never a trusted position.",
    ),
    CodecSupport(
        m.Reserved,
        "unimplemented",
        "raw",
        "Explicit DTI/data construction; decoding unknown DTIs returns Opaque.",
    ),
    CodecSupport(
        m.Opaque,
        "raw",
        "raw",
        "Unsupported content only; malformed input has a separate recovery result.",
    ),
    *(
        CodecSupport(
            model,
            "unimplemented",
            "unimplemented",
            "Model and JSON only; the wire codec raises CodecNotImplementedError.",
        )
        for model in (
            m.Object,
            m.Item,
            m.Weather,
            m.Telemetry,
            m.TelemetryDefinition,
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


def codec_support() -> tuple[CodecSupport, ...]:
    """Per-model support; 'partial' is not a promise for every value."""
    return _SUPPORT


def codec_support_for(value: m.Payload | type[m.Payload]) -> CodecSupport:
    model = value if isinstance(value, type) else type(value)
    for cls in model.__mro__:
        for support in _SUPPORT:
            if support.model is cls:
                return support
    raise TypeError("not a public APRS payload model")
