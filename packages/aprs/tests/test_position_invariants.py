# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Spatial validation independent of the not-yet-implemented wire encoders."""
from __future__ import annotations

import math
import unittest
from typing import Any

from hamkit import aprs as a


class PositionInvariantTests(unittest.TestCase):
    def reject_json(self, value: dict[str, Any]) -> None:
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict(value)

    def test_signpost_width_and_names(self) -> None:
        self.assertEqual(a.Signpost("123").label, "123")
        for label in ("1234", "{}"):
            with self.assertRaises(a.ModelError):
                a.Signpost(label)
            self.reject_json({"type": "signpost", "label": label})
        location = a.Location(49, -72, a.Symbol("/", "-"))
        stamp = a.Timestamp("dhm_utc", 12, 30, day=2)
        for name in ("   ", " Test", "Test "):
            with self.assertRaises(a.ModelError):
                a.Object(name, location, stamp)
            with self.assertRaises(a.ModelError):
                a.Item(name, location)
        self.assertFalse(a.Object("Test", location, stamp, alive=False).alive)
        self.assertFalse(a.Item("Test", location, alive=False).alive)

    def test_position_timestamp_family(self) -> None:
        stamp = a.Timestamp("mdhm_utc", 12, 30, day=2, month=1)
        with self.assertRaises(a.ModelError):
            a.Position(49, -72, a.Symbol("/", "-"), timestamp=stamp)
        with self.assertRaises(a.ModelError):
            a.Object("Test", a.Location(49, -72, a.Symbol("/", "-")), stamp)
        self.reject_json(
            {
                "type": "position",
                "latitude_deg": 49,
                "longitude_deg": -72,
                "symbol": {"table_id": "/", "code": "-"},
                "timestamp": a.to_json_dict(stamp),
            }
        )

    def test_dao_absent_and_present_precision(self) -> None:
        for value in (
            a.DAO("W"),
            a.DAO("W", 1, 2, "decimal"),
            a.DAO("w", 90, 0, "base91"),
        ):
            self.assertEqual(a.from_json(a.to_json(value)), value)
        for args in (
            ("W", 1, None, "decimal"),
            ("W", 1, 2, None),
            ("W", None, None, "decimal"),
            ("w", 1, 2, "decimal"),
        ):
            with self.assertRaises(a.ModelError):
                a.DAO(*args)  # type: ignore[arg-type]
        self.reject_json(
            {
                "type": "dao",
                "datum_byte": "w",
                "latitude_precision": 1,
                "longitude_precision": 2,
                "encoding": "decimal",
            }
        )

    def test_compression_bits_and_ignored_metadata(self) -> None:
        for value in (
            a.Compression(58, "current", "RMC", 2),
            a.Compression(ignored=True),
        ):
            self.assertEqual(a.from_json(a.to_json(value)), value)
        with self.assertRaises(a.ModelError):
            a.Compression(0, "current", "GGA", 7)
        with self.assertRaises(a.ModelError):
            a.Compression(0, "old", "other", 0, ignored=True)
        with self.assertRaises(a.ModelError):
            a.Compression()
        self.reject_json(
            {
                "type": "compression",
                "type_value": 0,
                "fix": "current",
                "nmea_source": "GGA",
                "origin_code": 7,
            }
        )

    def test_derived_geometry_and_radio_fields(self) -> None:
        radius = math.sqrt(2 * 80 * math.sqrt((25 / 10) * (10 ** (3 / 10) / 2)))
        phg = a.PHG(
            25, 80, 3, range_miles_1_0=radius, display_radius_miles_1_1=radius / 2
        )
        self.assertEqual(a.from_json(a.to_json(phg)), phg)
        kwargs: dict[str, Any]
        for kwargs in (
            {"height_haat_ft": -5},
            {"gain_dbi": -1},
            {"range_miles_1_0": 1},
            {"display_radius_miles_1_1": 1},
        ):
            values: dict[str, Any] = {
                "power_w": 25,
                "height_haat_ft": 80,
                "gain_dbi": 3,
            }
            values.update(kwargs)
            with self.assertRaises(a.ModelError):
                a.PHG(**values)
            self.reject_json({"type": "phg", **values})
        with self.assertRaises(a.ModelError):
            a.Signal(1, -5, 3)
        bearing = a.Bearing(90, 9, 4, 7, manual=True, range_miles=16)
        self.assertEqual(a.from_json(a.to_json(bearing)), bearing)
        for kwargs in (
            {"manual": False},
            {"range_miles": 2},
            {"accuracy_less_than_deg": -1},
        ):
            with self.assertRaises(a.ModelError):
                a.Bearing(90, 9, 4, 7, **kwargs)
        grid = a.Grid(
            "AA00", a.Extent((-90, -89), (-180, -178)), a.Coordinates(-89.5, -179)
        )
        self.assertEqual(a.from_json(a.to_json(grid)), grid)
        with self.assertRaises(a.ModelError):
            a.Grid("AA00", center=a.Coordinates(0, 0))
        with self.assertRaises(a.ModelError):
            a.Grid("AA00", bounds=a.Extent((0, 1), (0, 2)))
        area = a.Area(
            0,
            3,
            10,
            10,
            latitude_offset_deg=100 / 1500,
            transmitted_anchor="circle_center",
        )
        self.assertEqual(a.from_json(a.to_json(area)), area)
        for kwargs in (
            {"latitude_offset_deg": 1},
            {"transmitted_anchor": "lower_reference"},
            {"corridor_half_width_miles": 1},
        ):
            with self.assertRaises(a.ModelError):
                a.Area(0, 3, 10, 10, **kwargs)

    def test_extension_slots_and_symbols(self) -> None:
        with self.assertRaises(a.ModelError):
            a.Extensions(motion=a.Motion(90, 1), phg=a.PHG(25, 80, 3))
        with self.assertRaises(a.ModelError):
            a.Extensions(bearing=a.Bearing(90, 1, 4, 7))
        extensions = a.Extensions(motion=a.Motion(), bearing=a.Bearing(90, 1, 4, 7))
        self.assertIsInstance(
            a.Position(49, -72, a.Symbol("/", "\\"), extensions=extensions), a.Position
        )
        with self.assertRaises(a.ModelError):
            a.Position(49, -72, a.Symbol("/", "-"), extensions=extensions)
        with self.assertRaises(a.ModelError):
            a.Location(
                49,
                -72,
                a.Symbol("/", "-"),
                extensions=a.Extensions(signpost=a.Signpost("55")),
            )
        self.reject_json(
            {
                "type": "extensions",
                "range": {"miles": 1},
                "phg": {"power_w": 25, "height_haat_ft": 80, "gain_dbi": 3},
            }
        )

    def test_compressed_context_and_raw_evidence(self) -> None:
        with self.assertRaises(a.ModelError):
            a.Position(49, -72, a.Symbol("/", "-"), encoding="compressed")
        valid = a.Position(
            49,
            -72,
            a.Symbol("/", "-"),
            encoding="compressed",
            compression=a.Compression(ignored=True),
        )
        self.assertEqual(a.from_json(a.to_json(valid)), valid)
        with self.assertRaises(a.ModelError):
            a.Position(
                49,
                -72,
                a.Symbol("/", "-"),
                encoding="compressed",
                compression=a.Compression(ignored=True),
                extensions=a.Extensions(motion=a.Motion(90, 1)),
            )
        with self.assertRaises(a.ModelError):
            a.Position(
                49,
                -72,
                a.Symbol("/", "-"),
                encoding="compressed",
                compression=a.Compression(16, "old", "GGA", 0),
            )
        with self.assertRaises(a.ModelError):
            a.Compression(0, "current", "RMC", 2, csT_raw=b"7P[")
        with self.assertRaises(a.ModelError):
            a.Altitude(a.Measurement(None, "feet", raw=b"001234"), "feet_extension")
        with self.assertRaises(a.ModelError):
            a.Item("Test", a.Location(49, -72, a.Symbol("a", "-")))

    def test_mice_grid_pair_and_offset(self) -> None:
        with self.assertRaises(a.ModelError):
            a.MicE(a.Location(49, -72, a.Symbol("/", ">")), (False, False, False))
        location = a.Location(
            49, -72, a.Symbol("/", ">"), extensions=a.Extensions(motion=a.Motion())
        )
        with self.assertRaises(a.ModelError):
            a.MicE(location, (False, False, False), grid=a.Grid("AA00"))
        with self.assertRaises(a.ModelError):
            a.MicE(location, (False, False, False), longitude_offset=99)
