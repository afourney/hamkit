# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Public packet models. Construction does not imply an available wire codec."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from .data import (
    Ambiguity,
    Beam,
    Capability,
    Compression,
    DefinitionValue,
    Extensions,
    Footprint,
    Grid,
    Location,
    NTSRecord,
    PositionEncoding,
    RawFields,
    ReplyAck,
    Symbol,
    Telemetry,
    Timestamp,
    Weather,
)
from .nmea import NMEAMetadata, NMEASentence

WireInput: TypeAlias = bytes | str
ValidationProfile: TypeAlias = Literal["monitor", "rf"]
CoordinateAxis: TypeAlias = Literal["latitude", "longitude"]
SpecificationProfile: TypeAlias = Literal[
    "core-1.1", "historical-1.0", "compatibility-fap"
]
UnsupportedPolicy: TypeAlias = Literal["opaque", "raise"]
MalformedPolicy: TypeAlias = Literal["raise", "opaque"]


@dataclass(frozen=True)
class DecodeOptions:
    """Payload recovery only; invalid outer envelopes always raise.

    max_depth counts third-party wrappers, not the outer packet. Resource-limit
    failures always raise. Non-core specification profiles are reserved and
    currently raise CodecNotImplemented, never silently behave as core.
    """

    unsupported: UnsupportedPolicy = "opaque"
    malformed: MalformedPolicy = "raise"
    max_depth: int = 4
    specification: SpecificationProfile = "core-1.1"


@dataclass(frozen=True)
class EncodeOptions:
    max_depth: int = 4
    specification: SpecificationProfile = "core-1.1"
    destination: Literal["derive", "require_match"] = "derive"


@dataclass(frozen=True)
class Hop:
    address: str
    repeated: bool = False


Path: TypeAlias = tuple[Hop, ...]


@dataclass(frozen=True)
class Header:
    source: str
    destination: str
    path: Path = ()


@dataclass(frozen=True)
class HeaderSemantics:
    """Optional interpretation, independent of the exact header tokens."""

    destination_grid: Grid | None = None
    destination_symbol: Symbol | None = None
    source_ssid_symbol: Symbol | None = None
    destination_ssid_route: int | None = None
    software_identifier: str | None = None
    q_construct: str | None = None


@dataclass(frozen=True)
class Position:
    """Position report with its own encoding, timestamp and messaging flags.

    tail is the unsliced wire suffix when extensions are not decoded. For
    structured extensions use comment for the remaining bytes and leave tail
    empty; encoders must never silently choose between competing sources.
    """

    latitude_deg: float
    longitude_deg: float
    symbol: Symbol = field(default_factory=Symbol)
    messaging: bool = False
    timestamp: Timestamp | None = None
    tail: bytes = b""
    encoding: PositionEncoding = "uncompressed"
    ambiguity: Ambiguity | None = None
    compression: Compression | None = None
    extensions: Extensions = field(default_factory=Extensions)
    comment: bytes = b""

    @property
    def location(self) -> Location:
        return Location(
            self.latitude_deg,
            self.longitude_deg,
            self.symbol,
            self.ambiguity,
            self.extensions,
            self.tail,
            self.comment,
        )

    @property
    def is_null_position(self) -> bool:
        return (
            self.latitude_deg == 0
            and self.longitude_deg == 0
            and self.symbol == Symbol("\\", ".")
        )


@dataclass(frozen=True)
class MicE:
    """Header-dependent position. Destination is jointly encoded with payload."""

    position: Location
    comment_bits: tuple[bool, bool, bool]
    comment_set: Literal["standard", "custom"] = "standard"
    dti: Literal[0x60, 0x27, 0x1C, 0x1D] = 0x60
    fix: Literal["current", "old", "unknown"] = "current"
    type_marker: bytes = b""
    grid: Grid | None = None
    grid_symbol: Symbol | None = None
    destination_raw: str | None = None
    longitude_offset: int | None = None


@dataclass(frozen=True)
class Object:
    name: str
    position: Location
    timestamp: Timestamp
    alive: bool = True
    name_raw: bytes | None = None
    legacy: bool = False

    encoding: PositionEncoding = "uncompressed"
    compression: Compression | None = None


@dataclass(frozen=True)
class Item:
    name: str
    position: Location
    alive: bool = True
    name_raw: bytes | None = None

    encoding: PositionEncoding = "uncompressed"
    compression: Compression | None = None


@dataclass(frozen=True)
class Definition:
    addressee: str
    definition: DefinitionValue
    values_raw: RawFields = ()


@dataclass(frozen=True)
class Status:
    text: bytes = b""
    timestamp: Timestamp | None = None
    grid: Grid | None = None
    symbol: Symbol | None = None
    beam: Beam | None = None


@dataclass(frozen=True)
class Message:
    addressee: str
    text: bytes = b""
    message_id: str | None = None
    reply_ack: ReplyAck | None = None

    @property
    def addressee_raw(self) -> str:
        return self.addressee.ljust(9)


@dataclass(frozen=True)
class Acknowledgment:
    addressee: str
    message_id: str
    rejected: bool = False
    reply_ack: ReplyAck | None = None


@dataclass(frozen=True)
class AutoAnswer:
    addressee: str
    text: bytes
    previous_ack: str | None = None


@dataclass(frozen=True)
class Bulletin:
    identifier: str
    text: bytes
    group: str | None = None
    announcement: bool = False
    legacy: bool = False


@dataclass(frozen=True)
class NWSBulletin:
    addressee: str
    text: bytes
    reference_id: str | None = None


@dataclass(frozen=True)
class Radiogram:
    addressee: str
    record: NTSRecord
    message_id: str | None = None


@dataclass(frozen=True)
class Query:
    """General or directed; open query name preserves unrecognized requests."""

    name: str
    addressee: str | None = None
    footprint: Footprint | None = None
    heard_station: str | None = None
    arguments: bytes = b""
    message_id: str | None = None


@dataclass(frozen=True)
class DirectStations:
    stations: tuple[str, ...]


@dataclass(frozen=True)
class HeardStation:
    station: str
    counts: tuple[int | None, ...]


@dataclass(frozen=True)
class Trace:
    header: Header


ResponseValue: TypeAlias = DirectStations | HeardStation | Trace


@dataclass(frozen=True)
class Response:
    addressee: str
    response: ResponseValue


@dataclass(frozen=True)
class Capabilities:
    tokens: tuple[Capability, ...]


@dataclass(frozen=True)
class NMEA:
    sentence: NMEASentence
    metadata: NMEAMetadata = field(default_factory=NMEAMetadata)
    position_usable: bool | None = None
    symbol: Symbol | None = None
    comment: bytes = b""


@dataclass(frozen=True)
class ThirdParty:
    packet: Packet


@dataclass(frozen=True)
class UserDefined:
    user_id: bytes
    user_type: bytes
    data: bytes


@dataclass(frozen=True)
class RawWeather:
    """Vendor layout is not specified here; retain the complete information field."""

    format: Literal["ultimeter_ii", "ultimeter_2000", "ultw", "peet_logging"]
    information: bytes
    weather: Weather | None = None  # Optional externally interpreted measurements.


@dataclass(frozen=True)
class Agrelo:
    bearing_deg: int
    quality_code: int
    raw: bytes | None = None


@dataclass(frozen=True)
class Maidenhead:
    grid: Grid
    symbol: Symbol | None = None
    comment: bytes = b""


@dataclass(frozen=True)
class LegacyPosition:
    """X1J prefix-position convention, only for the historical profile."""

    prefix: bytes
    position: Position


@dataclass(frozen=True)
class Beacon:
    text: bytes


@dataclass(frozen=True)
class Invalid:
    data: bytes


@dataclass(frozen=True)
class Reserved:
    dti: int
    data: bytes


@dataclass(frozen=True)
class ExternalExtension:
    """Named extension lacking an authoritative grammar in this baseline.

    This is deliberately raw, not a guessed polygon or vendor measurement API.
    It can also annotate object extensions through an outer application model.
    """

    name: Literal["polygon_line", "vendor", "other"]
    information: bytes
    specification_url: str | None = None


@dataclass(frozen=True)
class Diagnostic:
    code: Literal["unsupported", "malformed"]
    message: str


@dataclass(frozen=True)
class Opaque:
    information: bytes
    reason: str = field(default="unsupported data type", compare=False)
    diagnostic: Diagnostic | None = field(default=None, compare=False)


Payload: TypeAlias = (
    Position
    | MicE
    | Object
    | Item
    | Weather
    | Telemetry
    | Definition
    | Status
    | Message
    | Acknowledgment
    | AutoAnswer
    | Bulletin
    | NWSBulletin
    | Radiogram
    | Query
    | Response
    | Capabilities
    | NMEA
    | ThirdParty
    | UserDefined
    | RawWeather
    | Agrelo
    | Maidenhead
    | LegacyPosition
    | Beacon
    | Invalid
    | Reserved
    | ExternalExtension
    | Opaque
)


@dataclass(frozen=True)
class Packet:
    header: Header
    payload: Payload
    original_wire: bytes | None = field(default=None, compare=False, repr=False)
    header_semantics: HeaderSemantics | None = field(default=None, compare=False)


@dataclass(frozen=True)
class EncodedPacketFields:
    """Joint encoding result: use this header, not the original template header."""

    header: Header
    information: bytes
