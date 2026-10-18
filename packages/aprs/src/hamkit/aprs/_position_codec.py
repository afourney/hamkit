# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Position wire primitives, including ambiguity and base-91 compression."""

from __future__ import annotations

import math
from dataclasses import replace
from decimal import Decimal

from ._data import Altitude, Compression, Extensions, Measurement, Motion, Range, Symbol
from ._errors import FieldError
from ._fields.position import CoordinateAxis, decode_coordinate, encode_coordinate


def base91(raw: bytes) -> int:
    if not raw or any(not 33 <= c <= 123 for c in raw):
        raise FieldError("invalid base-91 field")
    value = 0
    for c in raw:
        value = value * 91 + c - 33
    return value


def pack91(value: int, width: int) -> bytes:
    if not 0 <= value < 91**width:
        raise FieldError("value outside base-91 field range")
    result = bytearray(width)
    for i in range(width - 1, -1, -1):
        value, digit = divmod(value, 91)
        result[i] = digit + 33
    return bytes(result)


def ambiguity(raw: bytes) -> int:
    digits = raw[:-1].replace(b".", b"")
    n = len(digits) - len(digits.rstrip(b" "))
    if n > 4 or b" " in digits[: -n or None]:
        raise FieldError("ambiguity must hide trailing minute digits")
    return n


def center(value: float, n: int) -> float:
    if not n:
        return value
    cell = (0.1, 1, 10, 60)[n - 1]
    return math.copysign(
        (int(Decimal(str(abs(value))) * 60 // Decimal(str(cell))) + 0.5) * cell / 60,
        value,
    )


def center_wire(value: float, n: int) -> float:
    """Center a decoded hundredth-minute value without float boundary drift."""
    if not n:
        return value
    cell_units = (10, 100, 1000, 6000)[n - 1]
    units = round(abs(value) * 6000)
    return math.copysign((units // cell_units + 0.5) * cell_units / 6000, value)


def coordinates(lat: bytes, lon: bytes) -> tuple[float, float, int]:
    n, m = ambiguity(lat), ambiguity(lon)
    if m > n:
        raise FieldError("longitude cannot be more ambiguous than latitude")
    return (
        center_wire(decode_coordinate(lat.replace(b" ", b"0"), "latitude"), n),
        center_wire(decode_coordinate(lon.replace(b" ", b"0"), "longitude"), n),
        n,
    )


def coordinate_bytes(value: float, axis: CoordinateAxis, n: int) -> bytes:
    raw = bytearray(encode_coordinate(center(value, n), axis))
    for i in (len(raw) - 2, len(raw) - 3, len(raw) - 5, len(raw) - 6)[:n]:
        raw[i] = 32
    return bytes(raw)


def compressed(
    raw: bytes,
) -> tuple[float, float, Symbol, Compression, Extensions, bytes]:
    if len(raw) < 13:
        raise FieldError("truncated compressed position")
    if raw[0] not in b"/\\ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij":
        raise FieldError("invalid compressed symbol table")
    lat, lon = 90 - base91(raw[1:5]) / 380926, -180 + base91(raw[5:9]) / 190463
    symbol = Symbol(chr(raw[0]), chr(raw[9]))
    cs = raw[10:13]
    e = Extensions()
    if cs[0] == 32:
        compression = Compression(ignored=True, raw=cs)
    else:
        c, s, t = (base91(bytes([b])) for b in cs)
        t &= 63
        compression = Compression(
            fix="current" if t & 32 else "old",
            nmea_source=("other", "GLL", "GGA", "RMC")[(t >> 3) & 3],
            origin_code=t & 7,
            raw=cs,
        )
        if t & 24 == 16:
            e = Extensions(
                altitude=Altitude(
                    Measurement(1.002 ** (c * 91 + s), "feet"), "compressed"
                )
            )
        elif c == 90:
            e = Extensions(range=Range(2 * 1.08**s))
        else:
            e = Extensions(motion=Motion(c * 4, 1.08**s - 1))
    return lat, lon, symbol, compression, e, raw[13:]


def compressed_bytes(p) -> tuple[bytes, Extensions]:
    c = p.compression
    e = p.extensions
    if c.ignored:
        cs = b"   "
    elif e.altitude is not None and e.altitude.encoding == "compressed":
        if e.altitude.reference != "unspecified":
            raise FieldError(
                "compressed altitude reference is not an independent wire field"
            )
        from ._units import height

        feet = height(e.altitude.measurement, "feet")
        if feet <= 0 or c.nmea_source != "GGA":
            raise FieldError(
                "compressed altitude requires positive height and GGA source"
            )
        cs = pack91(round(math.log(feet, 1.002)), 2) + pack91(c.type_value, 1)
        e = replace(e, altitude=None)
    elif e.range is not None:
        if e.range.miles < 2:
            raise FieldError("compressed range must be at least two miles")
        cs = (
            b"{"
            + pack91(round(math.log(e.range.miles / 2, 1.08)), 1)
            + pack91(c.type_value, 1)
        )
        e = replace(e, range=None)
    else:
        m = e.motion
        if e.weather is not None:
            from ._weather import _value

            w = e.weather
            m = Motion(
                w.wind_direction.value if w.wind_direction else None,
                _value(w.wind_speed, "knots") if w.wind_speed else None,
            )
            e = replace(e, weather=replace(w, wind_direction=None, wind_speed=None))
        if m is None or m.course_deg is None or m.speed_knots is None:
            raise FieldError("active compression requires motion, range, or altitude")
        if c.nmea_source == "GGA":
            raise FieldError("GGA compression encodes altitude, not motion")
        course = round(m.course_deg / 4)
        if course == 90:
            course = 0
        cs = (
            pack91(course, 1)
            + pack91(round(math.log(m.speed_knots + 1, 1.08)), 1)
            + pack91(c.type_value, 1)
        )
        e = replace(e, motion=None)
    raw = (
        p.symbol.table_id.encode()
        + pack91(round((90 - p.latitude_deg) * 380926), 4)
        + pack91(round((180 + p.longitude_deg) * 190463), 4)
        + p.symbol.code.encode()
        + cs
    )
    return raw, e


def dao_offset(value: float, dao, axis: str) -> float:
    # Receive-only: decode precision from the received extension evidence.
    if dao is None or dao.encoding is None:
        return value
    if dao.raw is None:
        raise FieldError("received DAO precision bytes are missing")
    code = dao.raw[2 if axis == "latitude" else 3]
    increment = (
        (code - 48) / 60000 if dao.encoding == "decimal" else (code - 33) / (91 * 6000)
    )
    return math.copysign(abs(value) + increment, value)
