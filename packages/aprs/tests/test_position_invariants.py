# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Spatial constructor rules, independent of the not-yet-implemented encoders."""
from __future__ import annotations

import unittest
from typing import Any

from hamkit import aprs as a

SYMBOL = a.Symbol("/", "-")


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
        stamp = a.Timestamp.dhm(2, 12, 30)
        for name in ("   ", " Test", "Test ", "TenLetters"):
            with self.assertRaises(a.ModelError):
                a.Object(name, 49, -72, SYMBOL, timestamp=stamp)
            with self.assertRaises(a.ModelError):
                a.Item(name, 49, -72, SYMBOL)
        self.assertFalse(
            a.Object("Test", 49, -72, SYMBOL, timestamp=stamp, alive=False).alive
        )
        self.assertFalse(a.Item("Test", 49, -72, SYMBOL, alive=False).alive)

    def test_position_timestamp_family(self) -> None:
        stamp = a.Timestamp.mdhm(1, 2, 12, 30)
        with self.assertRaises(a.ModelError):
            a.Position(49, -72, SYMBOL, timestamp=stamp)
        with self.assertRaises(a.ModelError):
            a.Object("Test", 49, -72, SYMBOL, timestamp=stamp)
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
            a.DAO("W", latitude_precision=1, longitude_precision=2, encoding="decimal"),
            a.DAO("w", latitude_precision=90, longitude_precision=0, encoding="base91"),
        ):
            self.assertEqual(a.from_json(a.to_json(value)), value)
        for kwargs in (
            {"latitude_precision": 1, "encoding": "decimal"},
            {"latitude_precision": 1, "longitude_precision": 2},
            {"encoding": "decimal"},
            {"latitude_precision": 10, "longitude_precision": 2, "encoding": "decimal"},
        ):
            with self.assertRaises(a.ModelError):
                a.DAO("W", **kwargs)
        self.reject_json(
            {
                "type": "dao",
                "datum_byte": "w",
                "latitude_precision": 1,
                "longitude_precision": 2,
                "encoding": "decimal",
            }
        )

    def test_compression_metadata(self) -> None:
        for value in (
            a.Compression(fix="current", nmea_source="RMC", origin_code=2),
            a.Compression(ignored=True),
        ):
            self.assertEqual(a.from_json(a.to_json(value)), value)
        with self.assertRaises(a.ModelError):
            a.Compression(fix="current", nmea_source="GGA", origin_code=8)
        with self.assertRaises(a.ModelError):
            a.Compression(fix="old", nmea_source="other", origin_code=0, ignored=True)
        with self.assertRaises(a.ModelError):
            a.Compression()
        self.reject_json({"type": "compression", "type_value": 58})

    def test_radio_fields(self) -> None:
        for kwargs in ({"height_haat_ft": -5}, {"gain_dbi": -1}, {"power_w": -1}):
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
        with self.assertRaises(a.ModelError):
            a.Bearing(90, 10, 4, 7)
        with self.assertRaises(a.ModelError):
            a.Bearing(90, 9, 4, 7, accuracy_less_than_deg=-1)
        with self.assertRaises(a.ModelError):
            a.Area(0, 3, 10, 10, corridor_half_width_miles=1)
        self.assertEqual(
            a.Area(1, 3, 10, 10, corridor_half_width_miles=1).shape_code, 1
        )
        self.reject_json({"type": "grid", "locator": "AA00", "center": None})

    def test_unrepresentable_layouts(self) -> None:
        with self.assertRaises(a.ModelError):
            a.Item("Test", 49, -72, a.Symbol("a", "-"))
        overlay = a.Item(
            "Test", 49, -72, a.Symbol("a", "-"), compression=a.Compression(ignored=True)
        )
        self.assertTrue(overlay.compressed)
        with self.assertRaises(a.ModelError):
            a.Position(
                49, -72, SYMBOL, ambiguity=1, compression=a.Compression(ignored=True)
            )
        with self.assertRaises(a.ModelError):
            a.Altitude(a.Measurement(None, "feet", raw=b"001234"), "feet_extension")
        with self.assertRaises(a.ModelError):
            a.Altitude(a.Measurement(1, "feet"), "mic_e", reference="ellipsoid")
