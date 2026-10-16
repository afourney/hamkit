# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Uncompressed coordinates without position ambiguity (APRS101 pp. 23–24)."""

import math
import re
from decimal import ROUND_HALF_UP, Decimal

from ..errors import FieldError, UnsupportedFormat
from ..models import CoordinateAxis


def _parameters(axis: CoordinateAxis) -> tuple[int, int, bytes]:
    if axis == "latitude":
        return 2, 90, b"NS"
    if axis == "longitude":
        return 3, 180, b"EW"
    raise FieldError("unknown coordinate axis")


def decode_coordinate(raw: bytes, axis: CoordinateAxis) -> float:
    width, limit, hemispheres = _parameters(axis)
    if len(raw) != width + 6:
        raise FieldError("incorrect coordinate width")
    if b" " in raw:
        raise UnsupportedFormat("position ambiguity is not implemented")
    if not re.fullmatch(
        rb"[0-9]{" + str(width + 2).encode() + rb"}\.[0-9]{2}[" + hemispheres + rb"]",
        raw,
    ):
        raise FieldError("invalid coordinate syntax")
    degrees, minutes = int(raw[:width]), float(raw[width:-1])
    if minutes >= 60 or degrees > limit or (degrees == limit and minutes != 0):
        raise FieldError("coordinate out of range")
    value = degrees + minutes / 60
    return -value if raw[-1] == hemispheres[1] else value


def encode_coordinate(value: float, axis: CoordinateAxis) -> bytes:
    width, limit, hemispheres = _parameters(axis)
    if not math.isfinite(value) or abs(value) > limit:
        raise FieldError("coordinate must be finite and within axis bounds")
    # Round total hundredths of minutes, so carry into the next degree is valid.
    units = int(
        (Decimal(str(abs(value))) * 6000).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    )
    degrees, minutes = divmod(units, 6000)
    whole, fraction = divmod(minutes, 100)
    hemisphere = chr(hemispheres[1 if math.copysign(1, value) < 0 else 0])
    return f"{degrees:0{width}}{whole:02}.{fraction:02}{hemisphere}".encode("ascii")
