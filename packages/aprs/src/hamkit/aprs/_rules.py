# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Constructor invariants (APRS101 with APRS 1.1 corrections).

A rule belongs here only when the value cannot be represented on the wire, or
contradicts another field of the same model. Limits that a transmitter could
still violate, and requirements that depend on the enclosing report, are
conformance rules (_conformance.py): received packets that break them still
decode, and serialization refuses to send them.
"""
from __future__ import annotations

import calendar
import re
from typing import Any

from ._data import (
    DAO,
    PHG,
    Altitude,
    Area,
    Beam,
    Bearing,
    Capability,
    Compression,
    Coordinates,
    Extent,
    Footprint,
    Grid,
    Measurement,
    Motion,
    NTSAddress,
    NTSHeader,
    NTSPhone,
    NTSRouting,
    NTSSignature,
    NTSText,
    Range,
    Signal,
    Signpost,
    Storm,
    Symbol,
    Telemetry,
    TelemetryParameters,
    TelemetryUnits,
    Timestamp,
    WaterHeight,
    Weather,
)
from ._models import (
    NMEA,
    Acknowledgment,
    Agrelo,
    AutoAnswer,
    Beacon,
    Bulletin,
    DirectStations,
    ExternalExtension,
    Header,
    HeardStation,
    Hop,
    Item,
    LegacyPosition,
    Malformed,
    Message,
    MicE,
    NWSBulletin,
    Object,
    Opaque,
    Packet,
    Position,
    Query,
    Radiogram,
    RawWeather,
    Reserved,
    Response,
    Status,
    TelemetryDefinition,
    Trace,
    UserDefined,
)
from ._nmea import GGA, GLL, RMC, VTG, WPL, NMEADate, NMEAMetadata, UTCTime
from ._validation import fail, invariant

_ID = re.compile(r"[A-Za-z0-9]{1,5}")
_REPLY_ACK = re.compile(r"[A-Za-z0-9]{0,5}")
# Must match the decoder's acknowledgment grammar exactly, reply-ack included.
_ACK_TEXT = re.compile(r"(ack|rej)[A-Za-z0-9]{1,5}(?:\}[A-Za-z0-9]{0,5})?")


def _bounds(v: Any, name: str, low: float, high: float) -> None:
    value = getattr(v, name)
    if value is not None and not low <= value <= high:
        fail(name, f"must be in {low}..{high}")


def _nonnegative(v: Any, *names: str) -> None:
    for name in names:
        _bounds(v, name, 0, float("inf"))


def _length(v: Any, name: str, low: int, high: int) -> None:
    value = getattr(v, name)
    if value is not None and not low <= len(value) <= high:
        fail(name, f"length must be in {low}..{high}")


def _pattern(v: Any, name: str, pattern: re.Pattern[str], message: str) -> None:
    value = getattr(v, name)
    if value is not None and not pattern.fullmatch(value):
        fail(name, message)


def _station(v: Any, name: str, value: str) -> None:
    if not 1 <= len(value) <= 9 or any(c in " :>,*" for c in value):
        fail(name, "requires a station token of 1..9 characters")


# Places ------------------------------------------------------------------


@invariant(Coordinates, Position, MicE, Object, Item)
def _coordinates(v: Any) -> None:
    _bounds(v, "latitude_deg", -90, 90)
    _bounds(v, "longitude_deg", -180, 180)


@invariant(Position, MicE, Object, Item)
def _located(v: Any) -> None:
    _bounds(v, "ambiguity", 0, 4)


@invariant(Position, Object, Item)
def _overlay(v: Any) -> None:
    if v.compression is None and "a" <= v.symbol.table_id <= "j":
        fail("symbol.table_id", "numeric overlays a-j exist only in compressed form")
    if v.compression is not None and v.ambiguity:
        fail("ambiguity", "compressed coordinates do not encode ambiguity")


@invariant(Position, Object)
def _report_timestamp(v: Any) -> None:
    if v.timestamp is not None and v.timestamp.kind == "mdhm_utc":
        fail("timestamp", "position/object timestamps use DHM or HMS")


@invariant(Object, Item)
def _name(v: Any) -> None:
    _length(v, "name", 1, 9)
    if v.name != v.name.strip():
        fail("name", "names cannot have leading or trailing spaces")
    if isinstance(v, Item) and any(c in "!_" for c in v.name):
        fail("name", "item names cannot contain the ! or _ delimiters")


@invariant(Extent)
def _extent(v: Extent) -> None:
    for name, limit in (("latitude", 90), ("longitude", 180)):
        low, high = getattr(v, name)
        if not -limit <= low <= high <= limit:
            fail(name, "requires ordered bounds within coordinate limits")


@invariant(Symbol)
def _symbol(v: Symbol) -> None:
    if len(v.table_id) != 1 or v.table_id not in (
        "/\\0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
    ):
        fail("table_id", "invalid symbol table or overlay")
    if len(v.code) != 1 or not 33 <= ord(v.code) <= 126:
        fail("code", "requires one printable symbol code")


@invariant(Grid)
def _grid(v: Grid) -> None:
    if not re.fullmatch(r"[A-Ra-r]{2}[0-9]{2}(?:[A-Xa-x]{2})?", v.locator):
        fail("locator", "requires four or six Maidenhead characters")


@invariant(Timestamp)
def _timestamp(v: Timestamp) -> None:
    _bounds(v, "hour", 0, 23)
    _bounds(v, "minute", 0, 59)
    if v.kind == "hms_utc":
        if v.second is None:
            fail("second", "required for HMS")
        _bounds(v, "second", 0, 59)
        if v.day is not None or v.month is not None:
            fail("day", "HMS has no day or month")
        return
    if v.day is None:
        fail("day", "required for DHM/MDHM")
    _bounds(v, "day", 1, 31)
    if v.second is not None:
        fail("second", "only valid for HMS")
    if v.kind != "mdhm_utc":
        if v.month is not None:
            fail("month", "only valid for MDHM")
        return
    if v.month is None:
        fail("month", "required for MDHM")
    _bounds(v, "month", 1, 12)
    assert v.day is not None and v.month is not None
    if v.day > (29 if v.month == 2 else 30 if v.month in (4, 6, 9, 11) else 31):
        fail("day", "not valid for month")


# Extensions ----------------------------------------------------------------


@invariant(Motion)
def _motion(v: Motion) -> None:
    _bounds(v, "course_deg", 0, 360)
    _nonnegative(v, "speed_knots")


@invariant(PHG, Signal)
def _antenna(v: Any) -> None:
    if v.height_haat_ft <= 0:
        fail("height_haat_ft", "encoded antenna height must be positive")
    gain = "gain_dbi" if isinstance(v, PHG) else "gain_db"
    if getattr(v, gain) < 0:
        fail(gain, "PHG/DFS gain codes cannot describe negative gain")
    _bounds(v, "directivity_deg", 0, 360)
    if isinstance(v, PHG):
        _nonnegative(v, "power_w", "rate_per_hour")
    else:
        _bounds(v, "s_units", 0, 9)


@invariant(Bearing)
def _bearing(v: Bearing) -> None:
    _bounds(v, "bearing_deg", 0, 360)
    _bounds(v, "hit_ratio", 0, 1)
    if v.accuracy_deg is not None and v.accuracy_deg <= 0:
        fail("accuracy_deg", "an angular accuracy bound must be positive")
    if v.manual and v.hit_ratio is not None:
        fail("hit_ratio", "a manual report has no hit ratio")
    if v.nrq_meaningful:
        if v.range_miles is None:
            fail("range_miles", "a reported bearing needs a range")
        _bounds(v, "range_miles", 1, 512)
    elif v.range_miles is not None or v.accuracy_deg is not None:
        fail("hit_ratio", "range and accuracy need a hit ratio or manual=True")


@invariant(Range, Footprint)
def _distance(v: Any) -> None:
    _nonnegative(v, "miles" if isinstance(v, Range) else "radius_miles")


@invariant(Beam)
def _beam(v: Beam) -> None:
    _bounds(v, "heading_deg", 0, 360)
    _nonnegative(v, "erp_w")


@invariant(Compression)
def _compression(v: Compression) -> None:
    names = ("fix", "nmea_source", "origin")
    for name in names:
        # Missing metadata is chosen when sending; ignored csT has none.
        if v.ignored and getattr(v, name) is not None:
            fail(name, "ignored csT carries no compression metadata")


@invariant(DAO)
def _dao(v: DAO) -> None:
    if not re.fullmatch("[A-Z]", v.datum):
        fail("datum", "requires an uppercase datum identifier A..Z")


@invariant(Area)
def _area(v: Area) -> None:
    _bounds(v, "latitude_offset_deg", 0, 99**2 / 1500)
    _bounds(v, "longitude_offset_deg", 0, 99**2 / 1500)
    if v.corridor_half_width_miles is not None:
        if v.shape not in ("line_down_right", "line_down_left"):
            fail("corridor_half_width_miles", "corridors apply only to line shapes")
        _nonnegative(v, "corridor_half_width_miles")


@invariant(Signpost)
def _signpost(v: Signpost) -> None:
    if not 1 <= len(v.label) <= 3 or any(c in "{}" for c in v.label):
        fail("label", "requires 1..3 characters without braces")


@invariant(Altitude, WaterHeight)
def _height(v: Any) -> None:
    if v.measurement.unit not in ("feet", "meters"):
        fail("measurement.unit", "height requires feet or meters")
    if isinstance(v, Altitude):
        if v.encoding != "nmea" and v.measurement.value is None:
            fail("measurement.value", "this altitude encoding carries a number")
        if v.encoding == "mic_e" and v.reference == "ellipsoid":
            fail("reference", "Mic-E altitude uses mean sea level")


# Weather and telemetry -----------------------------------------------------

WEATHER_UNITS: dict[str, tuple[str, ...]] = {
    "wind_direction": ("degrees",),
    "wind_speed": ("mph", "knots", "m/s", "km/h", "disputed_knots_or_mph"),
    "gust": ("mph", "knots", "m/s", "km/h"),
    "temperature": ("fahrenheit", "celsius"),
    "humidity": ("percent",),
    "pressure": ("hPa",),
    "rain_1h": ("inches", "mm"),
    "rain_24h": ("inches", "mm"),
    "rain_since_midnight": ("inches", "mm"),
    "snow_24h": ("inches", "mm"),
    "luminosity": ("W/m2",),
    "rain_counter": ("count", "raw"),
    "radiation": ("nSv/h",),
    "battery_voltage": ("volts",),
}


@invariant(Weather)
def _weather(v: Weather) -> None:
    for name, units in WEATHER_UNITS.items():
        reading: Measurement | None = getattr(v, name)
        if reading is not None and reading.unit not in units:
            fail(name + ".unit", "unit does not describe this quantity")
    if v.timestamp is not None and v.timestamp.kind != "mdhm_utc":
        fail("timestamp", "weather timestamps use MDHM UTC")


@invariant(Storm)
def _storm(v: Storm) -> None:
    _nonnegative(
        v,
        "sustained_wind_knots",
        "peak_gust_knots",
        "central_pressure_hpa",
        "hurricane_radius_nm",
        "tropical_storm_radius_nm",
        "whole_gale_radius_nm",
    )


@invariant(Telemetry)
def _telemetry(v: Telemetry) -> None:
    _length(v, "analog", 0, 5)
    _length(v, "digital", 0, 8)
    if isinstance(v.sequence, int):
        _nonnegative(v, "sequence")


@invariant(TelemetryParameters, TelemetryUnits)
def _channel_labels(v: Any) -> None:
    for i, channel in enumerate(v.channels):
        if channel is not None and "," in channel:
            fail(f"channels[{i}]", "labels cannot contain the comma separator")


# Messages ------------------------------------------------------------------


@invariant(
    Message,
    Acknowledgment,
    AutoAnswer,
    NWSBulletin,
    Radiogram,
    TelemetryDefinition,
    Response,
    Query,
)
def _addressee(v: Any) -> None:
    if v.addressee is None:
        return
    _length(v, "addressee", 1, 9)
    if v.addressee.endswith(" ") or ":" in v.addressee:
        fail("addressee", "addressee cannot have trailing padding or a colon")


@invariant(Message, Acknowledgment, Radiogram)
def _message_id(v: Any) -> None:
    _pattern(v, "message_id", _ID, "requires 1..5 alphanumeric characters")


@invariant(Message, Acknowledgment)
def _reply_ack(v: Any) -> None:
    _pattern(v, "reply_ack", _REPLY_ACK, "requires 0..5 alphanumeric characters")


@invariant(Message)
def _message(v: Message) -> None:
    if "{" in v.text:
        fail("text", "{ would start a message ID")
    if v.message_id is None:
        if _ACK_TEXT.fullmatch(v.text):
            fail("text", "would be read as an acknowledgment; add a message ID")
        if v.reply_ack is not None:
            fail("reply_ack", "a reply-ack requires a message ID")


@invariant(AutoAnswer)
def _auto_answer(v: AutoAnswer) -> None:
    if "{" in v.text:
        fail("text", "{ would start an acknowledgment")
    _pattern(v, "previous_ack", _ID, "requires 1..5 alphanumeric characters")


@invariant(Bulletin)
def _bulletin(v: Bulletin) -> None:
    if not re.fullmatch(r"[0-9A-Z]", v.identifier):
        fail("identifier", "requires one bulletin digit or announcement letter")
    if v.group is not None:
        if v.announcement:
            fail("group", "group bulletins use a digit identifier")
        _length(v, "group", 1, 5)
        if v.group.endswith(" ") or ":" in v.group:
            fail("group", "group cannot have trailing padding or a colon")


@invariant(NWSBulletin)
def _nws(v: NWSBulletin) -> None:
    if not v.addressee.startswith("NWS-") or len(v.addressee) <= 4:
        fail("addressee", "requires NWS- followed by an application address")
    _pattern(v, "reference_id", _ID, "requires 1..5 alphanumeric characters")


@invariant(Status)
def _status(v: Status) -> None:
    if v.timestamp is not None and v.timestamp.kind != "dhm_utc":
        fail("timestamp", "status timestamps use DHM UTC")
    if (v.grid is None) != (v.symbol is None):
        fail("grid", "grid and symbol are supplied together")
    if v.grid is not None and v.timestamp is not None:
        fail("timestamp", "a grid status cannot include a timestamp")
    if v.timestamp is None and v.grid is None and re.match(r"[0-9]{6}z", v.text):
        fail("text", "would be read as a timestamp")


@invariant(NTSHeader, NTSAddress, NTSPhone, NTSText, NTSSignature, NTSRouting)
def _nts(v: Any) -> None:
    for name, value in vars(v).items():
        values = value if isinstance(value, tuple) else (value,)
        if any(isinstance(x, str) and "\\" in x for x in values):
            fail(name, "NTS values cannot contain the backslash separator")


@invariant(Query)
def _query(v: Query) -> None:
    if not re.fullmatch(r"[A-Z][A-Z0-9]*", v.name):
        fail("name", "requires an uppercase query token")
    if v.heard_station is not None:
        _station(v, "heard_station", v.heard_station)


@invariant(DirectStations)
def _direct(v: DirectStations) -> None:
    for i, station in enumerate(v.stations):
        _station(v, f"stations[{i}]", station)


@invariant(HeardStation)
def _heard(v: HeardStation) -> None:
    _station(v, "station", v.station)
    if any(x is not None and x < 0 for x in v.counts):
        fail("counts", "counts cannot be negative")


@invariant(Capability)
def _capability(v: Capability) -> None:
    if not v.name or any(c in " ,=" for c in v.name):
        fail("name", "requires a token without spaces, comma or equals")
    if v.value is not None and "," in v.value:
        fail("value", "values cannot contain the comma separator")


# Envelope, raw and historical ----------------------------------------------


@invariant(Hop, Header)
def _addresses(v: Any) -> None:
    for name in ("address",) if isinstance(v, Hop) else ("source", "destination"):
        value = getattr(v, name)
        if name == "destination" and value is None:
            continue
        if not value or any(c in " >,:*" for c in value):
            fail(name, "empty or invalid address token")


@invariant(UserDefined)
def _user_defined(v: UserDefined) -> None:
    _length(v, "user_id", 1, 1)
    _length(v, "user_type", 1, 1)


# Only identifiers APRS101 p17 marks unused/reserved. Assigned formats are not
# Reserved packets; Opaque keeps any other unknown bytes.
RESERVED_DTIS = frozenset(b'"&(+.-\\]^')


@invariant(Reserved)
def _reserved(v: Reserved) -> None:
    if v.dti not in RESERVED_DTIS:
        fail("dti", "requires an unused APRS101 identifier; use Opaque otherwise")


@invariant(Opaque, RawWeather, ExternalExtension)
def _raw_information(v: Any) -> None:
    _length(v, "information", 1, 2**31)
    if isinstance(v, Opaque) and v.diagnostic and v.diagnostic.code != "unsupported":
        fail("diagnostic.code", "opaque content is unsupported, not malformed")


@invariant(RawWeather)
def _raw_weather(v: RawWeather) -> None:
    prefixes = {
        "ultimeter_ii": (b"*", b"#"),
        "ultimeter_2000": (b"!!", b"$ULTW"),
        "ultw": (b"$ULTW",),
        "peet_logging": (b"!!",),
    }
    if not v.information.startswith(prefixes[v.format]):
        fail("information", "prefix does not match the declared vendor format")


@invariant(LegacyPosition)
def _legacy(v: LegacyPosition) -> None:
    if len(v.prefix) > 39 or b"!" in v.prefix:
        fail("prefix", "the position marker must be the first ! within 40 bytes")
    if v.position.timestamp is not None or v.position.messaging:
        fail("position", "a legacy ! position has no timestamp or messaging flag")


@invariant(Beacon)
def _beacon(v: Beacon) -> None:
    _length(v, "text", 1, 2**31)


@invariant(Agrelo)
def _agrelo(v: Agrelo) -> None:
    _bounds(v, "bearing_deg", 0, 360)
    _bounds(v, "quality_code", 0, 9)


@invariant(Malformed)
def _malformed(v: Malformed) -> None:
    if not v.diagnostics:
        fail("diagnostics", "at least one diagnostic is required")


# NMEA ----------------------------------------------------------------------


@invariant(NMEAMetadata)
def _nmea_metadata(v: NMEAMetadata) -> None:
    if not re.fullmatch(r"[A-Z]{2}", v.talker):
        fail("talker", "requires two uppercase ASCII letters")
    _pattern(
        v, "checksum_supplied", re.compile(r"[0-9A-Fa-f]{2}"), "requires two hex digits"
    )
    if type(v.checksum) is not bool:
        fail("checksum", "must be a bool")
    if v.checksum_valid is not None and not v.checksum:
        fail("checksum_valid", "checksum validity requires a checksum")


def _nmea_token(v: Any, name: str) -> None:
    value = getattr(v, name)
    if value is not None and any(c in value for c in ",*$"):
        fail(name, "NMEA fields cannot contain sentence delimiters")


@invariant(GGA, GLL, RMC)
def _nmea_fix(v: Any) -> None:
    active = (
        v.fix_quality != "invalid" if isinstance(v, GGA) else v.fix_status == "active"
    )
    if active and v.coordinates is None:
        fail("coordinates", "a valid fix requires coordinates")


@invariant(GGA)
def _gga(v: GGA) -> None:
    for name in ("altitude_msl", "geoid_separation"):
        reading = getattr(v, name)
        if reading is not None and reading.unit not in ("feet", "meters"):
            fail(name + ".unit", "height requires feet or meters")
    _bounds(v, "satellites", 0, 99)
    _nonnegative(v, "hdop", "dgps_age_seconds")
    # NMEA 0183 differential reference station IDs are 0000-1023.
    _bounds(v, "dgps_station", 0, 1023)


@invariant(RMC, VTG)
def _nmea_motion(v: Any) -> None:
    for name in ("course_deg", "course_true_deg", "course_magnetic_deg"):
        if hasattr(v, name):
            _bounds(v, name, 0, 360)
    for name in ("speed_knots", "speed_kmh_reported"):
        if hasattr(v, name):
            _nonnegative(v, name)


@invariant(RMC)
def _rmc(v: RMC) -> None:
    _bounds(v, "magnetic_variation_deg", -180, 180)


@invariant(WPL)
def _wpl(v: WPL) -> None:
    _length(v, "name", 1, 80)
    _nmea_token(v, "name")


@invariant(NMEA)
def _nmea(v: NMEA) -> None:
    if v.comment and not v.metadata.checksum:
        fail("comment", "a comment follows the checksum, so it requires checksum=True")
    if v.position_usable is not True:
        return
    sentence = v.sentence
    if getattr(sentence, "coordinates", None) is None:
        fail("position_usable", "a usable position requires coordinates")
    if (isinstance(sentence, (GLL, RMC)) and sentence.fix_status == "void") or (
        isinstance(sentence, GGA) and sentence.fix_quality == "invalid"
    ):
        fail("position_usable", "cannot mark an invalid fix as usable")
    if v.metadata.checksum_valid is False:
        fail("position_usable", "cannot mark a failed-checksum report as usable")


@invariant(Packet)
def _packet_destination(v: Packet) -> None:
    # Mic-E and symbol-bearing NMEA destinations are packed by the library.
    derived = isinstance(v.payload, MicE) or (
        isinstance(v.payload, NMEA) and v.payload.symbol is not None
    )
    if v.header.destination is None and not derived:
        fail(
            "header.destination",
            "destination is required except for Mic-E and NMEA with a symbol",
        )


@invariant(Trace)
def _trace_header(v: Trace) -> None:
    if v.header.destination is None:
        fail("header.destination", "trace headers require an explicit destination")


@invariant(UTCTime)
def _utc_time(v: UTCTime) -> None:
    _bounds(v, "hour", 0, 23)
    _bounds(v, "minute", 0, 59)
    if v.second is not None and not 0 <= v.second < 61:
        fail("second", "requires seconds in [0, 61), allowing a leap second")
    if v.second is not None and v.second >= 60 and (v.hour, v.minute) != (23, 59):
        fail("second", "a UTC leap second belongs to 23:59")


@invariant(NMEADate)
def _nmea_date(v: NMEADate) -> None:
    _bounds(v, "day", 1, 31)
    _bounds(v, "month", 1, 12)
    _bounds(v, "year_mod_100", 0, 99)
    if v.day is not None and v.month is not None:
        # 00 might belong to a leap century; never resolve that century here.
        year = 2000 + (v.year_mod_100 or 0)
        if v.day > calendar.monthrange(year, v.month)[1]:
            fail("day", "day does not exist in the supplied month/year")
