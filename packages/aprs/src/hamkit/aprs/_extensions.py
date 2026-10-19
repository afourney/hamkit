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
from typing import Any, cast

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
from ._errors import CodecNotImplementedError, FieldError, Unrepresentable
from ._policy import _DEFAULT_POLICY, EnvelopePolicy
from ._text import token

_FIELD = rb"(\d{3}|\.{3}| {3})"
_COURSE_SPEED = re.compile(_FIELD + rb"/" + _FIELD)
_BEARING = re.compile(rb"/(\d{3})/(\d)(\d)(\d)")
_PHG = re.compile(rb"PHG(\d)([0-9:;])(\d)([0-8])")
_PHGR_RATES = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_RNG = re.compile(rb"RNG(\d{4})")
_DFS = re.compile(rb"DFS(\d)([0-9:;])(\d)([0-8])")
_ALTITUDE = re.compile(rb"/A=(-\d{5}|\d{6})")
_DAO = re.compile(rb"![A-Za-z][\x21-\x7b]{2}!")
_BASE91_TELEMETRY = re.compile(rb"\|(?:[\x21-\x7b]{2}){2,7}\|")
# Text that looks like an extension but was not decoded, so it holds bad values.
_LOOKALIKE_PREFIX = re.compile(rb"[0-9. ]{3}/[0-9. ]{3}|PHG|RNG|DFS")


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


def weather_follows(symbol: Symbol, tail: bytes) -> bool:
    """Whether a weather report starts here. Under _ (APRS101 pp62-65) any
    wind or weather field does; /W and \\W are accepted as alternate weather
    symbols (aprs.org/aprs11/spec-wx.txt) only when weather fields follow, as
    the symbol is also used by moving stations whose ddd/sss is course/speed."""
    if symbol.code == "_":
        return bool(_COURSE_SPEED.match(tail)) or tail.startswith((b"g", b"t", b"c"))
    if symbol.code == "W":
        if _COURSE_SPEED.match(tail):
            tail = tail[7:]
        return tail.startswith((b"g", b"t"))
    return False


def read(
    tail: bytes,
    symbol: Symbol,
    policy: EnvelopePolicy = _DEFAULT_POLICY,
    *,
    compressed: bool = False,
) -> tuple[Extensions, bytes]:
    """Split decoded extensions from the information after the symbol.

    After a compressed position, PHG, DF signal, area and DF bearing data are
    plain comment text: the compressed layout does not carry them (APRS101
    p36: "this format does not support PHG").
    """

    found: dict[str, Any] = {}
    if weather_follows(symbol, tail):
        from . import _weather

        weather, tail = _weather.read(
            tail,
            positioned=True,
            compressed=not bool(_COURSE_SPEED.match(tail)),
            policy=policy,
        )
        found["weather"] = weather
    elif (
        not compressed
        and (symbol.table_id, symbol.code) == ("\\", "l")
        and (
            match := re.match(
                rb"(\d)(\d{2})(/[0-9]|1[0-5])(\d{2})(?:\{([0-9.]+)\})?", tail
            )
        )
    ):
        color = int(match[3].lstrip(b"/"))
        found["area"] = d.Area(
            d.AREA_SHAPES[int(match[1])],
            d.AREA_COLORS[color % 8],
            int(match[2]) ** 2 / 1500,
            int(match[4]) ** 2 / 1500,
            intensity="low" if color >= 8 else "high",
            corridor_half_width_miles=float(match[5]) if match[5] else None,
        )
        tail = tail[match.end() :]
    elif match := _COURSE_SPEED.match(tail):
        if (motion := _motion(match, _is_df(symbol))) is not None:
            found["motion"] = motion
            tail = tail[7:]
            bearing = (
                _BEARING.match(tail) if _is_df(symbol) and not compressed else None
            )
            if bearing and int(bearing[1]) <= 360:
                hits, range_code, quality = (int(bearing[i]) for i in (2, 3, 4))
                meaningful = hits != 0
                found["bearing"] = Bearing(
                    int(bearing[1]),
                    float(2**range_code) if meaningful else None,
                    d.DF_ACCURACY[quality] if meaningful else None,
                    hit_ratio=hits / 8 if 1 <= hits <= 8 else None,
                    manual=hits == 9,
                    raw=bearing[0],
                )
                tail = tail[8:]
    elif not compressed and (match := _PHG.match(tail)):
        found["phg"] = PHG(
            int(match[1]) ** 2,
            _height(match[2]),
            int(match[3]),
            directivity_deg=_directivity(match[4]),
            raw=match[0][3:],
        )
        tail = tail[7:]
        # PHGR (aprs.org/aprs12/probes.txt) requires both the rate character
        # and its delimiter. Without '/', a digit/letter belongs to the comment.
        if "phg_rate" in policy.extensions and re.match(rb"[0-9A-Z]/", tail):
            found["phg"] = replace(
                found["phg"], rate_per_hour=_PHGR_RATES.index(tail[0])
            )
            tail = tail[2:]
        elif (
            "phg_rate" in policy.extensions
            and tail.startswith(b"/")
            and not _ALTITUDE.match(tail)
        ):
            # The older PHG form also commonly separates its comment with '/'.
            # Consume one delimiter, but leave /A= altitude for the decoder below.
            tail = tail[1:]
    elif match := _RNG.match(tail):
        found["range"] = Range(int(match[1]), raw=match[0])
        tail = tail[7:]
    elif not compressed and (match := _DFS.match(tail)):
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
            next(k for k, code in d.STORM_CODES.items() if code == match[1].decode()),
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
    if "base91_telemetry" in policy.extensions and (
        match := _BASE91_TELEMETRY.search(tail)
    ):
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
    if "dao" in policy.extensions and (
        match := re.search(rb"!([A-Za-z])([\x20-\x7b]{2})!", tail)
    ):
        datum = match[1].decode()
        pair = match[2]
        if pair == b"  ":
            dao = d.DAO(datum.upper(), raw=match[0])
        elif datum.isupper() and pair.isdigit():
            dao = d.DAO(
                datum.upper(),
                precision="high",
                raw=match[0],
            )
        elif datum.islower() and all(33 <= c <= 123 for c in pair):
            dao = d.DAO(
                datum.upper(),
                precision="highest",
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
            Measurement(feet, "feet", raw=match[1]), encoding="feet_extension"
        )
        tail = tail[: match.start()] + tail[match.end() :]
    if "phg" in found and "phg_rate" in policy.extensions:
        # PHG/PHGR's presentation convention ignores surrounding whitespace.
        # This is not a general rule for message text or other position comments.
        tail = tail.strip()
    return Extensions(**found), tail


def lookalikes(
    extensions: Extensions, comment: bytes, symbol: Symbol, *, compressed: bool = False
) -> list[tuple[str, str]]:
    """Comment text shaped like an extension that did not decode (invalid values)."""
    findings = []
    primary = ("motion", "phg", "range", "signal")
    prefix = _LOOKALIKE_PREFIX.match(comment)
    # After a compressed position, PHG and DFS text is ordinary comment.
    if compressed and prefix and prefix[0] in (b"PHG", b"DFS"):
        prefix = None
    if not any(getattr(extensions, n) for n in primary) and prefix:
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


def _rounded(path: str, value: float | None, low: int, high: int) -> int:
    """A measurement quantized to the wire's whole units, like coordinates."""
    number = None if value is None else round(value)
    if number is None or not low <= number <= high:
        raise Unrepresentable(path, f"requires {low}..{high} after rounding")
    return number


# Coded quantities round to the nearest value the wire carries, like
# coordinates; only a value outside the code range after rounding is refused.


def _power_code(path: str, watts: float) -> int:
    """PHG power n² watts."""
    n = round(math.sqrt(watts)) if watts >= 0 else -1
    if not 0 <= n <= 9:
        raise Unrepresentable(path, "beyond the largest PHG power code (81 watts)")
    return n


def _height_code(path: str, feet: float) -> bytes:
    """10 × 2ⁿ feet, rounded on the logarithmic scale."""
    exponent = round(math.log2(feet / 10)) if feet > 0 else -1
    if not 0 <= exponent <= 11:
        raise Unrepresentable(path, "outside the height codes (10 to 20480 feet)")
    return bytes([ord("0") + exponent])


def _directivity_code(path: str, degrees: float | None) -> bytes:
    """None is omnidirectional; a direction rounds to the nearest 45 degrees."""
    if degrees is None:
        return b"0"
    if not 0 <= degrees <= 360:
        raise Unrepresentable(path, "requires 0..360 degrees, or None")
    octant = round(degrees / 45) % 8
    return str(octant or 8).encode()  # North is 8 (360); 0 means omni.


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


def _write_primary(
    extensions: Extensions,
    symbol: Symbol,
    comment: bytes = b"",
    policy: EnvelopePolicy = _DEFAULT_POLICY,
) -> bytes:
    """The bytes read() would split back into these extensions."""
    e = extensions
    for name in ("dao", "area", "signpost", "weather", "storm", "telemetry"):
        if getattr(e, name) is not None:
            raise CodecNotImplementedError(f"{name} position extension encoding")
    if e.altitude is not None and e.altitude.encoding != "feet_extension":
        raise CodecNotImplementedError(f"{e.altitude.encoding} altitude encoding")
    if e.altitude is not None and e.altitude.reference != "unspecified":
        raise Unrepresentable(
            "$.extensions.altitude.reference", "the /A= altitude has no reference field"
        )
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
        power = _power_code("$.extensions.phg.power_w", p.power_w)
        raw += b"PHG%d" % power + _height_code(
            "$.extensions.phg.height_haat_ft", p.height_haat_ft
        )
        raw += b"%d" % _rounded("$.extensions.phg.gain_dbi", p.gain_dbi, 0, 9)
        raw += _directivity_code("$.extensions.phg.directivity_deg", p.directivity_deg)
        if p.rate_per_hour is not None:
            if not 0 <= p.rate_per_hour < len(_PHGR_RATES):
                raise Unrepresentable(
                    "$.extensions.phg.rate_per_hour", "requires 0..35 (0-9 or A-Z)"
                )
            # Terminate PHGR before altitude or other extensions, too.
            raw += _PHGR_RATES[p.rate_per_hour : p.rate_per_hour + 1] + b"/"
        elif "phg_rate" in policy.extensions and (
            comment.startswith(b"/") or re.match(rb"[0-9A-Z]/", comment)
        ):
            # The optional separator protects comments that would otherwise
            # lose their leading slash or be read as a PHGR rate.
            raw += b"/"
    elif e.range is not None:
        raw += b"RNG%04d" % _rounded("$.extensions.range.miles", e.range.miles, 0, 9999)
    elif e.signal is not None:
        s = e.signal
        raw += b"DFS%d" % s.s_units + _height_code(
            "$.extensions.signal.height_haat_ft", s.height_haat_ft
        )
        raw += b"%d" % _rounded("$.extensions.signal.gain_db", s.gain_db, 0, 9)
        raw += _directivity_code(
            "$.extensions.signal.directivity_deg", s.directivity_deg
        )
    if e.altitude is not None:
        reading = e.altitude.measurement
        from ._units import height

        feet = _rounded(
            "$.extensions.altitude.measurement.value",
            height(reading, "feet"),
            -99999,
            999999,
        )
        raw += b"/A=-%05d" % -feet if feet < 0 else b"/A=%06d" % feet
    return raw


def write(
    extensions: Extensions,
    symbol: Symbol,
    comment: bytes = b"",
    policy: EnvelopePolicy = _DEFAULT_POLICY,
    *,
    coordinates: tuple[float, float] | None = None,
) -> bytes:
    e = extensions
    if e.dao is not None and "dao" not in policy.extensions:
        raise FieldError("DAO requires dao extension")
    if e.telemetry is not None and "base91_telemetry" not in policy.extensions:
        raise FieldError("comment telemetry requires base91_telemetry extension")
    if (
        e.phg
        and e.phg.rate_per_hour is not None
        and "phg_rate" not in policy.extensions
    ):
        raise FieldError("PHGR requires phg_rate extension")
    extra = b""
    if e.weather:
        from . import _weather

        extra += _weather.write(
            e.weather,
            positioned=True,
            compressed=e.weather.wind_direction is None
            and e.weather.wind_speed is None,
            policy=policy,
            path="$.extensions.weather",
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
            + d.STORM_CODES[s.kind].encode()
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
        from ._dao import encode

        extra += encode(e.dao, coordinates)
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
    return _write_primary(primary, symbol, comment, policy) + extra
