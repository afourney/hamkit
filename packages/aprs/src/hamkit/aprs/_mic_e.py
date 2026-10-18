# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Mic-E joint destination/information codec (APRS101 chapter 10).

Status text follows the APRS 1.2 type conventions
(aprs.org/aprs12/mic-e-types.txt) under two policy switches:

- mice_device_ids reads an apostrophe/backtick type byte where APRS101 hex
  telemetry is not present, and breaks declared version suffixes out of the
  comment for every type byte. APRS 1.1 accepted neither as a field.
- mice_hex_as_device also reads complete hex telemetry as device text, which
  changes the meaning of a field APRS 1.1 accepted.

Without either, the selectors keep their APRS101 hex-telemetry meaning.
"""

from __future__ import annotations

import math
import re
from dataclasses import replace
from typing import cast

from ._ambiguity import center, center_wire
from ._data import Altitude, Extensions, Measurement, Motion, Symbol, Telemetry
from ._errors import FieldError, Unrepresentable
from ._models import Header, MicE
from ._policy import _DEFAULT_POLICY, EnvelopePolicy
from ._position_codec import base91, dao_offset, pack91
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
    lat = center_wire(int(d[:2]) + int(d[2:]) / 6000, n)
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


def read(
    information: bytes,
    header: Header,
    diagnostics: list,
    policy: EnvelopePolicy = _DEFAULT_POLICY,
) -> MicE:
    if header.destination is None:
        raise FieldError("Mic-E decoding requires an explicit destination")
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
    lon = center_wire(degrees + (minutes + hundredths / 100) / 60, n)
    if west:
        lon = -lon
    speed = (b[3] - 28) * 10 + (b[4] - 28) // 10
    if speed >= 800:
        speed -= 800
    course = ((b[4] - 28) % 10) * 100 + b[5] - 28
    if course >= 400:
        course -= 400
    # Course 0 means unknown (APRS101 p49); north is 360.
    motion = Motion(
        None if course == 0 else course, speed, course_code=course, speed_code=speed
    )
    symbol = Symbol(chr(b[7]), chr(b[6]))
    device, extra, tail = read_status(b[8:], symbol, policy, receiving=True)
    e = replace(extra, motion=motion)
    return MicE(
        dao_offset(lat, e.dao, "latitude") if not n else lat,
        dao_offset(lon, e.dao, "longitude") if not n else lon,
        symbol,
        message=message,
        fix="current" if information[:1] in (b"`", b"\x1c") else "old",
        ambiguity=n,
        device_code=device,
        extensions=e,
        comment=free_text(tail, "$.comment", diagnostics, policy),
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


def _base_coordinates(p: MicE) -> tuple[float, float]:
    from ._dao import base_coordinates

    latitude, longitude = base_coordinates(p)
    if (
        abs(center(latitude, p.ambiguity)) > 90
        or abs(center(longitude, p.ambiguity)) >= 180
    ):
        raise FieldError("Mic-E coordinate/ambiguity cell is outside the wire range")
    return latitude, longitude


def destination_for(p: MicE) -> str:
    """Pack APRS101 pp44–46 latitude, message and longitude flags, without an SSID.

    Omission requests automatic encoding; an explicit address remains a caller
    assertion. Unknown mixed message bits have no unique semantic encoding.
    """
    latitude, longitude = _base_coordinates(p)
    latitude = center(latitude, p.ambiguity)
    longitude = center(longitude, p.ambiguity)
    units = round(abs(latitude) * 6000)
    degrees, minutes = divmod(units, 6000)
    digits = f"{degrees:02d}{minutes:04d}"
    if p.message == "unknown":
        raise FieldError(
            "unknown Mic-E message requires an explicit destination or a known message"
        )
    custom = p.message.startswith("custom_")
    bits = 7 - int(p.message[-1]) if custom else _MESSAGES.index(p.message)
    longitude_degrees = round(abs(longitude) * 6000) // 6000
    if longitude_degrees >= 180:
        raise FieldError("Mic-E rounded longitude is outside the wire range")
    flags = (
        math.copysign(1, latitude) > 0,
        longitude_degrees < 10 or longitude_degrees >= 100,
        math.copysign(1, longitude) < 0,
    )
    result = []
    for index, digit in enumerate(digits):
        high = bool(bits & (1 << (2 - index))) if index < 3 else flags[index - 3]
        is_custom = index < 3 and custom and high
        if index >= 6 - p.ambiguity:
            result.append("K" if is_custom else "Z" if high else "L")
        else:
            result.append(chr((65 if is_custom else 80 if high else 48) + int(digit)))
    return "".join(result)


def resolve_header(header: Header, p: MicE) -> Header:
    """Return a generated header without mutating the packet or its template."""
    return (
        replace(header, destination=destination_for(p))
        if header.destination is None
        else header
    )


def position_bytes(p: MicE, header: Header | None) -> bytes:
    """Check the joint header/position fields and encode the longitude bytes."""
    address = (
        destination_for(p)
        if header is None or header.destination is None
        else header.destination
    )
    latitude, longitude = _base_coordinates(p)
    p = replace(p, latitude_deg=latitude, longitude_deg=longitude)
    lat, n, message, offset, west = destination(address)
    if (
        abs(lat - center(p.latitude_deg, p.ambiguity)) > 1 / 12000
        or (math.copysign(1, lat) != math.copysign(1, p.latitude_deg))
        or n != p.ambiguity
        or message != p.message
        or west != (math.copysign(1, p.longitude_deg) < 0)
    ):
        raise FieldError(
            "Mic-E destination does not match latitude, ambiguity, message, or"
            " longitude hemisphere; leave header.destination out (None) to have"
            " it generated from the payload"
        )
    units = round(abs(center(p.longitude_deg, p.ambiguity)) * 6000)
    degrees, minutes = divmod(units, 6000)
    minutes, hundredths = divmod(minutes, 100)
    degree_byte = _longitude_degrees_byte(degrees, offset)
    return bytes([degree_byte, minutes + (88 if minutes < 10 else 28), hundredths + 28])


def write(
    p: MicE, header: Header | None, policy: EnvelopePolicy = _DEFAULT_POLICY
) -> bytes:
    position = position_bytes(p, header)
    m = p.extensions.motion
    if m is None or m.speed_knots is None:
        raise Unrepresentable(
            "$.extensions.motion.speed_knots", "Mic-E always carries a speed"
        )
    speed = round(m.speed_knots)
    # As in the uncompressed form: 0 is unknown, so north is sent as 360.
    course = 0 if m.course_deg is None else round(m.course_deg) or 360
    if not 0 <= speed <= 799:
        raise Unrepresentable(
            "$.extensions.motion.speed_knots", "Mic-E carries 0..799 knots"
        )
    if not 0 <= course <= 360:
        raise Unrepresentable(
            "$.extensions.motion.course_deg", "Mic-E carries 0..360 degrees"
        )
    body = (
        position
        + bytes(
            [
                speed // 10 + 28,
                speed % 10 * 10 + course // 100 + 28,
                course % 100 + 28,
            ]
        )
        + p.symbol.code.encode()
        + p.symbol.table_id.encode()
    )
    return (b"`" if p.fix == "current" else b"'") + body + write_status(p, policy)


def device_parts(
    code: str | None, policy: EnvelopePolicy = _DEFAULT_POLICY
) -> tuple[str, str]:
    """Split a device code into what precedes and what ends the status text."""
    if not code:
        return "", ""
    if not _device_ids(policy) and code not in (">", "]"):
        raise FieldError("Mic-E device code requires mice_device_ids")
    head, rest = code[:1], code[1:]
    if head[:1] not in TYPE_SUFFIXES or rest and rest not in TYPE_SUFFIXES[code[0]]:
        raise FieldError("unsupported Mic-E type code")
    return head, rest


def _device_ids(policy: EnvelopePolicy) -> bool:
    return bool({"mice_device_ids", "mice_hex_as_device"} & set(policy.extensions))


def _suffix(device: str, text: bytes) -> bytes:
    for suffix in TYPE_SUFFIXES[device]:
        if text.endswith(suffix.encode()):
            return suffix.encode()
    return b""


def _legacy_hex(tail: bytes) -> int:
    """Width of complete APRS101 hex telemetry after ` or ', or 0."""
    width = 4 if tail[:1] == b"`" else 10
    complete = re.fullmatch(rb"[0-9A-Fa-f]{%d}" % width, tail[1 : width + 1])
    if complete:
        return width
    return 0


def read_status(
    tail: bytes,
    symbol: Symbol,
    policy: EnvelopePolicy = _DEFAULT_POLICY,
    *,
    receiving: bool = False,
) -> tuple[str | None, Extensions, bytes]:
    """Decode the status text after the symbol: device code, extensions, comment.

    Broken APRS 1.1 hex telemetry raises at $.comment. When receiving, the
    position is kept and the status stays comment text; the send-side
    read-back of that comment then reports the problem once.
    """
    device = None
    suffix = b""
    telemetry = None
    altitude = None
    modern = _device_ids(policy)
    selector = tail[:1] in (b"`", b"'")
    hex_as_device = "mice_hex_as_device" in policy.extensions
    width = _legacy_hex(tail) if selector and not hex_as_device else 0
    if selector and not width and not modern:
        if not receiving:
            raise Unrepresentable(
                "$.comment", "truncated or invalid legacy Mic-E hexadecimal telemetry"
            )
        # Only the status field is broken: keep its bytes as the comment.
        return None, Extensions(), tail
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
        suffix = _suffix(device, tail[1:]) if modern else b""
        tail = tail[1 : len(tail) - len(suffix)]
    if len(tail) >= 4 and tail[3:4] == b"}":
        altitude = Altitude(
            Measurement(base91(tail[:3]) - 10000, "meters"), encoding="mic_e"
        )
        tail = tail[4:]
    # A legacy grid/status prefix remains literal comment text. It is neither
    # a device identifier nor a replacement for the encoded Mic-E coordinates.
    if device is not None:
        device += suffix.decode()
    from . import _extensions

    extra, tail = _extensions.read(tail, symbol, policy)
    e = replace(
        extra,
        altitude=altitude or extra.altitude,
        telemetry=telemetry or extra.telemetry,
    )
    return device, e, tail


def write_status(p: MicE, policy: EnvelopePolicy = _DEFAULT_POLICY) -> bytes:
    """Encode the status text after the symbol; the inverse of read_status."""
    _base_coordinates(p)
    head, suffix = device_parts(p.device_code, policy)
    e = replace(
        p.extensions, motion=p.extensions.motion if p.extensions.bearing else None
    )
    first = b""
    if e.telemetry and e.telemetry.encoding in ("mic_e_hex", "mic_e_binary"):
        if head:
            raise FieldError("Mic-E telemetry and a type code share the first byte")
        t = e.telemetry
        if t.encoding == "mic_e_hex" and "mice_hex_as_device" in policy.extensions:
            raise FieldError("hexadecimal telemetry conflicts with mice_hex_as_device")
        values = t.analog
        if len(values) == 2 and t.encoding == "mic_e_hex":
            values = (values[0], None, values[1], None, None)
        if len(values) != 5 or t.digital:
            raise FieldError("invalid Mic-E telemetry channels")
        two_channel = (
            t.encoding == "mic_e_hex"
            and values[1] is None
            and values[3:] == (None, None)
        )
        present = (values[0], values[2]) if two_channel else values
        if any(v is None or v != int(v) or not 0 <= v <= 255 for v in present):
            raise FieldError("Mic-E telemetry channels require integers in 0..255")
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
            raise Unrepresentable(
                "$.extensions.altitude.reference",
                "the Mic-E altitude has no reference field",
            )
        from ._units import height

        first += (
            pack91(round(height(e.altitude.measurement, "meters")) + 10000, 3) + b"}"
        )
        e = replace(e, altitude=None)
    from . import _extensions

    comment = p.comment.encode()
    return (
        first
        + _extensions.write(
            e, p.symbol, comment, policy, coordinates=(p.latitude_deg, p.longitude_deg)
        )
        + comment
        + suffix.encode()
    )
