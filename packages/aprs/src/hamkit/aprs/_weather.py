# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Weather token grammar; absent and unavailable observations remain distinct."""

from __future__ import annotations

import re
from typing import Any

from ._data import Measurement, WaterHeight, Weather
from ._errors import FieldError
from ._fields import decode_timestamp, encode_timestamp
from ._text import free_text

_FIELDS: dict[str, tuple[str, Any, int, float]] = {
    "c": ("wind_direction", "degrees", 3, 1),
    "s": ("wind_speed", "mph", 3, 1),
    "g": ("gust", "mph", 3, 1),
    "t": ("temperature", "fahrenheit", 3, 1),
    "r": ("rain_1h", "inches", 3, 0.01),
    "p": ("rain_24h", "inches", 3, 0.01),
    "P": ("rain_since_midnight", "inches", 3, 0.01),
    "h": ("humidity", "percent", 2, 1),
    "b": ("pressure", "hPa", 5, 0.1),
    "L": ("luminosity", "W/m2", 3, 1),
    "l": ("luminosity", "W/m2", 3, 1),
    "#": ("rain_counter", "count", 3, 1),
}


def read(
    raw: bytes, *, positioned=False, compressed=False, diagnostics=None
) -> tuple[Weather, bytes]:
    original = raw
    values: dict[str, Any] = {}
    timestamp = None
    if not positioned:
        if len(raw) < 8:
            raise FieldError("truncated weather timestamp")
        timestamp = decode_timestamp(raw[:8])
        raw = raw[8:]
    elif not compressed:
        match = re.match(rb"([0-9. ]{3})/([0-9. ]{3})", raw)
        if match:
            c, s = match[1], match[2]
            unavailable = c == s == b"000"
            values["wind_direction"] = Measurement(
                int(c) if c.isdigit() and not unavailable else None, "degrees", raw=c
            )
            values["wind_speed"] = Measurement(
                int(s) if s.isdigit() and not unavailable else None,
                "disputed_knots_or_mph",
                raw=s,
            )
            raw = raw[7:]
    while raw:
        tag = chr(raw[0])
        if tag in "Ff":
            match = re.match(rb"[Ff](-?\d+(?:\.\d+)?)", raw)
            if match:
                values["water_height"] = WaterHeight(
                    Measurement(float(match[1]), "feet" if tag == "F" else "meters")
                )
                raw = raw[match.end() :]
                continue
        if tag not in _FIELDS:
            break
        name, unit, width, scale = _FIELDS[tag]
        if tag == "s" and (positioned or "wind_speed" in values):
            name, unit = "snow_24h", "inches"
        field = raw[1 : width + 1]
        if len(field) != width or not (
            field in (b"." * width, b" " * width)
            or re.fullmatch(rb"-?\d+(?:\.\d+)?", field)
        ):
            if diagnostics is not None:
                from ._models import Diagnostic

                diagnostics.append(
                    Diagnostic(
                        "nonconforming",
                        "invalid weather field width or value",
                        "$.comment",
                    )
                )
            break
        value = None if field in (b"." * width, b" " * width) else float(field) * scale
        if value is not None:
            if tag == "h" and value == 0:
                value = 100
            if tag == "l":
                value += 1000
        values[name] = Measurement(value, unit, raw=field)
        raw = raw[width + 1 :]
    # APRS software + two/three-character weather device code is a suffix.
    if re.fullmatch(rb"[A-Za-z][A-Za-z0-9]{2,4}", raw):
        values["software_code"] = chr(raw[0])
        values["device_code"] = raw[1:].decode()
        raw = b""
    if not positioned:
        values["comment"] = free_text(
            raw, "$.comment", diagnostics if diagnostics is not None else []
        )
        raw = b""
    return Weather(**values, timestamp=timestamp, raw=original), raw


def _value(m: Measurement, unit: str) -> float | None:
    v = m.value
    if v is None or m.unit == unit:
        return v
    if unit == "fahrenheit" and m.unit == "celsius":
        return v * 1.8 + 32
    if unit == "inches" and m.unit == "mm":
        return v / 25.4
    if unit == "knots":
        if m.unit == "m/s":
            return v * 3600 / 1852
        if m.unit == "mph":
            return v * 1.609344 / 1.852
        if m.unit == "km/h":
            return v / 1.852
    if unit == "mph":
        if m.unit == "m/s":
            return v / 0.44704
        if m.unit == "knots":
            return v * 1.852 / 1.609344
        if m.unit == "km/h":
            return v / 1.609344
    raise FieldError("weather measurement unit cannot be encoded in this field")


def _number(value: float | None, width: int, scale: float = 1) -> bytes:
    if value is None:
        return b"." * width
    number = round(value / scale)
    raw = f"{number:0{width}d}".encode()
    if len(raw) != width:
        raise FieldError("weather value exceeds field width")
    return raw


def write(w: Weather, *, positioned=False, compressed=False) -> bytes:
    raw = b""
    if not positioned:
        if w.timestamp is None:
            raise FieldError("positionless weather requires timestamp")
        raw = b"_" + encode_timestamp(w.timestamp)
    if positioned and not compressed:
        if w.wind_direction is None or w.wind_speed is None:
            raise FieldError("positioned weather requires wind fields")
        speed = w.wind_speed
        value = (
            speed.value
            if speed.unit == "disputed_knots_or_mph"
            else _value(speed, "mph")
        )
        raw += _number(w.wind_direction.value, 3) + b"/" + _number(value, 3)
    for tag, (name, unit, width, scale) in _FIELDS.items():
        if tag == "l" or positioned and tag in "cs":
            continue
        reading = getattr(w, name)
        if reading is None:
            continue
        v = _value(reading, unit)
        if tag == "h" and v == 100:
            v = 0
        if tag == "L" and v is not None and v >= 1000:
            tag = "l"
            v -= 1000
        raw += tag.encode() + _number(v, width, scale)
    if w.snow_24h:
        v = _value(w.snow_24h, "inches")
        if v is not None and v != int(v):
            field = f"{v:.1f}".encode()
            if len(field) != 3:
                raise FieldError("snow value exceeds field width")
        else:
            field = _number(v, 3)
        raw += b"s" + field
    if w.water_height:
        if w.water_height.reference_datum is not None:
            raise FieldError("water-height datum has no wire field")
        m = w.water_height.measurement
        if m.value is None:
            raise FieldError("water height requires a value")
        raw += (b"F" if m.unit == "feet" else b"f") + f"{m.value:g}".encode()
    raw += (
        (w.software_code or "").encode()
        + (w.device_code or "").encode()
        + w.comment.encode()
    )
    return raw


def vendor(raw: bytes) -> Weather | None:
    """Decode the documented Ultimeter 2000 numeric fields; keep raw separately."""
    if not raw.startswith((b"$ULTW", b"!!")):
        return None
    logging = raw.startswith(b"!!")
    data = raw[2:] if logging else raw[5:]
    values: list[int | None] = []
    for i in range(0, len(data) - 3, 4):
        token = data[i : i + 4]
        if token == b"----":
            values.append(None)
            continue
        if not re.fullmatch(rb"[0-9A-Fa-f]{4}", token):
            break
        value = int(token, 16)
        values.append(value - 65536 if value >= 32768 else value)
    if not values:
        return None

    def get(i):
        return values[i] if i < len(values) else None

    found = {}

    def add(name, index, unit, convert):
        value = get(index)
        if value is not None:
            found[name] = Measurement(convert(value), unit)

    add("wind_speed" if logging else "gust", 0, "m/s", lambda x: round(x / 36, 1))
    add("wind_direction", 1, "degrees", lambda x: round((x & 255) * 1.41176))
    add("temperature", 2, "celsius", lambda x: round((x / 10 - 32) / 1.8, 1))
    add("rain_since_midnight", 3, "mm", lambda x: round(x * 0.254, 1))
    if get(4) is not None and get(4) >= 10:
        add("pressure", 4, "hPa", lambda x: x / 10)
    humidity = 6 if logging else 8
    if get(humidity) is not None and 1 <= get(humidity) // 10 <= 100:
        add("humidity", humidity, "percent", lambda x: x // 10)
    add(
        "rain_since_midnight",
        10 if logging else 11,
        "mm",
        lambda x: round(x * 0.254, 1),
    )
    add("wind_speed", 11 if logging else 12, "m/s", lambda x: round(x / 36, 1))
    return Weather(**found, raw=raw)
