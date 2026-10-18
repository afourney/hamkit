# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""NMEA sentence codecs. Checksums and fix validity do not imply each other."""

from __future__ import annotations

import functools
import math
import operator
import re
from typing import Any, cast

from . import _nmea as n
from ._data import Coordinates, Measurement, Symbol
from ._errors import CodecNotImplementedError, FieldError, Unrepresentable
from ._models import NMEA, Header
from ._policy import _DEFAULT_POLICY, EnvelopePolicy
from ._text import free_text, token


def _coordinate(number: str, hemisphere: str, width: int) -> float:
    if (
        not re.fullmatch(r"\d{" + str(width + 2) + r"}(?:\.\d+)?", number)
        or hemisphere not in ("NS" if width == 2 else "EW")
        or len(hemisphere) != 1
    ):
        raise FieldError("invalid NMEA coordinate")
    deg = int(number[:width])
    minutes = float(number[width:])
    if minutes >= 60:
        raise FieldError("NMEA coordinate minutes exceed 60")
    value = deg + minutes / 60
    return -value if hemisphere in "SW" else value


def _coordinates(fields: list[str]) -> Coordinates | None:
    if not any(fields):
        return None
    return Coordinates(
        _coordinate(fields[0], fields[1], 2), _coordinate(fields[2], fields[3], 3)
    )


# GPSxyz/SPCxyz/SYMxyz destinations (aprs.org/symbols/symbolsX.txt): x names
# a subgroup of one table, y the symbol within it, and z an optional overlay.
# Each row: first symbol, primary x, alternate x, and the y characters.
_XY_ROWS = (
    ("!", "B", "O", "BCDEFGHIJKLMNOP"),
    ("0", "P", "A", "0123456789"),
    (":", "M", "N", "RSTUVWX"),
    ("A", "P", "A", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    ("[", "H", "D", "STUVWX"),
    ("a", "L", "S", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    ("{", "J", "Q", "1234"),
)
_XY_SYMBOL: dict[str, tuple[str, str]] = {}
_SYMBOL_XY: dict[tuple[str, str], str] = {}
for _first, _primary, _alternate, _ys in _XY_ROWS:
    for _i, _y in enumerate(_ys):
        for _x, _table in ((_primary, "/"), (_alternate, "\\")):
            _code = chr(ord(_first) + _i)
            _XY_SYMBOL[_x + _y] = (_table, _code)
            _SYMBOL_XY[(_table, _code)] = _x + _y


def header_symbol(header: Header | None) -> Symbol | None:
    if header is None or header.destination is None:
        return None
    dest = header.destination.split("-")[0]
    match = re.fullmatch(r"(?:GPS|SPC|SYM)([CE])(\d{2})", dest)
    if match and 1 <= int(match[2]) <= 94:
        return Symbol("/" if match[1] == "C" else "\\", chr(32 + int(match[2])))
    match = re.fullmatch(r"(?:GPS|SPC|SYM)([A-Z][0-9A-Z])([0-9A-Z]?)", dest)
    if match and match[1] in _XY_SYMBOL:
        table, code = _XY_SYMBOL[match[1]]
        return Symbol(match[2] or table, code)
    suffix = header.source.rpartition("-")[2]
    if dest in ("GPS", "APRS") and suffix.isdigit() and 1 <= int(suffix) <= 15:
        return Symbol("/", "aUfbYX's><OjRkv"[int(suffix) - 1])
    return None


def destination_for(symbol: Symbol) -> str:
    """The GPSxyz destination that carries symbol; an overlay uses the alternate table."""
    table = "/" if symbol.table_id == "/" else "\\"
    xy = _SYMBOL_XY.get((table, symbol.code))
    if xy is None:
        raise Unrepresentable("$.symbol", "no GPSxyz destination encodes this symbol")
    overlay = "" if symbol.table_id in ("/", "\\") else symbol.table_id
    return "GPS" + xy + overlay


def read(
    raw: bytes,
    header: Header | None,
    diagnostics: list,
    policy: EnvelopePolicy = _DEFAULT_POLICY,
) -> NMEA:
    match = re.match(rb"\$([A-Z]{2})([A-Z]{3}),(.*)", raw, re.DOTALL)
    if not match:
        raise FieldError("invalid NMEA sentence identifier")
    talker, kind = match[1].decode(), match[2].decode()
    data, star, trailer = match[3].partition(b"*")
    supplied = None
    valid = None
    comment = b""
    if star:
        if len(trailer) < 2 or not re.fullmatch(rb"[0-9a-fA-F]{2}", trailer[:2]):
            raise FieldError("invalid NMEA checksum field")
        supplied = trailer[:2].decode()
        comment = trailer[2:]
        actual = functools.reduce(operator.xor, raw[1 : raw.index(b"*")], 0)
        # A mismatch is reported by conformance, so it also blocks sending.
        valid = actual == int(supplied, 16)
    fields_raw = tuple(data.split(b","))
    f = [token(v, "$.sentence") for v in fields_raw]
    number = lambda i: float(f[i]) if f[i] else None
    s: n.NMEASentence
    try:
        if kind == "GGA":
            if len(f) < 14:
                raise FieldError("GGA requires fourteen fields")
            if f[9] != "M" or f[11] != "M":
                raise FieldError("GGA height units must be meters")
            s = n.GGA(
                read_time(f[0]),
                _coordinates(f[1:5]),
                _fix_quality(f[5]),
                satellites=int(f[6]) if f[6] else None,
                hdop=number(7),
                altitude_msl=Measurement(number(8), "meters") if f[8] else None,
                geoid_separation=Measurement(number(10), "meters") if f[10] else None,
                dgps_age_seconds=_plain(f[12], r"[0-9]+(?:\.[0-9]+)?", float),
                dgps_station=_plain(f[13], r"[0-9]{1,4}", int),
            )
            usable = s.fix_quality != "invalid"
        elif kind == "GLL":
            if len(f) < 6:
                raise FieldError("GLL requires six fields")
            s = n.GLL(_coordinates(f[:4]), read_time(f[4]), _fix_status(f[5]))
            usable = s.fix_status == "active"
        elif kind == "RMC":
            if len(f) < 11:
                raise FieldError("RMC requires eleven fields")
            s = n.RMC(
                read_time(f[0]),
                read_date(f[8]),
                _fix_status(f[1]),
                _coordinates(f[2:6]),
                speed_knots=number(6),
                course_deg=number(7),
                magnetic_variation_deg=_variation(number(9), f[10]),
            )
            usable = s.fix_status == "active"
        elif kind == "VTG":
            if len(f) < 8 or [f[i] for i in (1, 3, 5, 7)] != ["T", "M", "N", "K"]:
                raise FieldError("invalid VTG fields or units")
            s = n.VTG(
                course_true_deg=number(0),
                course_magnetic_deg=number(2),
                speed_knots=number(4),
                speed_kmh_reported=number(6),
            )
            usable = False
        elif kind == "WPL":
            if len(f) < 5:
                raise FieldError("WPL requires five fields")
            coords = _coordinates(f[:4])
            if coords is None:
                raise FieldError("WPL requires coordinates")
            s = n.WPL(coords, f[4])
            usable = True
        else:
            raise CodecNotImplementedError("unknown NMEA sentence " + kind)
    except CodecNotImplementedError:
        raise
    except (ValueError, IndexError) as exc:
        raise FieldError("invalid NMEA field") from exc
    # A void or invalid fix is legitimate NMEA; position_usable=False says so.
    return NMEA(
        s,
        n.NMEAMetadata(
            talker,
            checksum=supplied is not None,
            checksum_valid=valid,
            checksum_supplied=supplied,
            fields_raw=fields_raw,
        ),
        position_usable=usable and valid is not False,
        symbol=header_symbol(header),
        comment=free_text(comment, "$.comment", diagnostics, policy),
    )


def _coord_fields(c: Coordinates | None) -> list[str]:
    if c is None:
        return [""] * 4
    result = []
    for value, width, hemispheres in (
        (c.latitude_deg, 2, "NS"),
        (c.longitude_deg, 3, "EW"),
    ):
        # Seven decimal minutes preserve sub-millimeter precision without
        # borrowing lexical fields from the original sentence.
        total = round(abs(value) * 60, 7)
        degrees = int(total // 60)
        minutes = total - degrees * 60
        # NMEA writes ddmm.mm; parsers expect the point, so keep two decimals.
        whole, _, fraction = f"{degrees:0{width}d}{minutes:010.7f}".rstrip(
            "0"
        ).partition(".")
        result.extend(
            [
                f"{whole}.{fraction.ljust(2, '0')}",
                hemispheres[math.copysign(1, value) < 0],
            ]
        )
    return result


_STATUS_LETTERS = {"active": "A", "void": "V"}


def _fix_status(letter: str) -> n.FixStatus:
    for status, code in _STATUS_LETTERS.items():
        if letter == code:
            return cast(n.FixStatus, status)
    raise FieldError("NMEA fix status must be A or V")


def _fix_quality(field: str) -> n.GGAFixQuality:
    if not field.isdigit() or int(field) >= len(n.GGA_FIX_QUALITIES):
        raise FieldError("GGA fix quality must be 0..8")
    return n.GGA_FIX_QUALITIES[int(field)]


def _variation(value: float | None, direction: str) -> float | None:
    """Signed degrees, east positive; a value and its direction occur together."""
    if value is None and not direction:
        return None
    if value is None or direction not in ("E", "W"):
        raise FieldError("magnetic variation needs a value and an E or W direction")
    return -value if direction == "W" else value


def _variation_fields(value: float | None, num: Any) -> list[str]:
    if value is None:
        return ["", ""]
    return [num(abs(value)), "W" if math.copysign(1, value) < 0 else "E"]


def write(p: NMEA) -> bytes:
    s = p.sentence
    num = lambda v: "" if v is None else f"{v:.12g}"
    if isinstance(s, n.GGA):
        f = [
            write_time(s.time_utc),
            *_coord_fields(s.coordinates),
            str(n.GGA_FIX_QUALITIES.index(s.fix_quality)),
            num(s.satellites),
            num(s.hdop),
            height_field(s.altitude_msl),
            "M",
            height_field(s.geoid_separation),
            "M",
            "" if s.dgps_age_seconds is None else _decimal(s.dgps_age_seconds),
            "" if s.dgps_station is None else f"{s.dgps_station:04d}",
        ]
    elif isinstance(s, n.GLL):
        f = [
            *_coord_fields(s.coordinates),
            write_time(s.time_utc),
            _STATUS_LETTERS[s.fix_status],
        ]
    elif isinstance(s, n.RMC):
        f = [
            write_time(s.time_utc),
            _STATUS_LETTERS[s.fix_status],
            *_coord_fields(s.coordinates),
            num(s.speed_knots),
            num(s.course_deg),
            write_date(s.date),
            *_variation_fields(s.magnetic_variation_deg, num),
        ]
    elif isinstance(s, n.VTG):
        f = [
            num(s.course_true_deg),
            "T",
            num(s.course_magnetic_deg),
            "M",
            num(s.speed_knots),
            "N",
            num(s.speed_kmh_reported),
            "K",
        ]
    else:
        f = [*_coord_fields(s.coordinates), s.name]
    raw = (p.metadata.talker + type(s).__name__ + "," + ",".join(f)).encode()
    if p.metadata.checksum:
        raw += b"*" + f"{functools.reduce(operator.xor,raw,0):02X}".encode()
    return b"$" + raw + p.comment.encode()


def read_time(raw: str) -> n.UTCTime | None:
    if not raw:
        return None
    if not re.fullmatch(r"[0-9]{4}(?:[0-9]{2}(?:\.[0-9]+)?)?", raw):
        raise FieldError("invalid NMEA UTC time")
    return n.UTCTime(int(raw[:2]), int(raw[2:4]), float(raw[4:]) if raw[4:] else None)


def write_time(value: n.UTCTime | None) -> str:
    if value is None:
        return ""
    if value.second is None:
        raise FieldError(
            "NMEA time requires seconds; unknown seconds cannot be invented"
        )
    from decimal import Decimal

    whole, dot, fraction = format(Decimal(str(value.second)), "f").partition(".")
    seconds = f"{int(whole):02d}"
    if dot and fraction.rstrip("0"):
        seconds += "." + fraction.rstrip("0")
    return f"{value.hour:02d}{value.minute:02d}" + seconds


def read_date(raw: str) -> n.NMEADate | None:
    if not raw:
        return None
    if not re.fullmatch(r"[0-9]{4}(?:[0-9]{2})?", raw):
        raise FieldError("invalid NMEA calendar date")
    return n.NMEADate(int(raw[:2]), int(raw[2:4]), int(raw[4:]) if raw[4:] else None)


def write_date(value: n.NMEADate | None) -> str:
    if value is None:
        return ""
    if value.day is None or value.month is None or value.year_mod_100 is None:
        raise FieldError(
            "NMEA RMC needs day, month and two-digit year; partial date cannot be encoded"
        )
    return f"{value.day:02d}{value.month:02d}{value.year_mod_100:02d}"


def _plain(raw: str, pattern: str, kind: Any) -> Any:
    """An empty field, or one plain decimal number (no sign, spaces or exponent)."""
    if not raw:
        return None
    if not re.fullmatch(pattern, raw):
        raise FieldError("invalid NMEA field")
    return kind(raw)


def _decimal(value: float) -> str:
    """An ordinary decimal number; NMEA fields have no exponent form."""
    from decimal import Decimal

    return format(Decimal(f"{value:.12g}"), "f")


def height_field(value: Measurement | None) -> str:
    from ._units import height

    if value is None or value.value is None:
        return ""
    return _decimal(height(value, "meters"))
