# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Weather and telemetry values: absence, units and channel shapes."""
from __future__ import annotations

import unittest

from hamkit import aprs as a


class WeatherInvariantTests(unittest.TestCase):
    def test_components_absence_unavailability_and_zero(self) -> None:
        empty = a.Weather()
        self.assertEqual(a.from_json(a.to_json(empty)), empty)
        unavailable = a.Weather(wind_speed=a.Measurement(None, "mph"))
        zero = a.Weather(wind_speed=a.Measurement(0, "mph"))
        self.assertNotEqual(empty, unavailable)
        self.assertNotEqual(unavailable, zero)
        # An incomplete report is a valid model; only sending checks the slots.
        packet = a.Packet(a.Header("N0CALL", "APRS"), empty)
        self.assertEqual(a.from_json(a.to_json(packet)), packet)
        self.assertTrue(a.check_packet(packet))
        with self.assertRaises(a.CodecNotImplementedError):
            a.serialize_packet(packet)

    def test_units_describe_the_quantity(self) -> None:
        for field, unit in (
            ("temperature", "mph"),
            ("humidity", "celsius"),
            ("rain_1h", "hPa"),
            ("wind_speed", "degrees"),
        ):
            with self.subTest(field=field), self.assertRaises(a.ModelError):
                a.Weather(**{field: a.Measurement(1, unit)})  # type: ignore[arg-type]
        with self.assertRaises(a.ModelError):
            a.WaterHeight(a.Measurement(1, "inches"))
        with self.assertRaises(a.ModelError):
            a.Weather(timestamp=a.Timestamp.dhm(1, 2, 3))


class TelemetryInvariantTests(unittest.TestCase):
    def test_channel_counts_and_sequence(self) -> None:
        for kwargs in (
            {"analog": (1,) * 6},
            {"digital": (True,) * 9},
            {"analog": (1,), "sequence": -1},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(a.ModelError):
                a.Telemetry(**kwargs)  # type: ignore[arg-type]
        for model in (a.TelemetryParameters, a.TelemetryUnits):
            with self.assertRaises(a.ModelError):
                model(("a,b",))
        with self.assertRaises(a.JSONModelError):
            a.from_json('{"type":"telemetry_bits","sense":[true]}')
        bits = a.TelemetryBits((True,) * 8, project_title="x" * 23)
        self.assertEqual(a.from_json(a.to_json(bits)), bits)
