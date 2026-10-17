# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Spatial invariants from APRS101 chapters 6–11 and APRS 1.1 corrections.

Physical values are not rounded here. Encoders must separately check the selected
wire format's representability. Archival bytes never supply semantic values.
"""
from __future__ import annotations

import math
from typing import Any

from .model_validation import ModelError


def validate_position(v: Any, path: str) -> None:
    name = type(v).__name__

    def fail(field: str, message: str) -> None:
        raise ModelError(f"{path}.{field}", message)

    def same(field: str, expected: float) -> None:
        actual = getattr(v, field)
        if actual is not None and not math.isclose(
            actual, expected, rel_tol=1e-9, abs_tol=1e-9
        ):
            fail(field, "contradicts the authoritative structured fields")

    if name == "Signpost" and (
        not 1 <= len(v.label) <= 3 or any(c in "{}" for c in v.label)
    ):
        fail("label", "requires 1..3 characters without framing braces")
    if name in ("Object", "Item") and (v.name != v.name.strip() or not v.name):
        fail("name", "semantic names cannot contain leading/trailing padding")
    if (
        name in ("Position", "Object")
        and v.timestamp is not None
        and v.timestamp.kind == "mdhm_utc"
    ):
        fail("timestamp", "position/object timestamps require DHM or HMS")
    if name in ("PHG", "Signal"):
        if v.height_haat_ft <= 0:
            fail("height_haat_ft", "encoded antenna height must be positive")
        gain = "gain_dbi" if name == "PHG" else "gain_db"
        if getattr(v, gain) < 0:
            fail(gain, "PHG/DFS gain codes cannot describe negative gain")
    # APRS101 p29, gain corrected to dBi by APRS1.1; half-radius display
    # recommendation is not a second independent transmitted measurement.
    if name == "PHG" and (
        v.range_miles_1_0 is not None or v.display_radius_miles_1_1 is not None
    ):
        try:
            radius = math.sqrt(
                2
                * v.height_haat_ft
                * math.sqrt((v.power_w / 10) * (10 ** (v.gain_dbi / 10) / 2))
            )
        except OverflowError:
            fail("gain_dbi", "derived range exceeds numeric limits")
        same("range_miles_1_0", radius)
        same("display_radius_miles_1_1", radius / 2)
    if name == "Bearing":
        if v.manual is not None and v.manual != (v.hits_code == 9):
            fail("manual", "manual flag must agree with hits_code 9")
        same("range_miles", 2**v.range_code)
        if v.accuracy_less_than_deg is not None and v.accuracy_less_than_deg <= 0:
            fail("accuracy_less_than_deg", "an angular accuracy bound must be positive")
        # Do not fabricate a Q mapping: APRS101 and original PROTOCOL.TXT
        # disagree, and the latter's table omits Q=6.
    if name == "Compression":
        fields = ("type_value", "fix", "nmea_source", "origin_code")
        if v.ignored:
            for field in fields:
                if getattr(v, field) is not None:
                    fail(field, "ignored csT has no meaningful compression metadata")
        else:
            for field in fields:
                if getattr(v, field) is None:
                    fail(field, "required when compression metadata is meaningful")
            expected = (
                (32 if v.fix == "current" else 0)
                + {"other": 0, "GLL": 8, "GGA": 16, "RMC": 24}[v.nmea_source]
                + v.origin_code
            )
            if v.type_value != expected:
                fail("type_value", "must match fix, NMEA source and origin bits")
    if name == "DAO":
        absent = (v.latitude_precision is None, v.longitude_precision is None)
        if absent[0] != absent[1]:
            fail(
                "longitude_precision",
                "latitude and longitude precision must be present or absent together",
            )
        if absent[0]:
            if v.encoding is not None:
                fail("encoding", "datum-only DAO has no precision encoding")
        else:
            if v.encoding is None:
                fail("encoding", "required when precision is present")
            if v.datum_byte.isalpha():
                expected = "decimal" if v.datum_byte.isupper() else "base91"
                if v.encoding != expected:
                    fail(
                        "encoding",
                        "precision encoding must agree with datum letter case",
                    )
    if name == "Area":
        same("latitude_offset_deg", v.latitude_offset_code**2 / 1500)
        same("longitude_offset_deg", v.longitude_offset_code**2 / 1500)
        anchor = "circle_center" if v.shape_code in (0, 5) else "lower_reference"
        if v.transmitted_anchor is not None and v.transmitted_anchor != anchor:
            fail(
                "transmitted_anchor",
                "must agree with the shape's transmitted reference",
            )
        if v.corridor_half_width_miles is not None and v.shape_code not in (1, 6):
            fail("corridor_half_width_miles", "corridors apply only to line shapes")
    if name == "Grid":
        code = v.locator.upper()
        west: float = -180 + (ord(code[0]) - ord("A")) * 20 + int(code[2]) * 2
        south: float = -90 + (ord(code[1]) - ord("A")) * 10 + int(code[3])
        width, height = 2.0, 1.0
        if len(code) == 6:
            width, height = 2 / 24, 1 / 24
            west += (ord(code[4]) - ord("A")) * width
            south += (ord(code[5]) - ord("A")) * height
        if v.bounds is not None:
            for field, expected in (
                ("latitude", (south, south + height)),
                ("longitude", (west, west + width)),
            ):
                if not all(
                    math.isclose(x, y, abs_tol=1e-9, rel_tol=1e-9)
                    for x, y in zip(getattr(v.bounds, field), expected)
                ):
                    fail("bounds." + field, "must match the locator's cell")
        if v.center is not None:
            for field, expected in (
                ("latitude_deg", south + height / 2),
                ("longitude_deg", west + width / 2),
            ):
                if not math.isclose(
                    getattr(v.center, field), expected, abs_tol=1e-9, rel_tol=1e-9
                ):
                    fail("center." + field, "must match the locator's center")
    if name == "Altitude":
        if v.encoding != "nmea" and v.measurement.value is None:
            fail("measurement.value", "this altitude encoding requires a numeric value")
        if v.encoding == "mic_e" and v.reference == "ellipsoid":
            fail("reference", "Mic-E altitude uses mean sea level")
    if name == "Extensions":
        # These alternatives share the immediate seven-byte extension slot.
        primary = ("motion", "phg", "range", "signal", "area")
        present = [f for f in primary if getattr(v, f) is not None]
        if len(present) > 1:
            fail(present[-1], "conflicts with another primary position extension")
        if v.bearing is not None and v.motion is None:
            fail("bearing", "DF bearing requires the preceding course/speed field")
    if name in ("Location", "Position"):
        e = v.extensions
        symbol = (v.symbol.table_id, v.symbol.code)
        if any(c in "|~" for c in v.comment):
            fail(
                "comment",
                "plain comment contains reserved delimiters; use structured extensions",
            )
        if e.storm is not None:
            required = ("/" if e.storm.predicted else "\\", "@")
            if symbol != required:
                fail(
                    "symbol", "storm symbol must agree with predicted/current position"
                )
            if e.motion is None:
                fail("extensions.motion", "storm reports require direction and speed")
        for field, required in (
            ("bearing", ("/", "\\")),
            ("signal", ("/", "\\")),
            ("area", ("\\", "l")),
            ("signpost", ("\\", "m")),
        ):
            if getattr(e, field) is not None and symbol != required:
                fail("symbol", f"{field} requires symbol {required!r}")
        if e.weather is not None:
            if v.symbol.code != "_":
                fail("symbol", "located weather requires the weather symbol")
            if any(
                getattr(e, f) is not None
                for f in ("motion", "phg", "range", "signal", "area", "bearing")
            ):
                fail("extensions.weather", "weather uses the wind extension slot")
            from .validation_weather import validate_weather_report

            validate_weather_report(
                e.weather, path + ".extensions.weather", positioned=True
            )
        if v.ambiguity is not None and v.ambiguity.extent is not None:
            extent = v.ambiguity.extent
            for field, bounds in (
                ("latitude_deg", extent.latitude),
                ("longitude_deg", extent.longitude),
            ):
                if not math.isclose(
                    getattr(v, field), sum(bounds) / 2, abs_tol=1e-9, rel_tol=1e-9
                ):
                    fail(field, "must match the ambiguity cell's center")
    if name in ("Position", "Object", "Item"):
        location = v if name == "Position" else v.position
        telemetry = location.extensions.telemetry
        if telemetry is not None and telemetry.encoding != "base91_comment":
            fail(
                "extensions.telemetry"
                if name == "Position"
                else "position.extensions.telemetry",
                "ordinary located reports require comment telemetry encoding",
            )
        if name == "Position" and v.encoding == "uncompressed" and len(v.comment) > 43:
            fail("comment", "uncompressed position comment exceeds 43 characters")
        if v.encoding == "uncompressed" and location.symbol.table_id.islower():
            fail(
                "symbol" if name == "Position" else "position.symbol",
                "lowercase numeric overlays require compressed encoding",
            )
        if v.encoding == "compressed":
            if location.ambiguity is not None:
                fail(
                    "ambiguity" if name == "Position" else "position.ambiguity",
                    "compressed coordinates do not encode position ambiguity",
                )
            if v.compression is None:
                fail(
                    "compression", "compressed positions require explicit csT semantics"
                )
            e = location.extensions
            if any(
                getattr(e, f) is not None for f in ("phg", "signal", "area", "bearing")
            ):
                fail(
                    "extensions" if name == "Position" else "position.extensions",
                    "extension is unavailable in compressed position layout",
                )
            altitude = e.altitude is not None and e.altitude.encoding == "compressed"
            if v.compression.ignored and (
                e.motion is not None or e.range is not None or altitude
            ):
                fail(
                    "compression",
                    "ignored csT cannot carry motion, range or compressed altitude",
                )
            if not v.compression.ignored:
                if (
                    not altitude
                    and e.motion is None
                    and e.range is None
                    and e.weather is None
                ):
                    fail(
                        "compression",
                        "meaningful csT requires motion, range, altitude or weather wind",
                    )
                if v.compression.nmea_source == "GGA" and not altitude:
                    fail(
                        "compression",
                        "GGA compressed source requires compressed altitude",
                    )
                if altitude and v.compression.nmea_source != "GGA":
                    fail("compression", "compressed altitude requires GGA source bits")
                if altitude and (e.motion is not None or e.range is not None):
                    fail(
                        "compression",
                        "compressed altitude shares the motion/range slot",
                    )
    if name == "MicE":
        telemetry = v.position.extensions.telemetry
        if telemetry is not None and telemetry.encoding not in (
            "mic_e_hex",
            "mic_e_binary",
        ):
            fail(
                "position.extensions.telemetry",
                "Mic-E telemetry requires its encoding variant",
            )
        if v.position.extensions.motion is None:
            fail(
                "position.extensions.motion",
                "Mic-E requires explicit motion or an unavailable Motion pair",
            )
        if (v.grid is None) != (v.grid_symbol is None):
            fail("grid_symbol", "Mic-E grid and its symbol must occur together")
        if v.longitude_offset is not None and v.longitude_offset not in (0, 100):
            fail("longitude_offset", "Mic-E longitude offset is 0 or 100")
