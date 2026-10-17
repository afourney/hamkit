# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Shared semantic fields, independent of packet DTIs and codec availability.

None on a containing field means absent. Measurement(None, unit) means
transmitted but unavailable. Raw codes are received evidence: they are kept,
but never override structured values and never take part in equality. Values
that follow from other fields (grid bounds, PHG range, csT bits) are properties.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from ._validation import FREE_TEXT, Validated, evidence

TimestampKind: TypeAlias = Literal["dhm_utc", "dhm_local", "hms_utc", "mdhm_utc"]
Bounds: TypeAlias = tuple[float, float]
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
    "nSv/h",
    "volts",
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
    raw: bytes | None = evidence()


@dataclass(frozen=True)
class Timestamp(Validated):
    """Partial time; MDHM has month/day, never an inferred year or UTC offset."""

    kind: TimestampKind
    hour: int
    minute: int
    day: int | None = field(default=None, kw_only=True)
    second: int | None = field(default=None, kw_only=True)
    month: int | None = field(default=None, kw_only=True)
    raw: bytes | None = evidence()

    @classmethod
    def dhm(cls, day: int, hour: int, minute: int, *, local: bool = False) -> Timestamp:
        """Day/hour/minute, in UTC unless local=True."""
        return cls("dhm_local" if local else "dhm_utc", hour, minute, day=day)

    @classmethod
    def hms(cls, hour: int, minute: int, second: int) -> Timestamp:
        return cls("hms_utc", hour, minute, second=second)

    @classmethod
    def mdhm(cls, month: int, day: int, hour: int, minute: int) -> Timestamp:
        """Month/day/hour/minute UTC, as used by positionless weather."""
        return cls("mdhm_utc", hour, minute, day=day, month=month)


@dataclass(frozen=True)
class Coordinates(Validated):
    latitude_deg: float
    longitude_deg: float


@dataclass(frozen=True)
class Extent(Validated):
    """A latitude/longitude cell; returned by grid and ambiguity properties."""

    latitude: Bounds
    longitude: Bounds


@dataclass(frozen=True)
class Symbol(Validated):
    """Wire table/overlay character plus symbol code."""

    table_id: str
    code: str

    @property
    def table(self) -> Literal["primary", "alternate"]:
        return "primary" if self.table_id == "/" else "alternate"

    @property
    def overlay(self) -> str | None:
        """Overlay character; compressed overlays a-j are reported as 0-9."""
        if self.table_id in "/\\":
            return None
        if "a" <= self.table_id <= "j":
            return str(ord(self.table_id) - ord("a"))
        return self.table_id


@dataclass(frozen=True)
class Grid(Validated):
    """A four- or six-character Maidenhead locator."""

    locator: str

    def _cell(self) -> tuple[float, float, float, float]:
        code = self.locator.upper()
        west = -180 + (ord(code[0]) - ord("A")) * 20 + int(code[2]) * 2.0
        south = -90 + (ord(code[1]) - ord("A")) * 10 + int(code[3]) * 1.0
        width, height = 2.0, 1.0
        if len(code) == 6:
            width, height = 2 / 24, 1 / 24
            west += (ord(code[4]) - ord("A")) * width
            south += (ord(code[5]) - ord("A")) * height
        return west, south, width, height

    @property
    def bounds(self) -> Extent:
        west, south, width, height = self._cell()
        return Extent((south, south + height), (west, west + width))

    @property
    def center(self) -> Coordinates:
        west, south, width, height = self._cell()
        return Coordinates(south + height / 2, west + width / 2)


@dataclass(frozen=True)
class Motion(Validated):
    course_deg: float | None = None
    speed_knots: float | None = None
    zero_pair: Literal["unavailable", "fixed", "measured", "unspecified"] = field(
        default="unspecified", kw_only=True
    )
    course_code: int | None = evidence()
    speed_code: int | None = evidence()
    raw: bytes | None = evidence()


@dataclass(frozen=True)
class Altitude(Validated):
    measurement: Measurement
    encoding: Literal["feet_extension", "compressed", "mic_e", "nmea"]
    reference: Literal["unspecified", "MSL", "ellipsoid"] = field(
        default="unspecified", kw_only=True
    )


@dataclass(frozen=True)
class Range(Validated):
    miles: float
    raw: bytes | None = evidence()


@dataclass(frozen=True)
class PHG(Validated):
    power_w: float
    height_haat_ft: float
    gain_dbi: float
    directivity_deg: float | None = field(
        default=None, kw_only=True
    )  # None denotes omnidirectional
    rate_per_hour: int | None = field(
        default=None, kw_only=True
    )  # compatibility extension
    raw: bytes | None = evidence()

    @property
    def range_miles(self) -> float:
        """APRS101 p29 radio range; APRS 1.1 corrected gain to dBi."""
        gain = 10 ** (self.gain_dbi / 10)
        return math.sqrt(
            2 * self.height_haat_ft * math.sqrt(self.power_w / 10 * gain / 2)
        )

    @property
    def display_radius_miles(self) -> float:
        """APRS 1.1 display recommendation: half the computed range."""
        return self.range_miles / 2


@dataclass(frozen=True)
class Signal(Validated):
    s_units: int
    height_haat_ft: float
    gain_db: float
    directivity_deg: float | None = field(default=None, kw_only=True)
    raw: bytes | None = evidence()


@dataclass(frozen=True)
class Bearing(Validated):
    bearing_deg: float
    hits_code: int
    range_code: int
    quality_code: int
    usable: bool | None = field(default=None, kw_only=True)
    accuracy_less_than_deg: float | None = field(default=None, kw_only=True)
    raw: bytes | None = evidence()

    @property
    def manual(self) -> bool:
        """Hits code 9 marks a manual report."""
        return self.hits_code == 9

    @property
    def range_miles(self) -> float:
        return float(2**self.range_code)


@dataclass(frozen=True)
class Compression(Validated):
    """csT semantics. ignored=True means c=space: the remaining bytes carry nothing."""

    fix: Literal["old", "current"] | None = field(default=None, kw_only=True)
    nmea_source: Literal["other", "GLL", "GGA", "RMC"] | None = field(
        default=None, kw_only=True
    )
    origin_code: int | None = field(default=None, kw_only=True)
    ignored: bool = field(default=False, kw_only=True)
    raw: bytes | None = evidence()

    @property
    def type_value(self) -> int | None:
        """The compression type byte value implied by fix, source and origin."""
        if self.ignored or self.fix is None or self.nmea_source is None:
            return None
        source = {"other": 0, "GLL": 8, "GGA": 16, "RMC": 24}[self.nmea_source]
        return (32 if self.fix == "current" else 0) + source + (self.origin_code or 0)


@dataclass(frozen=True)
class DAO(Validated):
    datum_byte: str
    latitude_precision: int | None = field(default=None, kw_only=True)
    longitude_precision: int | None = field(default=None, kw_only=True)
    encoding: Literal["decimal", "base91"] | None = field(default=None, kw_only=True)
    raw: bytes | None = evidence()


@dataclass(frozen=True)
class Area(Validated):
    shape_code: int
    color_code: int
    latitude_offset_code: int
    longitude_offset_code: int
    corridor_half_width_miles: float | None = field(default=None, kw_only=True)

    @property
    def latitude_offset_deg(self) -> float:
        """Corrected APRS 1.1 offset: code squared over 1500."""
        return self.latitude_offset_code**2 / 1500

    @property
    def longitude_offset_deg(self) -> float:
        return self.longitude_offset_code**2 / 1500

    @property
    def transmitted_anchor(self) -> Literal["lower_reference", "circle_center"]:
        return "circle_center" if self.shape_code in (0, 5) else "lower_reference"


@dataclass(frozen=True)
class Signpost(Validated):
    label: str


@dataclass(frozen=True)
class WaterHeight(Validated):
    measurement: Measurement
    reference_datum: str | None = field(default=None, kw_only=True)


@dataclass(frozen=True, kw_only=True)
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
    radiation: Measurement | None = None
    battery_voltage: Measurement | None = None
    software_code: str | None = None
    device_code: str | None = None
    timestamp: Timestamp | None = None
    comment: str = field(default="", metadata=FREE_TEXT)
    raw: bytes | None = evidence()


@dataclass(frozen=True)
class Storm(Validated):
    kind: Literal["HC", "TS", "TD"]
    predicted: bool = field(kw_only=True)
    sustained_wind_knots: float = field(kw_only=True)
    peak_gust_knots: float = field(kw_only=True)
    central_pressure_hpa: float = field(kw_only=True)
    hurricane_radius_nm: float = field(kw_only=True)
    tropical_storm_radius_nm: float = field(kw_only=True)
    whole_gale_radius_nm: float | None = field(default=None, kw_only=True)
    raw: bytes | None = evidence()


AnalogChannels: TypeAlias = tuple[float | None, ...]
DigitalChannels: TypeAlias = tuple[bool | None, ...]
TelemetryEncoding: TypeAlias = Literal[
    "classic", "mic_e_hex", "mic_e_binary", "base91_comment"
]


@dataclass(frozen=True)
class Telemetry(Validated):
    """Ordered raw channels, uncalibrated. Missing channels are None, not zero."""

    analog: AnalogChannels = ()
    digital: DigitalChannels = ()
    sequence: int | Literal["MIC"] | None = field(default=None, kw_only=True)
    encoding: TelemetryEncoding = field(default="classic", kw_only=True)
    comment: str = field(default="", metadata=FREE_TEXT, kw_only=True)
    sequence_raw: bytes | None = evidence()
    raw: bytes | None = evidence()


@dataclass(frozen=True, kw_only=True)
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

    def __bool__(self) -> bool:
        return any(getattr(self, name) is not None for name in _EXTENSION_FIELDS)


_EXTENSION_FIELDS = (
    "motion",
    "altitude",
    "phg",
    "range",
    "signal",
    "bearing",
    "dao",
    "area",
    "signpost",
    "weather",
    "storm",
    "telemetry",
)


@dataclass(frozen=True)
class Beam(Validated):
    heading_deg: float
    erp_w: float
    raw: bytes | None = evidence()


@dataclass(frozen=True)
class TelemetryParameters(Validated):
    """PARM. channel names."""

    channels: tuple[str | None, ...]


@dataclass(frozen=True)
class TelemetryUnits(Validated):
    """UNIT. channel units or labels."""

    channels: tuple[str | None, ...]


@dataclass(frozen=True)
class Calibration(Validated):
    """One EQNS. a·x² + b·x + c triple."""

    a: float
    b: float
    c: float


@dataclass(frozen=True)
class TelemetryEquations(Validated):
    """EQNS. coefficients; None keeps a channel's slot empty."""

    coefficients: tuple[Calibration | None, ...]


@dataclass(frozen=True)
class TelemetryBits(Validated):
    """BITS. sense bits plus an optional project title."""

    sense: tuple[bool, bool, bool, bool, bool, bool, bool, bool]
    project_title: str = field(default="", kw_only=True)


TelemetryDefinitionValue: TypeAlias = (
    TelemetryParameters | TelemetryUnits | TelemetryEquations | TelemetryBits
)


@dataclass(frozen=True, kw_only=True)
class NTSHeader(Validated):
    number: str
    precedence: str
    originator: str
    check: str
    place: str
    date: str
    handling: str | None = None
    time: str | None = None


@dataclass(frozen=True)
class NTSAddress(Validated):
    lines: tuple[str, str, str, str]


@dataclass(frozen=True)
class NTSPhone(Validated):
    number: str


@dataclass(frozen=True)
class NTSText(Validated):
    line: Literal[1, 2, 3, 4, 5, 6]
    text: str


@dataclass(frozen=True)
class NTSSignature(Validated):
    text: str


@dataclass(frozen=True, kw_only=True)
class NTSRouting(Validated):
    received_from: str
    received_at: str
    sent_to: str
    sent_at: str


NTSRecord: TypeAlias = (
    NTSHeader | NTSAddress | NTSPhone | NTSText | NTSSignature | NTSRouting
)


@dataclass(frozen=True)
class Footprint(Validated):
    center: Coordinates
    radius_miles: float


@dataclass(frozen=True)
class Capability(Validated):
    name: str
    value: str | None = None
