# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Constructor invariants, independent of codec availability and raw evidence."""
from __future__ import annotations

import math
import re
import types
from dataclasses import fields, is_dataclass
from functools import cache
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

from .errors import FieldError


class ModelError(FieldError):
    """An invalid structured field, with a machine-readable path."""

    def __init__(self, path: str, message: str):
        self.path = path
        super().__init__(f"{path}: {message}")


class Validated:
    def __post_init__(self) -> None:
        validate_model(self)


@cache
def hints(model: type[Any]) -> dict[str, Any]:
    return get_type_hints(model)


def json_data(value: object, path: str = "$", depth: int = 0) -> None:
    if depth > 64:
        raise ModelError(path, "JSON nesting limit exceeded")
    if value is None or type(value) in (bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is str and not any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        return
    if type(value) is list:
        for i, child in enumerate(value):
            json_data(child, f"{path}[{i}]", depth + 1)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for key, child in value.items():
            json_data(key, path, depth + 1)
            json_data(child, f"{path}.{key}", depth + 1)
        return
    raise ModelError(path, "expected finite, surrogate-free JSON data")


def _check(value: Any, annotation: Any, path: str, active: set[int]) -> None:
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (Union, types.UnionType):
        if isinstance(value, Validated) and type(value) in args:
            validate_model(value, path, active)
            return
        for variant in args:
            try:
                _check(value, variant, path, active)
                return
            except ModelError:
                pass
        raise ModelError(path, "value does not match the declared field type")
    if origin is Literal:
        if any(type(value) is type(v) and value == v for v in args):
            return
    elif origin is tuple and type(value) is tuple:
        repeated = len(args) == 2 and args[1] is Ellipsis
        if repeated or len(value) == len(args):
            for i, child in enumerate(value):
                _check(child, args[0] if repeated else args[i], f"{path}[{i}]", active)
            return
    elif origin is dict and type(value) is dict:
        json_data(value, path)
        return
    elif annotation is float and type(value) in (float, int):
        try:
            if math.isfinite(value):
                return
        except OverflowError:
            pass
    elif type(value) is annotation:
        if isinstance(value, Validated):
            validate_model(value, path, active)
        elif isinstance(value, str):
            json_data(value, path)
        return
    raise ModelError(path, f"invalid value for {annotation!r}")


def validate_model(value: Any, path: str = "$", active: set[int] | None = None) -> None:
    if not isinstance(value, Validated) or not is_dataclass(value):
        raise ModelError(path, "expected a validated APRS model")
    active = set() if active is None else active
    if id(value) in active:
        raise ModelError(path, "cyclic model graph")
    active.add(id(value))
    try:
        for f in fields(value):
            _check(
                getattr(value, f.name),
                hints(type(value))[f.name],
                f"{path}.{f.name}",
                active,
            )
        _semantics(value, path)
    finally:
        active.remove(id(value))


def _semantics(v: Any, path: str) -> None:
    name = type(v).__name__

    def fail(field: str, message: str) -> None:
        raise ModelError(f"{path}.{field}", message)

    def bounds(field: str, low: float, high: float) -> None:
        x = getattr(v, field, None)
        if x is not None and not low <= x <= high:
            fail(field, f"must be in {low}..{high}")

    def length(field: str, low: int, high: int) -> None:
        x = getattr(v, field, None)
        if x is not None and not low <= len(x) <= high:
            fail(field, f"length must be in {low}..{high}")

    # Tuple-valued text (addresses, channel names) follows the same policy.
    for f in fields(v):
        x = getattr(v, f.name)
        texts = x if isinstance(x, tuple) else (x,)
        if name not in ("Diagnostic", "Malformed") and f.name not in (
            "reason",
            "specification_url",
        ):
            for item in texts:
                if isinstance(item, str) and any(not 32 <= ord(c) <= 126 for c in item):
                    fail(f.name, "protocol text must be printable ASCII")
    if name in ("Position", "Location", "Coordinates"):
        bounds("latitude_deg", -90, 90)
        bounds("longitude_deg", -180, 180)
    if (
        name in ("Position", "Location")
        and v.tail
        and (
            v.comment
            or any(
                getattr(v.extensions, f.name) is not None for f in fields(v.extensions)
            )
        )
    ):
        fail("tail", "raw suffix cannot accompany structured extensions or comment")
    if name in ("Position", "Object", "Item"):
        if v.encoding == "uncompressed" and v.compression is not None:
            fail("compression", "requires compressed encoding")
        if (
            name == "Position"
            and v.encoding == "uncompressed"
            and v.symbol.table_id.islower()
        ):
            fail("symbol.table_id", "lowercase overlays require compressed encoding")
    if name == "Extent":
        for field, limit in (("latitude", 90), ("longitude", 180)):
            lo, hi = getattr(v, field)
            if not -limit <= lo <= hi <= limit:
                fail(field, "requires ordered bounds within coordinate limits")
    if name == "Ambiguity":
        bounds("digits", 0, 4)
    if name == "Symbol":
        if (
            len(v.table_id) != 1
            or v.table_id not in "/\\0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        ):
            fail("table_id", "invalid symbol table/overlay")
        if len(v.code) != 1 or not 33 <= ord(v.code) <= 126:
            fail("code", "requires one printable symbol code")
    if name == "Timestamp":
        bounds("hour", 0, 23)
        bounds("minute", 0, 59)
        if v.kind == "hms_utc":
            if v.second is None:
                fail("second", "required for HMS")
            bounds("second", 0, 59)
            if v.day is not None or v.month is not None:
                fail("day", "HMS has no day/month")
        else:
            if v.day is None:
                fail("day", "required for DHM/MDHM")
            bounds("day", 1, 31)
            if v.second is not None:
                fail("second", "only valid for HMS")
            if v.kind == "mdhm_utc":
                if v.month is None:
                    fail("month", "required for MDHM")
                bounds("month", 1, 12)
                if v.month is not None and v.day > (
                    29 if v.month == 2 else 30 if v.month in (4, 6, 9, 11) else 31
                ):
                    fail("day", "not valid for month")
            elif v.month is not None:
                fail("month", "only valid for MDHM")
    if name in ("Header", "Hop"):
        for field in ("source", "destination") if name == "Header" else ("address",):
            x = getattr(v, field)
            if not x or any(ord(c) < 33 or ord(c) > 126 or c in ">,:*" for c in x):
                fail(field, "empty or invalid address token")
    if hasattr(v, "addressee") and v.addressee is not None:
        length("addressee", 1, 9)
        if v.addressee.endswith(" ") or ":" in v.addressee:
            fail("addressee", "invalid addressee padding or delimiter")
    for field in ("message_id", "previous_ack", "message_number"):
        if (
            hasattr(v, field)
            and getattr(v, field) is not None
            and not re.fullmatch(r"[A-Za-z0-9]{1,5}", getattr(v, field))
        ):
            fail(field, "requires 1..5 alphanumeric characters")
    if name == "Status":
        length("text", 0, 62 - (7 if v.timestamp is not None else 0))
        if v.timestamp is not None and v.timestamp.kind != "dhm_utc":
            fail("timestamp", "status requires DHM UTC")
        if v.timestamp is None and re.match(r"[0-9]{6}z", v.text):
            fail("text", "would be interpreted as a timestamp")
    if name == "Message":
        length("text", 0, 67)
        if any(c in "{|~" for c in v.text):
            fail("text", "contains a reserved message delimiter")
        if v.message_id is None and re.fullmatch(r"(ack|rej)[A-Za-z0-9]{1,5}", v.text):
            fail("text", "would be interpreted as acknowledgment")
    if name in ("Object", "Item"):
        length("name", 1 if name == "Object" else 3, 9)
        if name == "Item" and any(c in "!_" for c in v.name):
            fail("name", "contains item delimiter")
    if name == "Grid" and not re.fullmatch(
        r"[A-Ra-r]{2}[0-9]{2}(?:[A-Xa-x]{2})?", v.locator
    ):
        fail("locator", "requires four or six Maidenhead characters")
    if name in ("DecodeOptions", "EncodeOptions"):
        bounds("max_depth", 0, 32)
    if name == "UserDefined":
        length("user_id", 1, 1)
        length("user_type", 1, 1)
    if name == "Reserved":
        bounds("dti", 0, 255)
    if name in ("Opaque", "RawWeather", "ExternalExtension", "EncodedPacketFields"):
        length("information", 1, 2**31)
    if name == "Malformed" and not v.diagnostics:
        fail("diagnostics", "at least one diagnostic is required")
    if name in ("Motion", "RMC", "VTG"):
        for field in ("course_deg", "course_true_deg", "course_magnetic_deg"):
            bounds(field, 0, 360)
        for field in ("speed_knots", "speed_kmh_reported"):
            bounds(field, 0, float("inf"))
    for field in ("bearing_deg", "heading_deg", "directivity_deg"):
        bounds(field, 0, 360)
    for field in (
        "miles",
        "radius_miles",
        "erp_w",
        "power_w",
        "range_miles",
        "range_miles_1_0",
        "display_radius_miles_1_1",
        "corridor_half_width_miles",
        "sustained_wind_knots",
        "peak_gust_knots",
        "central_pressure_hpa",
        "hurricane_radius_nm",
        "tropical_storm_radius_nm",
        "whole_gale_radius_nm",
    ):
        bounds(field, 0, float("inf"))
    if name == "Signal":
        bounds("s_units", 0, 9)
    if name == "Bearing":
        for field in ("hits_code", "range_code", "quality_code"):
            bounds(field, 0, 9)
    if name == "Agrelo":
        bounds("quality_code", 0, 9)
    if name == "Compression":
        bounds("type_value", 0, 63)
        bounds("origin_code", 0, 7)
    if name == "DAO":
        length("datum_byte", 1, 1)
        bounds("latitude_precision", 0, 9 if v.encoding == "decimal" else 90)
        bounds("longitude_precision", 0, 9 if v.encoding == "decimal" else 90)
    if name == "Area":
        bounds("shape_code", 0, 9)
        bounds("color_code", 0, 15)
        bounds("latitude_offset_code", 0, 99)
        bounds("longitude_offset_code", 0, 99)
    if (
        name == "Packet"
        and type(v.payload).__name__ == "Weather"
        and v.payload.timestamp is None
    ):
        fail("payload.timestamp", "positionless weather requires an MDHM timestamp")
    if name == "Weather" and v.timestamp is not None and v.timestamp.kind != "mdhm_utc":
        fail("timestamp", "weather requires MDHM UTC")
    if name == "Telemetry":
        if not v.analog and not v.digital:
            fail("analog", "at least one channel is required")
        if v.encoding == "classic":
            if v.sequence is None:
                fail("sequence", "classic telemetry requires a sequence or MIC")
            length("analog", 5, 5)
            length("digital", 8, 8)
            if any(
                x is None or not float(x).is_integer() or not 0 <= x <= 255
                for x in v.analog
            ):
                fail(
                    "analog",
                    "classic telemetry requires five integer channels in 0..255",
                )
            if any(x is None for x in v.digital):
                fail("digital", "classic telemetry requires eight binary channels")
        length("analog", 0, 5)
        length("digital", 0, 8)
        if type(v.sequence) is int:
            bounds("sequence", 0, 999)
    if name in ("Parameters", "Units"):
        length("channels", 1, 13)
        if any(
            x is not None and any(not 32 <= ord(c) <= 126 for c in x)
            for x in v.channels
        ):
            fail("channels", "protocol names/units require printable ASCII")
    if name == "Equations":
        length("coefficients", 1, 5)
    if name == "Bits":
        length("sense", 8, 8)
    if name == "Weather":
        expected = {
            "wind_direction": {"degrees"},
            "wind_speed": {"mph", "knots", "m/s", "km/h", "disputed_knots_or_mph"},
            "gust": {"mph", "knots", "m/s", "km/h"},
            "temperature": {"fahrenheit", "celsius"},
            "humidity": {"percent"},
            "pressure": {"hPa"},
            "luminosity": {"W/m2"},
            "rain_counter": {"count", "raw"},
        }
        expected.update(
            {
                f: {"inches", "mm"}
                for f in ("rain_1h", "rain_24h", "rain_since_midnight", "snow_24h")
            }
        )
        for field, units in expected.items():
            reading = getattr(v, field)
            if reading is not None:
                if reading.unit not in units:
                    fail(field + ".unit", "unit does not describe this quantity")
                if reading.value is not None:
                    low = (
                        -273.15
                        if reading.unit == "celsius"
                        else -459.67
                        if reading.unit == "fahrenheit"
                        else 0
                    )
                    high = (
                        100
                        if field == "humidity"
                        else 360
                        if field == "wind_direction"
                        else float("inf")
                    )
                    if not low <= reading.value <= high:
                        fail(field + ".value", "reading outside quantity bounds")
    if name in ("Altitude", "WaterHeight") and v.measurement.unit not in (
        "feet",
        "meters",
    ):
        fail("measurement.unit", "height requires feet or meters")
    if name == "HeardStation" and any(x is not None and x < 0 for x in v.counts):
        fail("counts", "counts cannot be negative")
    if name == "NMEAMetadata":
        length("talker", 2, 2)
        if v.checksum_supplied is not None and not re.fullmatch(
            r"[0-9A-Fa-f]{2}", v.checksum_supplied
        ):
            fail("checksum_supplied", "requires two hexadecimal digits")
    if name in ("GGA", "GLL", "RMC"):
        if not re.fullmatch(
            r"(?:[01][0-9]|2[0-3])[0-5][0-9][0-5][0-9](?:\.[0-9]+)?", v.time_utc
        ):
            fail("time_utc", "requires HHMMSS with optional fraction")
        if (
            (name in ("GLL", "RMC") and v.fix_status == "A")
            or (name == "GGA" and v.fix_quality > 0)
        ) and v.coordinates is None:
            fail("coordinates", "a valid fix requires coordinates")
        if name == "GGA":
            bounds("fix_quality", 0, 8)
            bounds("satellites", 0, 99)
            bounds("hdop", 0, float("inf"))
        if name == "RMC" and not re.fullmatch(
            r"(?:0[1-9]|[12][0-9]|3[01])(?:0[1-9]|1[0-2])[0-9]{2}", v.date_ddmmyy
        ):
            fail("date_ddmmyy", "requires DDMMYY")
    if name in ("Query", "Capability", "WPL", "Phone", "Signpost"):
        field = (
            "number" if name == "Phone" else "label" if name == "Signpost" else "name"
        )
        length(field, 1, 80)
