# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Shared semantic fields, independent of packet DTIs and codec availability.

None on a containing field means absent. Measurement(None, raw=...) means
transmitted but unavailable. Raw codes are evidence, not automatic overrides
for encoding; a future encoder must validate contradictions rather than drop
structured fields. Units are explicit and no datum conversions are implied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from .model_validation import Validated

TimestampKind: TypeAlias = Literal["dhm_utc", "dhm_local", "hms_utc", "mdhm_utc"]
PositionEncoding: TypeAlias = Literal["uncompressed", "compressed"]
Bounds: TypeAlias = tuple[float, float]
RawFields: TypeAlias = tuple[bytes, ...]
Unit: TypeAlias = Literal[
    "degrees",
    "knots",
    "mph",
    "m/s",
    "km/h",
    "feet",
    "meters",
    "miles",
    "nautical_miles",
    "fahrenheit",
    "celsius",
    "percent",
    "hPa",
    "inches",
    "mm",
    "W/m2",
    "watts",
    "dBi",
    "dB",
    "S_units",
    "count",
    "raw",
    "disputed_knots_or_mph",
]


@dataclass(frozen=True)
class Measurement(Validated):
    value: float | None
    unit: Unit
    raw: bytes | None = None


@dataclass(frozen=True)
class Timestamp(Validated):
    """Partial time; MDHM has month/day, never an inferred year or UTC offset."""

    kind: TimestampKind
    hour: int
    minute: int
    day: int | None = None
    second: int | None = None
    month: int | None = None
    raw: bytes | None = None


@dataclass(frozen=True)
class Coordinates(Validated):
    latitude_deg: float
    longitude_deg: float


@dataclass(frozen=True)
class Extent(Validated):
    latitude: Bounds
    longitude: Bounds


@dataclass(frozen=True)
class Ambiguity(Validated):
    digits: int
    extent: Extent | None = None
    representative: Literal["center"] = "center"


@dataclass(frozen=True)
class Symbol(Validated):
    """Wire table/overlay byte plus symbol; lower-case compressed overlays retained."""

    table_id: str = "/"
    code: str = "-"


@dataclass(frozen=True)
class Grid(Validated):
    locator: str
    bounds: Extent | None = None
    center: Coordinates | None = None


@dataclass(frozen=True)
class Motion(Validated):
    course_deg: float | None = None
    speed_knots: float | None = None
    course_code: int | None = None
    speed_code: int | None = None
    raw: bytes | None = None
    zero_pair: Literal[
        "unavailable", "fixed", "measured", "unspecified"
    ] = "unspecified"


@dataclass(frozen=True)
class Altitude(Validated):
    measurement: Measurement
    encoding: Literal["feet_extension", "compressed", "mic_e", "nmea"]
    reference: Literal["unspecified", "MSL", "ellipsoid"] = "unspecified"


@dataclass(frozen=True)
class Range(Validated):
    miles: float
    raw: bytes | None = None


@dataclass(frozen=True)
class PHG(Validated):
    power_w: float
    height_haat_ft: float
    gain_dbi: float
    directivity_deg: float | None = None  # None denotes omnidirectional
    raw: bytes | None = None
    range_miles_1_0: float | None = None
    display_radius_miles_1_1: float | None = None
    rate_per_hour: int | None = None  # compatibility extension


@dataclass(frozen=True)
class Signal(Validated):
    s_units: int
    height_haat_ft: float
    gain_db: float
    directivity_deg: float | None = None
    raw: bytes | None = None


@dataclass(frozen=True)
class Bearing(Validated):
    bearing_deg: float
    hits_code: int
    range_code: int
    quality_code: int
    manual: bool = False
    usable: bool | None = None
    range_miles: float | None = None
    accuracy_less_than_deg: float | None = None
    raw: bytes | None = None


@dataclass(frozen=True)
class Compression(Validated):
    """Raw csT plus semantic bits; c=space can explicitly ignore the remainder."""

    type_value: int
    fix: Literal["old", "current"]
    nmea_source: Literal["other", "GLL", "GGA", "RMC"]
    origin_code: int
    csT_raw: bytes | None = None
    ignored: bool = False


@dataclass(frozen=True)
class DAO(Validated):
    datum_byte: str
    latitude_precision: int
    longitude_precision: int
    encoding: Literal["decimal", "base91"]
    raw: bytes | None = None


@dataclass(frozen=True)
class Area(Validated):
    shape_code: int
    color_code: int
    latitude_offset_code: int
    longitude_offset_code: int
    corridor_half_width_miles: float | None = None
    latitude_offset_deg: float | None = None
    longitude_offset_deg: float | None = None
    transmitted_anchor: Literal["lower_reference", "circle_center"] = "lower_reference"


@dataclass(frozen=True)
class Signpost(Validated):
    label: str


@dataclass(frozen=True)
class WaterHeight(Validated):
    measurement: Measurement
    reference_datum: str | None = None


@dataclass(frozen=True)
class Weather(Validated):
    """Weather observations, usable as a payload or a located extension."""

    wind_direction: Measurement | None = None
    wind_speed: Measurement | None = None
    gust: Measurement | None = None
    temperature: Measurement | None = None
    humidity: Measurement | None = None
    pressure: Measurement | None = None
    rain_1h: Measurement | None = None
    rain_24h: Measurement | None = None
    rain_since_midnight: Measurement | None = None
    snow_24h: Measurement | None = None
    luminosity: Measurement | None = None
    rain_counter: Measurement | None = None
    water_height: WaterHeight | None = None
    software_code: str | None = None
    device_code: str | None = None
    raw: bytes | None = None
    timestamp: Timestamp | None = None
    comment: str = ""


@dataclass(frozen=True)
class Storm(Validated):
    kind: Literal["HC", "TS", "TD"]
    predicted: bool
    sustained_wind_knots: float
    peak_gust_knots: float
    central_pressure_hpa: float
    hurricane_radius_nm: float
    tropical_storm_radius_nm: float
    whole_gale_radius_nm: float | None = None
    raw: bytes | None = None


AnalogChannels: TypeAlias = tuple[float | None, ...]
DigitalChannels: TypeAlias = tuple[bool | None, ...]
TelemetryEncoding: TypeAlias = Literal[
    "classic", "mic_e_hex", "mic_e_binary", "base91_comment", "compatibility"
]


@dataclass(frozen=True)
class Telemetry(Validated):
    """Ordered raw channels, uncalibrated. Missing channels are None, not zero."""

    analog: AnalogChannels = ()
    digital: DigitalChannels = ()
    sequence: int | Literal["MIC"] | None = None
    encoding: TelemetryEncoding = "classic"
    sequence_raw: bytes | None = None
    raw: bytes | None = None
    mic_comma: bool = True
    comment: str = ""


@dataclass(frozen=True)
class Extensions(Validated):
    motion: Motion | None = None
    altitude: Altitude | None = None
    phg: PHG | None = None
    range: Range | None = None
    signal: Signal | None = None
    bearing: Bearing | None = None
    dao: DAO | None = None
    area: Area | None = None
    signpost: Signpost | None = None
    weather: Weather | None = None
    storm: Storm | None = None
    telemetry: Telemetry | None = None


@dataclass(frozen=True)
class Location(Validated):
    """Shared spatial content, without report-level timestamps or messaging flags."""

    latitude_deg: float
    longitude_deg: float
    symbol: Symbol = field(default_factory=Symbol)
    ambiguity: Ambiguity | None = None
    extensions: Extensions = field(default_factory=Extensions)
    tail: bytes = b""
    comment: str = ""


@dataclass(frozen=True)
class Beam(Validated):
    heading_deg: float
    erp_w: float
    raw: bytes | None = None


@dataclass(frozen=True)
class ReplyAck(Validated):
    message_number: str
    previous_ack: str | None = None


@dataclass(frozen=True)
class Parameters(Validated):
    channels: tuple[str | None, ...]


@dataclass(frozen=True)
class Units(Validated):
    channels: tuple[str | None, ...]


@dataclass(frozen=True)
class Calibration(Validated):
    a: float
    b: float
    c: float


@dataclass(frozen=True)
class Equations(Validated):
    coefficients: tuple[Calibration | None, ...]


@dataclass(frozen=True)
class Bits(Validated):
    sense: DigitalChannels
    project_title: str = ""


DefinitionValue: TypeAlias = Parameters | Units | Equations | Bits


@dataclass(frozen=True)
class NTSHeader(Validated):
    number: str
    precedence: str
    handling: str
    originator: str
    check: str
    place: str
    time: str
    date: str


@dataclass(frozen=True)
class Address(Validated):
    lines: tuple[str, str, str, str]


@dataclass(frozen=True)
class Phone(Validated):
    number: str


@dataclass(frozen=True)
class Text(Validated):
    line: Literal[1, 2, 3, 4, 5, 6]
    text: str


@dataclass(frozen=True)
class Signature(Validated):
    text: str


@dataclass(frozen=True)
class Routing(Validated):
    received_from: str
    received_at: str
    sent_to: str
    sent_at: str


NTSRecord: TypeAlias = NTSHeader | Address | Phone | Text | Signature | Routing


@dataclass(frozen=True)
class Footprint(Validated):
    center: Coordinates
    radius_miles: float


@dataclass(frozen=True)
class Capability(Validated):
    name: str
    value: str | None = None
