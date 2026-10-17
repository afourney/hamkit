# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Mic-E joint destination/information codec (APRS101 chapter 10)."""

from __future__ import annotations

import math
import re
from dataclasses import replace
from typing import cast

from ._data import Altitude, Measurement, Motion, Symbol, Telemetry
from ._errors import FieldError
from ._models import Header, MicE
from ._position_codec import base91, center, dao_offset, pack91
from ._text import free_text

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
    tail = b[8:]
    device = None
    altitude = None
    telemetry = None
    if tail[:1] in (b"]", b">"):
        device = tail[:1].decode()
        tail = tail[1:]
    if len(tail) >= 4 and tail[3:4] == b"}":
        altitude = Altitude(Measurement(base91(tail[:3]) - 10000, "meters"), "mic_e")
        tail = tail[4:]
    if tail[:1] in (b"`", b"'"):
        width = 4 if tail[:1] == b"`" else 10
        if len(tail) < width + 1 or not re.fullmatch(
            rb"[0-9A-Fa-f]+", tail[1 : width + 1]
        ):
            raise FieldError("invalid Mic-E hex telemetry")
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
    # The legacy grid/status prefix has no coordinate authority; retain its
    # bytes in the device code so composing does not discard that information.
    grid = re.match(rb"[A-R]{2}[0-9]{2}[A-X]{2}/[A-Za-z]", tail)
    if grid and device:
        device += grid[0].decode()
        tail = tail[grid.end() :]
    from . import _extensions

    extra, tail = _extensions.read(tail, symbol)
    e = replace(
        extra,
        motion=motion,
        altitude=altitude or extra.altitude,
        telemetry=telemetry or extra.telemetry,
    )
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
    # Find a legal wire longitude byte for the caller-supplied destination bit.
    candidates = []
    for byte in range(28, 128):
        value = byte - 28 + (100 if offset else 0)
        if 180 <= value <= 189:
            value -= 80
        elif 190 <= value <= 199:
            value -= 190
        if value == degrees:
            candidates.append(byte)
    if not candidates:
        raise FieldError("Mic-E destination longitude offset does not match longitude")
    m = p.extensions.motion
    if m is None or m.course_deg is None or m.speed_knots is None:
        raise FieldError("Mic-E requires course and speed")
    speed, course = round(m.speed_knots), round(m.course_deg)
    if not 0 <= speed <= 799 or not 0 <= course <= 360:
        raise FieldError("Mic-E motion outside wire range")
    body = (
        bytes(
            [
                candidates[0],
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
    if p.device_code:
        if not re.fullmatch(
            r"[>\]](?:[A-R]{2}[0-9]{2}[A-X]{2}/[A-Za-z])?", p.device_code
        ):
            raise FieldError("unsupported Mic-E device marker")
        body += p.device_code.encode()
    e = replace(p.extensions, motion=None)
    if e.altitude and e.altitude.encoding == "mic_e":
        if e.altitude.reference != "unspecified":
            raise FieldError(
                "Mic-E altitude reference is not an independent wire field"
            )
        a = e.altitude.measurement
        if a.unit != "meters" or a.value is None:
            raise FieldError("Mic-E altitude requires meters")
        body += pack91(round(a.value) + 10000, 3) + b"}"
        e = replace(e, altitude=None)
    if e.telemetry and e.telemetry.encoding in ("mic_e_hex", "mic_e_binary"):
        t = e.telemetry
        values = t.analog
        if len(values) == 2 and t.encoding == "mic_e_hex":
            values = (values[0], None, values[1], None, None)
        if len(values) != 5 or t.digital:
            raise FieldError("invalid Mic-E telemetry channels")
        if t.encoding == "mic_e_binary":
            body += b"\x1d" + bytes(int(cast(float, v)) for v in values)
        elif values[1] is None and values[3:] == (None, None):
            body += (
                b"`"
                + bytes([int(cast(float, values[0])), int(cast(float, values[2]))])
                .hex()
                .upper()
                .encode()
            )
        else:
            body += (
                b"'" + bytes(int(cast(float, v)) for v in values).hex().upper().encode()
            )
        e = replace(e, telemetry=None)
    from . import _extensions

    return (
        (b"`" if p.fix == "current" else b"'")
        + body
        + _extensions.write(e, p.symbol, p.comment.encode())
        + p.comment.encode()
    )
