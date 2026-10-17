# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Mic-E joint destination/information codec (APRS101 chapter 10).

Status text follows the APRS 1.2 type codes (aprs.org/aprs12/mic-e-types.txt):
"T......Mv", where T is a type byte and a declared suffix may end the text.
APRS 1.2 redefines the ` and ' type bytes, which APRS101 used for hex
telemetry; that reading remains only for the complete legacy hex form.
"""

from __future__ import annotations

import math
import re
from dataclasses import replace
from typing import cast

from ._data import Altitude, Extensions, Measurement, Motion, Symbol, Telemetry
from ._errors import FieldError
from ._models import Header, MicE
from ._position_codec import base91, center, dao_offset, pack91
from ._text import free_text

# Declared version suffixes. The manufacturer/version pair after ` or ' does
# not depend on which of the two type bytes was sent.
_OTHER_SUFFIXES = (
    *("_ ", '_"', "_#", "_$", "_%", "_)", "_(", "_0", "_3", "_1"),  # Yaesu
    *(" X", "(5", "(8", "|3", "|4", ":4", ":8"),  # AP510, Anytone, Byonics, SCS
)
TYPE_SUFFIXES: dict[str, tuple[str, ...]] = {
    ">": ("=", "^"),  # TH-D72, TH-D74
    "]": ("=",),  # TM-D710
    "`": _OTHER_SUFFIXES,
    "'": _OTHER_SUFFIXES,
}
# The legacy grid/status prefix has no coordinate authority; it stays in the
# device code after a Kenwood type byte so composing does not discard it.
_GRID = r"[A-R]{2}[0-9]{2}[A-X]{2}/[A-Za-z]"

_MESSAGES = (
    "emergency",
    "priority",
    "special",
    "committed",
    "returning",
    "in_service",
    "en_route",
    "off_duty",
)


def destination(raw: str):
    raw = raw.split("-")[0]
    if not re.fullmatch(r"[0-9A-LP-Z]{3}[0-9LP-Z]{3}", raw):
        raise FieldError("invalid Mic-E destination")
    digits = "".join(
        (
            c
            if c.isdigit()
            else (
                str(ord(c) - 65)
                if "A" <= c <= "J"
                else str(ord(c) - 80)
                if "P" <= c <= "Y"
                else " "
            )
        )
        for c in raw
    )
    n = len(digits) - len(digits.rstrip())
    if n > 4 or " " in digits[: -n or None]:
        raise FieldError("invalid Mic-E latitude ambiguity")
    d = digits.replace(" ", "0")
    if int(d[2:4]) >= 60:
        raise FieldError("invalid Mic-E latitude minutes")
    lat = center(int(d[:2]) + int(d[2:]) / 6000, n)
    if raw[3] < "P":
        lat = -lat
    bits = sum(
        (1 << (2 - i))
        for i, c in enumerate(raw[:3])
        if "A" <= c <= "K" or "P" <= c <= "Z"
    )
    custom = any("A" <= c <= "K" for c in raw[:3])
    standard = any("P" <= c <= "Z" for c in raw[:3])
    message = (
        "unknown"
        if custom and standard
        else f"custom_{7-bits}"
        if custom and bits
        else _MESSAGES[bits]
    )
    return lat, n, message, raw[4] >= "P", raw[5] >= "P"


def read(information: bytes, header: Header, diagnostics: list) -> MicE:
    lat, n, message, offset, west = destination(header.destination)
    b = information[1:]
    if len(b) < 8 or any(not 28 <= c <= 127 for c in b[:6]):
        raise FieldError("truncated or invalid Mic-E information")
    degrees = b[0] - 28 + (100 if offset else 0)
    if 180 <= degrees <= 189:
        degrees -= 80
    elif 190 <= degrees <= 199:
        degrees -= 190
    minutes = b[1] - 28
    if minutes >= 60:
        minutes -= 60
    hundredths = b[2] - 28
    if minutes >= 60 or hundredths > 99:
        raise FieldError("invalid Mic-E longitude minutes")
    lon = center(degrees + (minutes + hundredths / 100) / 60, n)
    if west:
        lon = -lon
    speed = (b[3] - 28) * 10 + (b[4] - 28) // 10
    if speed >= 800:
        speed -= 800
    course = ((b[4] - 28) % 10) * 100 + b[5] - 28
    if course >= 400:
        course -= 400
    motion = Motion(course, speed, course_code=course, speed_code=speed)
    symbol = Symbol(chr(b[7]), chr(b[6]))
    device, extra, tail = read_status(b[8:], symbol)
    e = replace(extra, motion=motion)
    return MicE(
        dao_offset(lat, e.dao, "latitude"),
        dao_offset(lon, e.dao, "longitude"),
        symbol,
        message=message,
        fix="current" if information[:1] in (b"`", b"\x1c") else "old",
        ambiguity=n,
        device_code=device,
        extensions=e,
        comment=free_text(tail, "$.comment", diagnostics),
    )


def _longitude_degrees_byte(degrees: int, offset: bool) -> int:
    """APRS101 p.48 longitude-degrees table.

    100-109 degrees use 'l'-'u' (108-117). Bytes 28-37 decode to the same
    values arithmetically, but they are not the specified encoding and include
    the FS-US control characters.
    """
    if offset:
        if 0 <= degrees <= 9:
            return degrees + 118
        if 100 <= degrees <= 109:
            return degrees + 8
        if 110 <= degrees <= 179:
            return degrees - 100 + 28
    elif 10 <= degrees <= 99:
        return degrees + 28
    raise FieldError("Mic-E destination longitude offset does not match longitude")


def write(p: MicE, header: Header) -> bytes:
    p = replace(
        p,
        latitude_deg=dao_offset(p.latitude_deg, p.extensions.dao, "latitude", -1),
        longitude_deg=dao_offset(p.longitude_deg, p.extensions.dao, "longitude", -1),
    )
    lat, n, message, offset, west = destination(header.destination)
    if (
        abs(lat - center(p.latitude_deg, p.ambiguity)) > 1 / 12000
        or n != p.ambiguity
        or message != p.message
        or west != (math.copysign(1, p.longitude_deg) < 0)
    ):
        raise FieldError(
            "Mic-E destination does not match latitude, ambiguity, message, or longitude hemisphere"
        )
    units = round(abs(p.longitude_deg) * 6000)
    degrees, minutes = divmod(units, 6000)
    minutes, hundredths = divmod(minutes, 100)
    degree_byte = _longitude_degrees_byte(degrees, offset)
    m = p.extensions.motion
    if m is None or m.course_deg is None or m.speed_knots is None:
        raise FieldError("Mic-E requires course and speed")
    speed, course = round(m.speed_knots), round(m.course_deg)
    if not 0 <= speed <= 799 or not 0 <= course <= 360:
        raise FieldError("Mic-E motion outside wire range")
    body = (
        bytes(
            [
                degree_byte,
                minutes + (88 if minutes < 10 else 28),
                hundredths + 28,
                speed // 10 + 28,
                speed % 10 * 10 + course // 100 + 28,
                course % 100 + 28,
            ]
        )
        + p.symbol.code.encode()
        + p.symbol.table_id.encode()
    )
    return (b"`" if p.fix == "current" else b"'") + body + write_status(p)


def device_parts(code: str | None) -> tuple[str, str]:
    """Split a device code into what precedes and what ends the status text."""
    if not code:
        return "", ""
    head, rest = code[:1], code[1:]
    if head in (">", "]"):
        grid = re.match(_GRID, rest)
        if grid:
            head, rest = head + grid[0], rest[grid.end() :]
    if head[:1] not in TYPE_SUFFIXES or rest and rest not in TYPE_SUFFIXES[code[0]]:
        raise FieldError("unsupported Mic-E type code")
    return head, rest


def _suffix(device: str, text: bytes) -> bytes:
    for suffix in TYPE_SUFFIXES[device]:
        if text.endswith(suffix.encode()):
            return suffix.encode()
    return b""


def _legacy_hex(tail: bytes) -> int:
    """Width of complete APRS101 hex telemetry after ` or ', or 0."""
    width = 4 if tail[:1] == b"`" else 10
    complete = re.fullmatch(rb"[0-9A-Fa-f]{%d}" % width, tail[1 : width + 1])
    if complete and not _suffix(tail[:1].decode(), tail[width + 1 :]):
        return width
    return 0


def read_status(tail: bytes, symbol: Symbol) -> tuple[str | None, Extensions, bytes]:
    """Decode the status text after the symbol: device code, extensions, comment."""
    device = None
    suffix = b""
    telemetry = None
    altitude = None
    width = _legacy_hex(tail) if tail[:1] in (b"`", b"'") else 0
    if width:
        values: tuple[int | None, ...] = tuple(
            bytes.fromhex(tail[1 : width + 1].decode())
        )
        if width == 4:
            values = (values[0], None, values[1], None, None)
        telemetry = Telemetry(values, encoding="mic_e_hex")
        tail = tail[width + 1 :]
    elif tail[:1] == b"\x1d":
        if len(tail) < 6:
            raise FieldError("truncated Mic-E binary telemetry")
        telemetry = Telemetry(tuple(tail[1:6]), encoding="mic_e_binary")
        tail = tail[6:]
    elif tail[:1] in (b">", b"]", b"`", b"'"):
        device = tail[:1].decode()
        suffix = _suffix(device, tail[1:])
        tail = tail[1 : len(tail) - len(suffix)]
    if len(tail) >= 4 and tail[3:4] == b"}":
        altitude = Altitude(Measurement(base91(tail[:3]) - 10000, "meters"), "mic_e")
        tail = tail[4:]
    grid = re.match(_GRID.encode(), tail)
    if grid and device in (">", "]"):
        device += grid[0].decode()
        tail = tail[grid.end() :]
    if device is not None:
        device += suffix.decode()
    from . import _extensions

    extra, tail = _extensions.read(tail, symbol)
    e = replace(
        extra,
        altitude=altitude or extra.altitude,
        telemetry=telemetry or extra.telemetry,
    )
    return device, e, tail


def write_status(p: MicE) -> bytes:
    """Encode the status text after the symbol; the inverse of read_status."""
    head, suffix = device_parts(p.device_code)
    e = replace(p.extensions, motion=None)
    first = b""
    if e.telemetry and e.telemetry.encoding in ("mic_e_hex", "mic_e_binary"):
        if head:
            raise FieldError("Mic-E telemetry and a type code share the first byte")
        t = e.telemetry
        values = t.analog
        if len(values) == 2 and t.encoding == "mic_e_hex":
            values = (values[0], None, values[1], None, None)
        if len(values) != 5 or t.digital:
            raise FieldError("invalid Mic-E telemetry channels")
        if t.encoding == "mic_e_binary":
            first = b"\x1d" + bytes(int(cast(float, v)) for v in values)
        elif values[1] is None and values[3:] == (None, None):
            first = (
                b"`"
                + bytes([int(cast(float, values[0])), int(cast(float, values[2]))])
                .hex()
                .upper()
                .encode()
            )
        else:
            first = (
                b"'" + bytes(int(cast(float, v)) for v in values).hex().upper().encode()
            )
        e = replace(e, telemetry=None)
    else:
        first = head[:1].encode()
    if e.altitude and e.altitude.encoding == "mic_e":
        if e.altitude.reference != "unspecified":
            raise FieldError(
                "Mic-E altitude reference is not an independent wire field"
            )
        a = e.altitude.measurement
        if a.unit != "meters" or a.value is None:
            raise FieldError("Mic-E altitude requires meters")
        first += pack91(round(a.value) + 10000, 3) + b"}"
        e = replace(e, altitude=None)
    from . import _extensions

    comment = p.comment.encode()
    return (
        first
        + head[1:].encode()
        + _extensions.write(e, p.symbol, comment)
        + comment
        + suffix.encode()
    )
