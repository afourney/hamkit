# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""NMEA sentence codecs. Checksums and fix validity do not imply each other."""

from __future__ import annotations

import functools
import math
import operator
import re
from typing import Literal, cast

from . import _nmea as n
from ._data import Coordinates, Symbol
from ._errors import CodecNotImplementedError, FieldError
from ._models import NMEA, Diagnostic, Header
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


def header_symbol(header: Header | None) -> Symbol | None:
    if header is None:
        return None
    dest = header.destination.split("-")[0]
    match = re.fullmatch(r"(?:GPS|SPC|SYM)([CE])(\d{2})", dest)
    if match and 1 <= int(match[2]) <= 94:
        return Symbol("/" if match[1] == "C" else "\\", chr(32 + int(match[2])))
    # APRS symbol XY codes: B/P are punctuation; M/N are vehicles and
    # the remaining primary/alternate groups follow the APRS symbol table.
    match = re.fullmatch(r"(?:GPS|SPC|SYM)([BPMNOAHS DQJL])([A-Z])([0-9A-Z]?)", dest)
    if match:
        group, letter, overlay = match.groups()
        groups = {
            "B": (32, "/"),
            "P": (32, "\\"),
            "M": (41, "/"),
            "N": (41, "\\"),
            "O": (64, "/"),
            "A": (64, "\\"),
            "H": (96, "/"),
            "D": (96, "\\"),
        }
        if group in groups:
            offset, table = groups[group]
            code = chr(offset + ord(letter) - 65)
            if 33 <= ord(code) <= 126:
                return Symbol(overlay or table, code)
    suffix = header.source.rpartition("-")[2]
    if dest in ("GPS", "APRS") and suffix.isdigit() and 1 <= int(suffix) <= 15:
        return Symbol("/", "aUfbYX's><OjRkv"[int(suffix) - 1])
    return None


def read(raw: bytes, header: Header | None, diagnostics: list) -> NMEA:
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
                f[0],
                _coordinates(f[1:5]),
                int(f[5]),
                satellites=int(f[6]) if f[6] else None,
                hdop=number(7),
                altitude_msl_m=number(8),
                geoid_separation_m=number(10),
                dgps_age=f[12] or None,
                dgps_station=f[13] or None,
            )
            usable = s.fix_quality > 0
        elif kind == "GLL":
            if len(f) < 6:
                raise FieldError("GLL requires six fields")
            s = n.GLL(_coordinates(f[:4]), f[4], cast(Literal["A", "V"], f[5]))
            usable = s.fix_status == "A"
        elif kind == "RMC":
            if len(f) < 11:
                raise FieldError("RMC requires eleven fields")
            s = n.RMC(
                f[0],
                f[8],
                cast(Literal["A", "V"], f[1]),
                _coordinates(f[2:6]),
                speed_knots=number(6),
                course_deg=number(7),
                magnetic_variation=number(9),
                magnetic_variation_direction=cast(
                    Literal["E", "W"] | None, f[10] or None
                ),
            )
            usable = s.fix_status == "A"
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
    if not usable and kind in ("GGA", "GLL", "RMC"):
        diagnostics.append(
            Diagnostic(
                "nonconforming", "NMEA reports no valid fix", "$.position_usable"
            )
        )
    return NMEA(
        s,
        n.NMEAMetadata(
            talker,
            checksum_supplied=supplied,
            checksum_valid=valid,
            fields_raw=fields_raw,
        ),
        position_usable=usable and valid is not False,
        symbol=header_symbol(header),
        comment=free_text(comment, "$.comment", diagnostics),
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
        result.extend(
            [
                f"{degrees:0{width}d}{minutes:010.7f}".rstrip("0").rstrip("."),
                hemispheres[math.copysign(1, value) < 0],
            ]
        )
    return result


def write(p: NMEA) -> bytes:
    s = p.sentence
    num = lambda v: "" if v is None else f"{v:.12g}"
    if isinstance(s, n.GGA):
        f = [
            s.time_utc,
            *_coord_fields(s.coordinates),
            str(s.fix_quality),
            num(s.satellites),
            num(s.hdop),
            num(s.altitude_msl_m),
            "M",
            num(s.geoid_separation_m),
            "M",
            s.dgps_age or "",
            s.dgps_station or "",
        ]
    elif isinstance(s, n.GLL):
        f = [*_coord_fields(s.coordinates), s.time_utc, s.fix_status]
    elif isinstance(s, n.RMC):
        f = [
            s.time_utc,
            s.fix_status,
            *_coord_fields(s.coordinates),
            num(s.speed_knots),
            num(s.course_deg),
            s.date_ddmmyy,
            num(s.magnetic_variation),
            s.magnetic_variation_direction or "",
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
    if p.metadata.checksum_supplied is not None:
        raw += b"*" + f"{functools.reduce(operator.xor,raw,0):02X}".encode()
    return b"$" + raw + p.comment.encode()
