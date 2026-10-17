# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Discover codec availability without confusing model coverage with support."""

from dataclasses import dataclass
from typing import Literal, TypeAlias, cast

from . import _models as m

SupportLevel: TypeAlias = Literal["implemented", "partial", "unimplemented", "raw"]


@dataclass(frozen=True)
class CodecSupport:
    """Which directions of the wire codec exist for one payload model."""

    model: type[m.Payload]
    decode: SupportLevel
    encode: SupportLevel
    notes: str


_SUPPORT: tuple[CodecSupport, ...] = tuple(
    CodecSupport(model, cast(SupportLevel, decode), cast(SupportLevel, encode), notes)
    for model, decode, encode, notes in (
        (
            m.Position,
            "implemented",
            "implemented",
            "Uncompressed, ambiguous and compressed positions with structured extensions.",
        ),
        (
            m.MicE,
            "implemented",
            "implemented",
            "Destination-dependent latitude/message; serialization requires a matching header.",
        ),
        (
            m.Status,
            "implemented",
            "implemented",
            "Text, timestamp, grid/symbol and beam/ERP.",
        ),
        (
            m.Message,
            "implemented",
            "implemented",
            "Message IDs and reply acknowledgments.",
        ),
        (
            m.Acknowledgment,
            "implemented",
            "implemented",
            "ack/rej including reply-ack.",
        ),
        (m.ThirdParty, "implemented", "implemented", "Bounded nesting."),
        (
            m.UserDefined,
            "implemented",
            "implemented",
            "User ID/type and arbitrary data.",
        ),
        (m.Invalid, "implemented", "implemented", "Explicit invalid/test information."),
        (
            m.Reserved,
            "raw",
            "raw",
            "Unassigned DTIs decode as Opaque; explicit Reserved values can be composed.",
        ),
        (
            m.Opaque,
            "raw",
            "raw",
            "Unknown information retained without invented semantics.",
        ),
        (
            m.Object,
            "implemented",
            "implemented",
            "Named live/killed objects, positions and extensions.",
        ),
        (
            m.Item,
            "implemented",
            "implemented",
            "Named live/killed items, positions and extensions.",
        ),
        (
            m.Weather,
            "implemented",
            "implemented",
            "Weather observations; absent and unavailable fields remain distinct.",
        ),
        (
            m.Telemetry,
            "implemented",
            "implemented",
            "Classic telemetry and context-specific extension encodings.",
        ),
        (
            m.TelemetryDefinition,
            "implemented",
            "implemented",
            "PARM, UNIT, EQNS and BITS definitions.",
        ),
        (
            m.AutoAnswer,
            "implemented",
            "implemented",
            "Automatic answers with previous acknowledgment.",
        ),
        (
            m.Bulletin,
            "implemented",
            "implemented",
            "Bulletins, announcements and groups.",
        ),
        (
            m.NWSBulletin,
            "implemented",
            "implemented",
            "NWS bulletins with reference IDs.",
        ),
        (m.Radiogram, "implemented", "implemented", "NTS records."),
        (
            m.Query,
            "implemented",
            "implemented",
            "General/directed queries, footprints and operands.",
        ),
        (
            m.Response,
            "implemented",
            "implemented",
            "Direct stations, hourly heard counts and trace headers.",
        ),
        (m.Capabilities, "implemented", "implemented", "Ordered capability tokens."),
        (
            m.NMEA,
            "implemented",
            "implemented",
            "GGA, GLL, RMC, VTG and WPL; checksum recomputed on send.",
        ),
        (
            m.RawWeather,
            "partial",
            "raw",
            "Vendor information authoritative; Ultimeter 2000 numeric fields decoded.",
        ),
        (m.Agrelo, "implemented", "implemented", "Bearing and quality."),
        (m.Maidenhead, "implemented", "implemented", "Historical grid beacons."),
        (
            m.LegacyPosition,
            "implemented",
            "implemented",
            "X1J prefix with position within the first forty bytes.",
        ),
        (m.Beacon, "implemented", "implemented", "Recognized non-APRS beacons."),
        (
            m.ExternalExtension,
            "raw",
            "raw",
            "Explicit extension bytes; no invented external grammar.",
        ),
    )
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
