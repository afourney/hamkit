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
from .model_validation import Validated
from .nmea import NMEAMetadata, NMEASentence

WireInput: TypeAlias = bytes | str
ValidationProfile: TypeAlias = Literal["monitor", "rf"]
CoordinateAxis: TypeAlias = Literal["latitude", "longitude"]
SpecificationProfile: TypeAlias = Literal[
    "core-1.1", "historical-1.0", "compatibility-fap"
]
UnsupportedPolicy: TypeAlias = Literal["opaque", "raise"]
MalformedPolicy: TypeAlias = Literal["return", "raise"]


@dataclass(frozen=True)
class DecodeOptions(Validated):
    """Malformed inputs return a top-level recovery result by default.

    max_depth counts third-party wrappers, not the outer packet. Resource-limit
    failures always raise. Non-core specification profiles are reserved and
    currently raise CodecNotImplemented, never silently behave as core.
    """

    unsupported: UnsupportedPolicy = "opaque"
    malformed: MalformedPolicy = "return"
    max_depth: int = 4
    specification: SpecificationProfile = "core-1.1"


@dataclass(frozen=True)
class EncodeOptions(Validated):
    max_depth: int = 4
    specification: SpecificationProfile = "core-1.1"
    destination: Literal["derive", "require_match"] = "derive"


@dataclass(frozen=True)
class Hop(Validated):
    address: str
    repeated: bool = False


Path: TypeAlias = tuple[Hop, ...]


@dataclass(frozen=True)
class Header(Validated):
    source: str
    destination: str
    path: Path = ()


@dataclass(frozen=True)
class HeaderSemantics(Validated):
    """Optional interpretation, independent of the exact header tokens."""

    destination_grid: Grid | None = None
    destination_symbol: Symbol | None = None
    source_ssid_symbol: Symbol | None = None
    destination_ssid_route: int | None = None
    software_identifier: str | None = None
    q_construct: str | None = None


@dataclass(frozen=True)
class Position(Validated):
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
    comment: str = ""

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
class MicE(Validated):
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
class Object(Validated):
    name: str
    position: Location
    timestamp: Timestamp
    alive: bool = True
    name_raw: bytes | None = None
    legacy: bool = False

    encoding: PositionEncoding = "uncompressed"
    compression: Compression | None = None


@dataclass(frozen=True)
class Item(Validated):
    name: str
    position: Location
    alive: bool = True
    name_raw: bytes | None = None

    encoding: PositionEncoding = "uncompressed"
    compression: Compression | None = None


@dataclass(frozen=True)
class Definition(Validated):
    addressee: str
    definition: DefinitionValue
    values_raw: RawFields = ()


@dataclass(frozen=True)
class Status(Validated):
    text: str = ""
    timestamp: Timestamp | None = None
    grid: Grid | None = None
    symbol: Symbol | None = None
    beam: Beam | None = None


@dataclass(frozen=True)
class Message(Validated):
    addressee: str
    text: str = ""
    message_id: str | None = None
    reply_ack: ReplyAck | None = None

    @property
    def addressee_raw(self) -> str:
        return self.addressee.ljust(9)


@dataclass(frozen=True)
class Acknowledgment(Validated):
    addressee: str
    message_id: str
    rejected: bool = False
    reply_ack: ReplyAck | None = None


@dataclass(frozen=True)
class AutoAnswer(Validated):
    addressee: str
    text: str
    previous_ack: str | None = None


@dataclass(frozen=True)
class Bulletin(Validated):
    identifier: str
    text: str
    group: str | None = None
    announcement: bool = False
    legacy: bool = False


@dataclass(frozen=True)
class NWSBulletin(Validated):
    addressee: str
    text: str
    reference_id: str | None = None


@dataclass(frozen=True)
class Radiogram(Validated):
    addressee: str
    record: NTSRecord
    message_id: str | None = None


@dataclass(frozen=True)
class Query(Validated):
    """General or directed; open query name preserves unrecognized requests."""

    name: str
    addressee: str | None = None
    footprint: Footprint | None = None
    heard_station: str | None = None
    arguments: bytes = b""
    message_id: str | None = None


@dataclass(frozen=True)
class DirectStations(Validated):
    stations: tuple[str, ...]


@dataclass(frozen=True)
class HeardStation(Validated):
    station: str
    counts: tuple[int | None, ...]


@dataclass(frozen=True)
class Trace(Validated):
    header: Header


ResponseValue: TypeAlias = DirectStations | HeardStation | Trace


@dataclass(frozen=True)
class Response(Validated):
    addressee: str
    response: ResponseValue


@dataclass(frozen=True)
class Capabilities(Validated):
    tokens: tuple[Capability, ...]


@dataclass(frozen=True)
class NMEA(Validated):
    sentence: NMEASentence
    metadata: NMEAMetadata = field(default_factory=NMEAMetadata)
    position_usable: bool | None = None
    symbol: Symbol | None = None
    comment: str = ""


@dataclass(frozen=True)
class ThirdParty(Validated):
    packet: Packet


@dataclass(frozen=True)
class UserDefined(Validated):
    user_id: bytes
    user_type: bytes
    data: bytes


@dataclass(frozen=True)
class RawWeather(Validated):
    """Vendor layout is not specified here; retain the complete information field."""

    format: Literal["ultimeter_ii", "ultimeter_2000", "ultw", "peet_logging"]
    information: bytes
    weather: Weather | None = None  # Optional externally interpreted measurements.


@dataclass(frozen=True)
class Agrelo(Validated):
    bearing_deg: int
    quality_code: int
    raw: bytes | None = None


@dataclass(frozen=True)
class Maidenhead(Validated):
    grid: Grid
    symbol: Symbol | None = None
    comment: str = ""


@dataclass(frozen=True)
class LegacyPosition(Validated):
    """X1J prefix-position convention, only for the historical profile."""

    prefix: bytes
    position: Position


@dataclass(frozen=True)
class Beacon(Validated):
    text: str


@dataclass(frozen=True)
class Invalid(Validated):
    data: bytes


@dataclass(frozen=True)
class Reserved(Validated):
    dti: int
    data: bytes


@dataclass(frozen=True)
class ExternalExtension(Validated):
    """Named extension lacking an authoritative grammar in this baseline.

    This is deliberately raw, not a guessed polygon or vendor measurement API.
    It can also annotate object extensions through an outer application model.
    """

    name: Literal["polygon_line", "vendor", "other"]
    information: bytes
    specification_url: str | None = None


@dataclass(frozen=True)
class Diagnostic(Validated):
    code: Literal["unsupported", "malformed"]
    message: str
    path: str = "$"


@dataclass(frozen=True)
class Malformed(Validated):
    """Invalid wire input with repairable JSON data, never an invalid Packet."""

    original_wire: bytes
    diagnostics: tuple[Diagnostic, ...]
    recovered: dict[str, object]


@dataclass(frozen=True)
class Opaque(Validated):
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
class Packet(Validated):
    header: Header
    payload: Payload
    original_wire: bytes | None = field(default=None, compare=False, repr=False)
    header_semantics: HeaderSemantics | None = field(default=None, compare=False)


@dataclass(frozen=True)
class EncodedPacketFields(Validated):
    """Joint encoding result: use this header, not the original template header."""

    header: Header
    information: bytes
