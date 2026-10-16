# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Seven-byte APRS DHM and HMS timestamps (APRS101 pp. 22–23)."""

from ..errors import FieldError
from ..models import Timestamp


def encode_timestamp(value: Timestamp) -> bytes:
    if not all(type(n) is int for n in (value.hour, value.minute)):
        raise FieldError("timestamp components must be integers")
    if not (0 <= value.hour <= 23 and 0 <= value.minute <= 59):
        raise FieldError("hour/minute out of range")
    if value.kind == "hms_utc":
        if (
            value.day is not None
            or type(value.second) is not int
            or not 0 <= value.second <= 59
        ):
            raise FieldError("HMS requires second 0..59 and no day")
        return f"{value.hour:02}{value.minute:02}{value.second:02}h".encode("ascii")
    if value.kind not in ("dhm_utc", "dhm_local"):
        raise FieldError("unknown timestamp kind")
    if (
        value.second is not None
        or type(value.day) is not int
        or not 1 <= value.day <= 31
    ):
        raise FieldError("DHM requires day 1..31 and no second")
    suffix = "z" if value.kind == "dhm_utc" else "/"
    return f"{value.day:02}{value.hour:02}{value.minute:02}{suffix}".encode("ascii")


def decode_timestamp(raw: bytes) -> Timestamp:
    if len(raw) != 7 or not raw[:6].isdigit():
        raise FieldError("timestamp must contain six digits and a suffix")
    a, b, c = int(raw[:2]), int(raw[2:4]), int(raw[4:6])
    if raw[6:] == b"h":
        value = Timestamp("hms_utc", a, b, second=c)
    elif raw[6:] in (b"z", b"/"):
        value = Timestamp("dhm_utc" if raw[6:] == b"z" else "dhm_local", b, c, day=a)
    else:
        raise FieldError("unknown timestamp suffix")
    encode_timestamp(value)
    return value
