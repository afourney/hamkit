# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Public packet models. Construction does not imply an available wire codec."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from ._ambiguity import axis_extent
from ._data import (
    Beam,
    Capability,
    Compression,
    Coordinates,
    Extensions,
    Extent,
    Footprint,
    Grid,
    NTSRecord,
    Symbol,
    Telemetry,
    TelemetryDefinitionValue,
    Timestamp,
    Weather,
)
from ._errors import APRSError, EnvelopeError
from ._nmea import NMEAMetadata, NMEASentence
from ._validation import ANY_TEXT, FREE_TEXT, Validated

UnsupportedPolicy: TypeAlias = Literal["opaque", "raise"]
MalformedPolicy: TypeAlias = Literal["return", "raise"]
DiagnosticCode: TypeAlias = Literal["unsupported", "malformed", "nonconforming"]
MicEMessage: TypeAlias = Literal[
    "off_duty",
    "en_route",
    "in_service",
    "returning",
    "committed",
    "special",
    "priority",
    "custom_0",
    "custom_1",
    "custom_2",
    "custom_3",
    "custom_4",
    "custom_5",
    "custom_6",
    "emergency",
    "unknown",
]


@dataclass(frozen=True)
class Hop(Validated):
    address: str
    repeated: bool = False


@dataclass(frozen=True)
class Header(Validated):
    """TNC2 header; destination=None requests automatic packing in a Mic-E Packet.

    A standalone automatic header is a template, not serializable wire text.
    Other packet payloads require an explicit destination.
    """

    source: str
    destination: str | None = None
    path: tuple[Hop, ...] = ()

    @classmethod
    def parse(cls, text: str) -> Header:
        """Build a header from TNC2 text such as ``N0CALL>APRS,WIDE1-1*``."""
        source, arrow, route = text.partition(">")
        destination, *hops = route.split(",")
        if not arrow:
            raise EnvelopeError("header text requires SOURCE>DESTINATION")
        return cls(
            source,
            destination,
            tuple(Hop(t.removesuffix("*"), t.endswith("*")) for t in hops),
        )

    def __str__(self) -> str:
        if self.destination is None:
            raise EnvelopeError(
                "automatic destination needs a Mic-E packet; use serialize_packet"
            )
        route = "".join(
            "," + hop.address + ("*" if hop.repeated else "") for hop in self.path
        )
        return f"{self.source}>{self.destination}{route}"


class _Located:
    """Shared views for payloads that report a place."""

    latitude_deg: float
    longitude_deg: float
    ambiguity: int

    @property
    def coordinates(self) -> Coordinates:
        return Coordinates(self.latitude_deg, self.longitude_deg)

    @property
    def ambiguity_extent(self) -> Extent | None:
        """The selected wire cell; raises FieldError if it exceeds axis bounds."""
        if not self.ambiguity:
            return None
        return Extent(
            axis_extent(self.latitude_deg, self.ambiguity, 90),
            axis_extent(self.longitude_deg, self.ambiguity, 180),
        )


@dataclass(frozen=True)
class Position(_Located, Validated):
    """A station position report.

    comment holds the free text after the decoded data extensions. Text shaped
    like an extension but with invalid values stays in comment, with a finding.
    Extensions this version recognizes but cannot decode make the payload
    Opaque, so they are never mistaken for comment text.
    """

    latitude_deg: float
    longitude_deg: float
    symbol: Symbol
    comment: str = field(default="", metadata=FREE_TEXT, kw_only=True)
    messaging: bool = field(default=False, kw_only=True)
    timestamp: Timestamp | None = field(default=None, kw_only=True)
    ambiguity: int = field(default=0, kw_only=True)
    compression: Compression | None = field(default=None, kw_only=True)
    extensions: Extensions = field(default_factory=Extensions, kw_only=True)

    @property
    def compressed(self) -> bool:
        return self.compression is not None

    @property
    def is_null_position(self) -> bool:
        return (
            self.latitude_deg == 0
            and self.longitude_deg == 0
            and self.symbol == Symbol("\\", ".")
        )


@dataclass(frozen=True)
class MicE(_Located, Validated):
    """Header-dependent position: the destination address carries latitude.

    device_code contains the type byte and declared manufacturer suffix only.
    Optional legacy grid/status text is preserved in comment.
    """

    latitude_deg: float
    longitude_deg: float
    symbol: Symbol
    message: MicEMessage = field(kw_only=True)
    comment: str = field(default="", metadata=FREE_TEXT, kw_only=True)
    fix: Literal["current", "old"] = field(default="current", kw_only=True)
    ambiguity: int = field(default=0, kw_only=True)
    device_code: str | None = field(default=None, kw_only=True)
    extensions: Extensions = field(default_factory=Extensions, kw_only=True)


@dataclass(frozen=True)
class Object(_Located, Validated):
    name: str
    latitude_deg: float
    longitude_deg: float
    symbol: Symbol
    timestamp: Timestamp = field(kw_only=True)
    comment: str = field(default="", metadata=FREE_TEXT, kw_only=True)
    alive: bool = field(default=True, kw_only=True)
    ambiguity: int = field(default=0, kw_only=True)
    compression: Compression | None = field(default=None, kw_only=True)
    extensions: Extensions = field(default_factory=Extensions, kw_only=True)

    @property
    def compressed(self) -> bool:
        return self.compression is not None


@dataclass(frozen=True)
class Item(_Located, Validated):
    name: str
    latitude_deg: float
    longitude_deg: float
    symbol: Symbol
    comment: str = field(default="", metadata=FREE_TEXT, kw_only=True)
    alive: bool = field(default=True, kw_only=True)
    ambiguity: int = field(default=0, kw_only=True)
    compression: Compression | None = field(default=None, kw_only=True)
    extensions: Extensions = field(default_factory=Extensions, kw_only=True)

    @property
    def compressed(self) -> bool:
        return self.compression is not None


@dataclass(frozen=True)
class TelemetryDefinition(Validated):
    """PARM./UNIT./EQNS./BITS. message addressed to the reporting station."""

    addressee: str
    definition: TelemetryDefinitionValue


@dataclass(frozen=True)
class Status(Validated):
    text: str = field(metadata=FREE_TEXT)
    timestamp: Timestamp | None = field(default=None, kw_only=True)
    grid: Grid | None = field(default=None, kw_only=True)
    symbol: Symbol | None = field(default=None, kw_only=True)
    beam: Beam | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class Message(Validated):
    """A message. reply_ack is the APRS 1.1 '}AA' suffix ('' when no ack)."""

    addressee: str
    text: str = field(metadata=FREE_TEXT)
    message_id: str | None = field(default=None, kw_only=True)
    reply_ack: str | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class Acknowledgment(Validated):
    addressee: str
    message_id: str
    rejected: bool = field(default=False, kw_only=True)
    reply_ack: str | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class AutoAnswer(Validated):
    addressee: str
    text: str = field(metadata=FREE_TEXT)
    previous_ack: str | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class Bulletin(Validated):
    """BLNn bulletin (digit) or BLNx announcement (letter)."""

    identifier: str
    text: str = field(metadata=FREE_TEXT)
    group: str | None = field(default=None, kw_only=True)

    @property
    def announcement(self) -> bool:
        return self.identifier.isalpha()


@dataclass(frozen=True)
class NWSBulletin(Validated):
    addressee: str
    text: str = field(metadata=FREE_TEXT)
    reference_id: str | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class Radiogram(Validated):
    addressee: str
    record: NTSRecord
    message_id: str | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class Query(Validated):
    """General or directed; an open query name preserves unrecognized requests."""

    name: str
    addressee: str | None = field(default=None, kw_only=True)
    footprint: Footprint | None = field(default=None, kw_only=True)
    heard_station: str | None = field(default=None, kw_only=True)
    arguments: bytes = field(default=b"", kw_only=True)


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
    """A station's advertised capability tokens."""

    tokens: tuple[Capability, ...]


@dataclass(frozen=True)
class NMEA(Validated):
    sentence: NMEASentence
    metadata: NMEAMetadata
    position_usable: bool | None = field(default=None, kw_only=True)
    symbol: Symbol | None = field(default=None, kw_only=True)
    comment: str = field(default="", metadata=FREE_TEXT, kw_only=True)


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
    """Vendor bytes are authoritative; prefix is checked, detailed layout is not."""

    format: Literal["ultimeter_ii", "ultimeter_2000", "ultw", "peet_logging"]
    information: bytes
    weather: Weather | None = field(
        default=None, kw_only=True
    )  # Optional externally interpreted measurements.


@dataclass(frozen=True)
class Agrelo(Validated):
    bearing_deg: int
    quality_code: int
    raw: bytes | None = field(default=None, compare=False, repr=False, kw_only=True)


@dataclass(frozen=True)
class Maidenhead(Validated):
    grid: Grid
    symbol: Symbol | None = field(default=None, kw_only=True)
    comment: str = field(default="", metadata=FREE_TEXT, kw_only=True)


@dataclass(frozen=True)
class LegacyPosition(Validated):
    """X1J prefix-position convention from historical software."""

    prefix: bytes
    position: Position


@dataclass(frozen=True)
class Beacon(Validated):
    text: str = field(metadata=FREE_TEXT)


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
    """

    name: Literal["polygon_line", "vendor", "other"]
    information: bytes
    specification_url: str | None = field(default=None, metadata=ANY_TEXT, kw_only=True)


@dataclass(frozen=True)
class Diagnostic(Validated):
    """A finding about received data or a packet about to be sent.

    unsupported: no decoder yet. malformed: a field could not be decoded.
    nonconforming: decodable, but outside APRS rules; sending would be refused.
    """

    code: DiagnosticCode
    message: str = field(metadata=ANY_TEXT)
    path: str = "$"


@dataclass(frozen=True)
class Opaque(Validated):
    """Information bytes this version does not interpret."""

    information: bytes
    diagnostic: Diagnostic | None = field(default=None, compare=False, kw_only=True)


@dataclass(frozen=True)
class Malformed(Validated):
    """Wire input with undecodable fields; never a Packet or a payload.

    recovered holds the reliable values in the ordinary JSON shape, so they can
    be corrected and loaded with from_json_dict.
    """

    original_wire: bytes
    diagnostics: tuple[Diagnostic, ...]
    recovered: dict[str, object]

    @property
    def header(self) -> Header | None:
        """The header, when it was decoded intact."""
        from ._json import from_json_dict

        data = self.recovered.get("header")
        if self.recovered.get("type") != "packet" or not isinstance(data, dict):
            return None
        try:
            return from_json_dict(data, expected_type=Header)
        except APRSError:
            return None


Payload: TypeAlias = (
    Position
    | MicE
    | Object
    | Item
    | Weather
    | Telemetry
    | TelemetryDefinition
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
    """A header and payload.

    original_wire and diagnostics describe received bytes, not the current
    fields: they are ignored by equality and never used for serialization.
    """

    header: Header
    payload: Payload
    original_wire: bytes | None = field(
        default=None, compare=False, repr=False, kw_only=True
    )
    diagnostics: tuple[Diagnostic, ...] = field(default=(), compare=False, kw_only=True)
