# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""APRS position extensions and their shared read/write grammar.

Decode motion, radio/DF fields, weather, storm/area/signpost descriptors, altitude,
DAO and telemetry. Invalid extension-shaped text remains inspectable as comment
with a conformance finding. Wire evidence never overrides semantic fields.
"""

from __future__ import annotations

import math
import re
from dataclasses import replace
from typing import Any, Literal, cast

from . import _data as d
from ._data import (
    PHG,
    Altitude,
    Bearing,
    Extensions,
    Measurement,
    Motion,
    Range,
    Signal,
    Symbol,
)
from ._errors import CodecNotImplementedError, FieldError
from ._text import token

_FIELD = rb"(\d{3}|\.{3}| {3})"
_COURSE_SPEED = re.compile(_FIELD + rb"/" + _FIELD)
_BEARING = re.compile(rb"/(\d{3})/(\d)(\d)(\d)")
_PHG = re.compile(rb"PHG(\d)([0-9:;])(\d)([0-8])")
_RNG = re.compile(rb"RNG(\d{4})")
_DFS = re.compile(rb"DFS(\d)([0-9:;])(\d)([0-8])")
_ALTITUDE = re.compile(rb"/A=(-\d{5}|\d{6})")
_DAO = re.compile(rb"![A-Za-z][\x21-\x7b]{2}!")
_BASE91_TELEMETRY = re.compile(rb"\|(?:[\x21-\x7b]{2}){2,7}\|")
# Text that looks like an extension but was not decoded, so it holds bad values.
_LOOKALIKE_PREFIX = re.compile(rb"[0-9. ]{3}/[0-9. ]{3}|PHG|RNG|DFS")


class Unrepresentable(FieldError):
    """A structured value has no exact form in the uncompressed extension grammar."""

    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


def _is_df(symbol: Symbol) -> bool:
    return (symbol.table_id, symbol.code) == ("/", "\\")


def _height(code: bytes) -> float:
    return 10.0 * 2 ** (code[0] - ord("0"))


def _directivity(code: bytes) -> float | None:
    return None if code == b"0" else 45.0 * int(code)


def _motion(match: re.Match[bytes], df: bool) -> Motion | None:
    course, speed = match[1], match[2]
    if not course.isdigit() or not speed.isdigit():
        if course.isdigit() or speed.isdigit():
            return None  # Half-numeric fields are not a defined extension.
        return Motion(raw=match[0])
    c, s = int(course), int(speed)
    if c > 360:
        return None
    if c == 0 and s == 0:
        if df:
            return Motion(
                None, 0, zero_pair="fixed", course_code=0, speed_code=0, raw=match[0]
            )
        return Motion(
            None,
            None,
            zero_pair="unavailable",
            course_code=0,
            speed_code=0,
            raw=match[0],
        )
    # Course code 000 means unknown; north is 360.
    return Motion(None if c == 0 else c, s, course_code=c, speed_code=s, raw=match[0])


def read(tail: bytes, symbol: Symbol) -> tuple[Extensions, bytes]:
    """Split decoded extensions from the information after an uncompressed symbol."""

    found: dict[str, Any] = {}
    if symbol.code in "_W" and (
        _COURSE_SPEED.match(tail) or tail.startswith((b"g", b"t", b"c"))
    ):
        from . import _weather

        weather, tail = _weather.read(
            tail, positioned=True, compressed=not bool(_COURSE_SPEED.match(tail))
        )
        found["weather"] = weather
    elif (symbol.table_id, symbol.code) == ("\\", "l") and (
        match := re.match(rb"(\d)(\d{2})(/[0-9]|1[0-5])(\d{2})(?:\{([0-9.]+)\})?", tail)
    ):
        found["area"] = d.Area(
            int(match[1]),
            int(match[3].lstrip(b"/")),
            int(match[2]),
            int(match[4]),
            corridor_half_width_miles=float(match[5]) if match[5] else None,
        )
        tail = tail[match.end() :]
    elif match := _COURSE_SPEED.match(tail):
        if (motion := _motion(match, _is_df(symbol))) is not None:
            found["motion"] = motion
            tail = tail[7:]
            bearing = _BEARING.match(tail) if _is_df(symbol) else None
            if bearing and int(bearing[1]) <= 360:
                found["bearing"] = Bearing(
                    int(bearing[1]),
                    int(bearing[2]),
                    int(bearing[3]),
                    int(bearing[4]),
                    raw=bearing[0],
                )
                tail = tail[8:]
    elif match := _PHG.match(tail):
        found["phg"] = PHG(
            int(match[1]) ** 2,
            _height(match[2]),
            int(match[3]),
            directivity_deg=_directivity(match[4]),
            raw=match[0][3:],
        )
        tail = tail[7:]
        if re.match(rb"[0-9](?:/|$)", tail):
            found["phg"] = replace(found["phg"], rate_per_hour=int(tail[:1]))
            tail = tail[1:]
    elif match := _RNG.match(tail):
        found["range"] = Range(int(match[1]), raw=match[0])
        tail = tail[7:]
    elif match := _DFS.match(tail):
        found["signal"] = Signal(
            int(match[1]),
            _height(match[2]),
            int(match[3]),
            directivity_deg=_directivity(match[4]),
            raw=match[0],
        )
        tail = tail[7:]
    if symbol.code == "@" and (
        match := re.match(
            rb"/(HC|TS|TD)/(\d{3})\^(\d{3})/(\d{4})>(\d{3})&(\d{3})(?:%(\d{3}))?", tail
        )
    ):
        found["storm"] = d.Storm(
            cast(Literal["HC", "TS", "TD"], match[1].decode()),
            predicted=symbol.table_id == "/",
            sustained_wind_knots=int(match[2]),
            peak_gust_knots=int(match[3]),
            central_pressure_hpa=int(match[4]),
            hurricane_radius_nm=int(match[5]),
            tropical_storm_radius_nm=int(match[6]),
            whole_gale_radius_nm=int(match[7]) if match[7] else None,
        )
        tail = tail[match.end() :]
    if (symbol.table_id, symbol.code) == ("\\", "m") and (
        match := re.search(rb"\{([^{}]{1,3})\}", tail)
    ):
        found["signpost"] = d.Signpost(token(match[1], "$.extensions.signpost.label"))
        tail = tail[: match.start()] + tail[match.end() :]
    if match := _BASE91_TELEMETRY.search(tail):
        from ._position_codec import base91

        raw = match[0][1:-1]
        values = [base91(raw[i : i + 2]) for i in range(0, len(raw), 2)]
        digital = (
            tuple(bool(values[-1] & (1 << i)) for i in range(8))
            if len(values) == 7
            else ()
        )
        found["telemetry"] = d.Telemetry(
            tuple(values[1:6]),
            digital,
            sequence=values[0],
            encoding="base91_comment",
            raw=match[0],
        )
        tail = tail[: match.start()] + tail[match.end() :]
    if match := re.search(rb"!([A-Za-z])([\x20-\x7b]{2})!", tail):
        datum = match[1].decode()
        pair = match[2]
        if pair == b"  ":
            dao = d.DAO(datum, raw=match[0])
        elif datum.isupper() and pair.isdigit():
            dao = d.DAO(
                datum,
                latitude_precision=int(chr(pair[0])),
                longitude_precision=int(chr(pair[1])),
                encoding="decimal",
                raw=match[0],
            )
        elif datum.islower() and all(33 <= c <= 123 for c in pair):
            dao = d.DAO(
                datum,
                latitude_precision=pair[0] - 33,
                longitude_precision=pair[1] - 33,
                encoding="base91",
                raw=match[0],
            )
        else:
            dao = None
        if dao:
            found["dao"] = dao
            tail = tail[: match.start()] + tail[match.end() :]
    if match := _ALTITUDE.search(tail):
        feet = int(match[1])
        found["altitude"] = Altitude(
            Measurement(feet, "feet", raw=match[1]), "feet_extension"
        )
        tail = tail[: match.start()] + tail[match.end() :]
    return Extensions(**found), tail


def lookalikes(
    extensions: Extensions, comment: bytes, symbol: Symbol
) -> list[tuple[str, str]]:
    """Comment text shaped like an extension that did not decode (invalid values)."""
    findings = []
    primary = ("motion", "phg", "range", "signal")
    if not any(getattr(extensions, n) for n in primary) and _LOOKALIKE_PREFIX.match(
        comment
    ):
        findings.append(("$.comment", "begins with an invalid data extension"))
    if b"/A=" in comment:
        findings.append(("$.comment", "contains an invalid /A= altitude"))
    if (
        _is_df(symbol)
        and extensions.motion is not None
        and extensions.bearing is None
        and _BEARING.match(comment)
    ):
        findings.append(("$.comment", "contains an invalid DF bearing"))
    return findings


def _code(path: str, value: float | None, low: int, high: int) -> int:
    """An exact code-table value, such as a PHG gain digit."""
    if value is None or value != int(value) or not low <= value <= high:
        raise Unrepresentable(path, f"requires a whole number in {low}..{high}")
    return int(value)


def _rounded(path: str, value: float | None, low: int, high: int) -> int:
    """A measurement quantized to the wire's whole units, like coordinates."""
    number = None if value is None else round(value)
    if number is None or not low <= number <= high:
        raise Unrepresentable(path, f"requires {low}..{high} after rounding")
    return number


def _height_code(path: str, feet: float) -> bytes:
    exponent = math.log2(feet / 10) if feet >= 10 else -1
    if exponent != int(exponent) or not 0 <= exponent <= 11:
        raise Unrepresentable(path, "requires 10 × 2ⁿ feet for n in 0..11")
    return bytes([ord("0") + int(exponent)])


def _directivity_code(path: str, degrees: float | None) -> bytes:
    if degrees is None:
        return b"0"
    if degrees % 45 or not 45 <= degrees <= 360:
        raise Unrepresentable(path, "requires a multiple of 45 in 45..360, or None")
    return str(int(degrees // 45)).encode()


def _motion_bytes(m: Motion) -> bytes:
    if m.course_deg is None and m.speed_knots is None:
        return b"000/000" if m.zero_pair == "unavailable" else b".../..."
    if m.speed_knots is None:
        raise Unrepresentable(
            "$.extensions.motion.speed_knots", "a known course requires a speed"
        )
    speed = _rounded("$.extensions.motion.speed_knots", m.speed_knots, 0, 999)
    if m.course_deg is None:
        course = 0  # Unknown course; with speed 0 it reads as a fixed DF station.
    else:
        course = _rounded("$.extensions.motion.course_deg", m.course_deg, 0, 360)
        course = course or 360  # 000 would mean unknown; north is sent as 360.
    return b"%03d/%03d" % (course, speed)


def _write_primary(extensions: Extensions, symbol: Symbol) -> bytes:
    """The bytes read() would split back into these extensions."""
    e = extensions
    for name in ("dao", "area", "signpost", "weather", "storm", "telemetry"):
        if getattr(e, name) is not None:
            raise CodecNotImplementedError(f"{name} position extension encoding")
    if e.altitude is not None and e.altitude.encoding != "feet_extension":
        raise CodecNotImplementedError(f"{e.altitude.encoding} altitude encoding")
    if e.altitude is not None and e.altitude.reference != "unspecified":
        raise CodecNotImplementedError("altitude reference cannot be encoded in /A=")
    if e.bearing is not None and (
        e.bearing.usable is not None or e.bearing.accuracy_less_than_deg is not None
    ):
        raise CodecNotImplementedError("DF bearing annotations have no wire encoding")
    raw = b""
    if e.motion is not None:
        raw += _motion_bytes(e.motion)
        match = _COURSE_SPEED.fullmatch(raw)
        assert match is not None
        decoded = _motion(match, _is_df(symbol))
        assert decoded is not None
        for name in ("course_deg", "speed_knots"):
            if (getattr(e.motion, name) is None) != (getattr(decoded, name) is None):
                raise Unrepresentable(
                    f"$.extensions.motion.{name}",
                    "wire form would change whether the measurement is known",
                )
        if (
            e.motion.zero_pair != "unspecified"
            and e.motion.zero_pair != decoded.zero_pair
        ):
            raise Unrepresentable(
                "$.extensions.motion.zero_pair",
                "wire form would change the zero-pair interpretation",
            )
        if e.bearing is not None:
            b = e.bearing
            raw += b"/%03d/%d%d%d" % (
                _rounded("$.extensions.bearing.bearing_deg", b.bearing_deg, 0, 360),
                b.hits_code,
                b.range_code,
                b.quality_code,
            )
    elif e.phg is not None:
        p = e.phg
        power = math.isqrt(int(p.power_w)) if p.power_w == int(p.power_w) else -1
        if power * power != p.power_w or power > 9:
            raise Unrepresentable(
                "$.extensions.phg.power_w", "requires n² watts, n 0..9"
            )
        raw += b"PHG%d" % power + _height_code(
            "$.extensions.phg.height_haat_ft", p.height_haat_ft
        )
        raw += b"%d" % _code("$.extensions.phg.gain_dbi", p.gain_dbi, 0, 9)
        raw += _directivity_code("$.extensions.phg.directivity_deg", p.directivity_deg)
    elif e.range is not None:
        raw += b"RNG%04d" % _rounded("$.extensions.range.miles", e.range.miles, 0, 9999)
    elif e.signal is not None:
        s = e.signal
        raw += b"DFS%d" % s.s_units + _height_code(
            "$.extensions.signal.height_haat_ft", s.height_haat_ft
        )
        raw += b"%d" % _code("$.extensions.signal.gain_db", s.gain_db, 0, 9)
        raw += _directivity_code(
            "$.extensions.signal.directivity_deg", s.directivity_deg
        )
    if e.altitude is not None:
        reading = e.altitude.measurement
        if reading.unit != "feet":
            raise Unrepresentable(
                "$.extensions.altitude.measurement.unit", "/A= altitude is in feet"
            )
        feet = _rounded(
            "$.extensions.altitude.measurement.value", reading.value, -99999, 999999
        )
        raw += b"/A=-%05d" % -feet if feet < 0 else b"/A=%06d" % feet
    return raw


def write(extensions: Extensions, symbol: Symbol) -> bytes:
    e = extensions
    extra = b""
    if e.weather:
        from . import _weather

        extra += _weather.write(
            e.weather,
            positioned=True,
            compressed=e.weather.wind_direction is None
            and e.weather.wind_speed is None,
        )
    if e.area:
        a = e.area
        extra += (
            b"%d%02d" % (a.shape_code, a.latitude_offset_code)
            + (b"/%d" % a.color_code if a.color_code < 10 else b"%02d" % a.color_code)
            + b"%02d" % a.longitude_offset_code
        )
        if a.corridor_half_width_miles is not None:
            extra += b"{" + f"{a.corridor_half_width_miles:g}".encode() + b"}"
    if e.storm:
        s = e.storm
        extra += (
            b"/"
            + s.kind.encode()
            + b"/%03d^%03d/%04d>%03d&%03d"
            % (
                _rounded(
                    "$.extensions.storm.sustained_wind_knots",
                    s.sustained_wind_knots,
                    0,
                    999,
                ),
                _rounded(
                    "$.extensions.storm.peak_gust_knots", s.peak_gust_knots, 0, 999
                ),
                _rounded(
                    "$.extensions.storm.central_pressure_hpa",
                    s.central_pressure_hpa,
                    0,
                    9999,
                ),
                _rounded(
                    "$.extensions.storm.hurricane_radius_nm",
                    s.hurricane_radius_nm,
                    0,
                    999,
                ),
                _rounded(
                    "$.extensions.storm.tropical_storm_radius_nm",
                    s.tropical_storm_radius_nm,
                    0,
                    999,
                ),
            )
        )
        if s.whole_gale_radius_nm is not None:
            extra += b"%%%03d" % _rounded(
                "$.extensions.storm.whole_gale_radius_nm",
                s.whole_gale_radius_nm,
                0,
                999,
            )
    if e.signpost:
        extra += b"{" + e.signpost.label.encode() + b"}"
    if e.dao:
        dao = e.dao
        if not dao.datum_byte.isascii() or not dao.datum_byte.isalpha():
            raise Unrepresentable(
                "$.extensions.dao.datum_byte", "DAO requires a datum letter"
            )
        if dao.encoding is not None and (
            dao.latitude_precision is None or dao.longitude_precision is None
        ):
            raise FieldError("DAO precision is required")
        pair = (
            b"  "
            if dao.encoding is None
            else bytes(
                [
                    cast(int, dao.latitude_precision)
                    + (48 if dao.encoding == "decimal" else 33),
                    cast(int, dao.longitude_precision)
                    + (48 if dao.encoding == "decimal" else 33),
                ]
            )
        )
        extra += b"!" + dao.datum_byte.encode() + pair + b"!"
    if e.telemetry:
        from ._position_codec import pack91

        t = e.telemetry
        if t.encoding != "base91_comment" or not isinstance(t.sequence, int):
            raise FieldError("comment telemetry requires base91 encoding and sequence")
        values = [t.sequence, *t.analog]
        if t.digital:
            if len(t.analog) != 5:
                raise FieldError("digital comment telemetry requires five analog slots")
            values.append(sum(int(bool(v)) << i for i, v in enumerate(t.digital)))
        if any(v is None or v != int(v) for v in values):
            raise FieldError("base91 telemetry requires integer channels")
        extra += b"|" + b"".join(pack91(int(cast(float, v)), 2) for v in values) + b"|"
    primary = replace(
        e, dao=None, area=None, signpost=None, weather=None, storm=None, telemetry=None
    )
    if primary.phg and primary.phg.rate_per_hour is not None:
        rate = primary.phg.rate_per_hour
        primary = replace(primary, phg=replace(primary.phg, rate_per_hour=None))
        return _write_primary(primary, symbol) + str(rate).encode() + extra
    return _write_primary(primary, symbol) + extra
