# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Weather token grammar; absent and unavailable observations remain distinct.

Beyond APRS101 and the APRS 1.1 clarification (spec-wx.txt), the APRS 1.2
weather proposal (aprs.org/aprs12/weather-new.txt) adds Xnnn radiation,
Vnnn battery volts and a fixed four-byte Fnnnn water level in tenths of a foot.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Literal

from ._data import Measurement, WaterHeight, Weather
from ._errors import FieldError, Unrepresentable
from ._fields import decode_timestamp, encode_timestamp
from ._policy import _DEFAULT_POLICY, EnvelopePolicy
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
    raw: bytes,
    *,
    positioned=False,
    compressed=False,
    diagnostics=None,
    policy: EnvelopePolicy = _DEFAULT_POLICY,
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
            height = _water_height(raw, policy)
            if height:
                values["water_height"], raw = height
                continue
        if tag in "XV" and "weather_extensions" in policy.extensions:
            match = re.match(rb"[XV](\d{3}|\.{3})", raw)
            if match:
                field = match[1]
                if tag == "X":
                    # Resistor-code style: two digits times ten to the third.
                    value = (
                        None
                        if field == b"..."
                        else int(field[:2]) * 10 ** int(field[2:])
                    )
                    values["radiation"] = Measurement(value, "nSv/h", raw=field)
                else:
                    value = None if field == b"..." else int(field) / 10
                    values["battery_voltage"] = Measurement(value, "volts", raw=field)
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
            # Only a number after the tag is a broken field; other text is
            # the comment (for example "home" after the report).
            if diagnostics is not None and re.match(rb"[-.\d]", field):
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
    if CODES.fullmatch(raw):
        values["software_code"] = chr(raw[0])
        values["device_code"] = raw[1:].decode()
        raw = b""
    if not positioned:
        values["comment"] = free_text(
            raw, "$.comment", diagnostics if diagnostics is not None else [], policy
        )
        raw = b""
    return Weather(**values, timestamp=timestamp, raw=original), raw


def _water_height(
    raw: bytes, policy: EnvelopePolicy = _DEFAULT_POLICY
) -> tuple[WaterHeight, bytes] | None:
    """F/f water level: decimal feet/meters (APRS 1.1) or Fnnnn tenths (1.2)."""
    unit: Literal["feet", "meters"] = "feet" if raw[:1] == b"F" else "meters"
    decimal = re.match(rb"[Ff](-?\d+\.\d+)", raw)
    if decimal:
        return WaterHeight(Measurement(float(decimal[1]), unit)), raw[decimal.end() :]
    if unit == "feet" and "water_height_tenths" in policy.extensions:
        tenths = re.match(rb"F(\d{4}|-\d{3}|\.{4})", raw)
        if tenths:
            field = tenths[1]
            value = None if field == b"...." else int(field) / 10
            measurement = Measurement(value, "feet", raw=field)
            return WaterHeight(measurement), raw[tenths.end() :]
    whole = re.match(rb"[Ff](-?\d+)", raw)
    if whole:
        return WaterHeight(Measurement(float(whole[1]), unit)), raw[whole.end() :]
    return None


def radiation_code(value: float | None) -> bytes:
    if value is None:
        return b"..."
    for exponent in range(10):
        mantissa = value / 10**exponent
        if mantissa <= 99 and mantissa == int(mantissa):
            return f"{int(mantissa):02d}{exponent}".encode()
    raise FieldError("radiation is not two digits times a power of ten")


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


def _number(
    value: float | None, width: int, scale: float = 1, path: str = "$"
) -> bytes:
    if value is None:
        return b"." * width
    number = round(value / scale)
    raw = f"{number:0{width}d}".encode()
    if len(raw) != width:
        raise Unrepresentable(path, f"exceeds the {width}-character weather field")
    return raw


# Software S plus unit uuuu (APRS101 p.63) when they are all that remains.
CODES = re.compile(rb"[A-Za-z][A-Za-z0-9]{2,4}")


def write(
    w: Weather,
    *,
    positioned=False,
    compressed=False,
    policy: EnvelopePolicy = _DEFAULT_POLICY,
    path: str = "$",
) -> bytes:
    """Encode a report; error paths are relative to path (the Weather node)."""
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
        direction = _number(
            w.wind_direction.value, 3, path=f"{path}.wind_direction.value"
        )
        # 000/000 reads back as unavailable, so a measured north wind is 360.
        if direction == b"000":
            direction = b"360"
        raw += direction + b"/" + _number(value, 3, path=f"{path}.wind_speed.value")
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
        raw += tag.encode() + _number(v, width, scale, f"{path}.{name}.value")
    if w.snow_24h:
        v = _value(w.snow_24h, "inches")
        if v is not None and v != int(v):
            field = f"{v:.1f}".encode()
            if len(field) != 3:
                raise Unrepresentable(
                    f"{path}.snow_24h.value", "exceeds the 3-character weather field"
                )
        else:
            field = _number(v, 3, path=f"{path}.snow_24h.value")
        raw += b"s" + field
    if w.water_height:
        if w.water_height.reference_datum is not None:
            raise Unrepresentable(
                f"{path}.water_height.reference_datum",
                "the water height has no reference datum field",
            )
        m = w.water_height.measurement
        if m.value is None:
            if m.unit != "feet":
                raise FieldError("only feet water height can be marked unavailable")
            if "water_height_tenths" not in policy.extensions:
                raise FieldError(
                    "unavailable water height requires water_height_tenths"
                )
            raw += b"F...."
        else:
            # A decimal point distinguishes feet from APRS 1.2's Fnnnn tenths.
            # Expand exponents without rounding away small or precise readings;
            # the water-height grammar accepts only ordinary decimal numbers.
            height_text = format(Decimal(str(m.value)), "f")
            if "." not in height_text:
                height_text += ".0"
            raw += (b"F" if m.unit == "feet" else b"f") + height_text.encode()
    if w.radiation:
        raw += b"X" + radiation_code(w.radiation.value)
    if w.battery_voltage:
        raw += b"V" + _number(
            w.battery_voltage.value, 3, 0.1, f"{path}.battery_voltage.value"
        )
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
