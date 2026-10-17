"""Contextual weather completeness and per-format telemetry model checks."""
from __future__ import annotations

import unittest
from typing import Any

from hamkit import aprs as a


class WeatherInvariantTests(unittest.TestCase):
    def weather(self, **changes: Any) -> a.Weather:
        values: dict[str, Any] = {
            "wind_direction": a.Measurement(None, "degrees"),
            "wind_speed": a.Measurement(None, "mph"),
            "gust": a.Measurement(None, "mph"),
            "temperature": a.Measurement(None, "fahrenheit"),
            "timestamp": a.Timestamp("mdhm_utc", 12, 0, day=17, month=10),
        }
        values.update(changes)
        return a.Weather(**values)

    def test_components_absence_unavailability_and_zero(self) -> None:
        empty = a.Weather()
        self.assertEqual(a.from_json(a.to_json(empty)), empty)
        unavailable = a.Weather(wind_speed=a.Measurement(None, "mph"))
        zero = a.Weather(wind_speed=a.Measurement(0, "mph"))
        self.assertNotEqual(empty, unavailable)
        self.assertNotEqual(unavailable, zero)
        for weather in (
            self.weather(),
            self.weather(wind_speed=a.Measurement(0, "mph")),
        ):
            packet = a.Packet(a.Header("N0CALL", "APRS"), weather)
            self.assertEqual(a.from_json(a.to_json(packet)), packet)
            with self.assertRaises(a.CodecNotImplemented):
                a.serialize_packet(packet)

    def test_positionless_required_slots_and_json(self) -> None:
        for field in (
            "timestamp",
            "wind_direction",
            "wind_speed",
            "gust",
            "temperature",
        ):
            weather = self.weather(**{field: None})
            with self.subTest(field=field):
                with self.assertRaises(a.ModelError):
                    a.Packet(a.Header("N0CALL", "APRS"), weather)
                data = a.to_json_dict(
                    a.Packet(a.Header("N0CALL", "APRS"), self.weather())
                )
                payload = data["payload"]
                assert isinstance(payload, dict)
                del payload[field]
                with self.assertRaises(a.JSONModelError):
                    a.from_json_dict(data)
        with self.assertRaises(a.ModelError):
            a.Packet(
                a.Header("N0CALL", "APRS"),
                self.weather(snow_24h=a.Measurement(1, "inches")),
            )

    def test_located_weather_uses_enclosing_time(self) -> None:
        weather = self.weather(timestamp=None)
        position = a.Position(
            49, -72, a.Symbol("/", "_"), extensions=a.Extensions(weather=weather)
        )
        self.assertIsNone(position.timestamp)
        self.assertEqual(a.from_json(a.to_json(position)), position)
        with self.assertRaises(a.ModelError):
            a.Position(
                49,
                -72,
                a.Symbol("/", "_"),
                extensions=a.Extensions(weather=self.weather()),
            )
        with self.assertRaises(a.ModelError):
            a.Location(
                49,
                -72,
                a.Symbol("/", "_"),
                extensions=a.Extensions(weather=a.Weather()),
            )

    def test_station_identifiers(self) -> None:
        a.Weather(software_code="Z", device_code="ABCD")
        invalid: tuple[dict[str, Any], ...] = (
            {"software_code": ""},
            {"software_code": "XX"},
            {"device_code": "X"},
            {"device_code": "ABCDE"},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(a.ModelError):
                a.Weather(**changes)


class TelemetryInvariantTests(unittest.TestCase):
    def test_classic_complete(self) -> None:
        for sequence in (0, 999, "MIC"):
            model = a.Telemetry((0, 1, 2, 3, 255), (False,) * 8, sequence)  # type: ignore[arg-type]
            self.assertEqual(a.from_json(a.to_json(model)), model)
        for changes in ({"sequence": 1000}, {"sequence": None}, {"mic_comma": False}):
            kwargs: dict[str, Any] = {
                "analog": (1,) * 5,
                "digital": (True,) * 8,
                "sequence": 1,
            }
            kwargs.update(changes)
            with self.assertRaises(a.ModelError):
                a.Telemetry(**kwargs)

    def test_mic_e_profiles(self) -> None:
        for encoding, analog in (
            ("mic_e_hex", (1, 255)),
            ("mic_e_hex", (1,) * 5),
            ("mic_e_binary", (1,) * 5),
        ):
            model = a.Telemetry(analog=analog, encoding=encoding)  # type: ignore[arg-type]
            self.assertEqual(a.from_json(a.to_json(model)), model)
        for changes in (
            {"analog": (1,)},
            {"analog": (1.5, 2)},
            {"analog": (1, 256)},
            {"analog": (None, 2)},
            {"digital": (True,)},
            {"sequence": "MIC"},
            {"comment": "text"},
            {"encoding": "mic_e_binary"},
        ):
            kwargs: dict[str, Any] = {"analog": (1, 2), "encoding": "mic_e_hex"}
            kwargs.update(changes)
            with self.subTest(changes=changes), self.assertRaises(a.ModelError):
                a.Telemetry(**kwargs)

    def test_base91_sequence_and_channel_layout(self) -> None:
        for sequence in (0, 1000, 8280):
            model = a.Telemetry((8280,), sequence=sequence, encoding="base91_comment")
            self.assertEqual(a.from_json(a.to_json(model)), model)
        a.Telemetry((0,) * 5, (True,) * 8, 8280, "base91_comment")
        for changes in (
            {"sequence": None},
            {"sequence": "MIC"},
            {"sequence": 8281},
            {"analog": ()},
            {"analog": (8281,)},
            {"analog": (-1,)},
            {"analog": (0.5,)},
            {"digital": (True,) * 8},
            {"analog": (0,) * 5, "digital": (None,) * 8},
        ):
            kwargs: dict[str, Any] = {
                "analog": (1,),
                "sequence": 1,
                "encoding": "base91_comment",
            }
            kwargs.update(changes)
            with self.subTest(changes=changes), self.assertRaises(a.ModelError):
                a.Telemetry(**kwargs)
        with self.assertRaises(a.JSONModelError):
            a.from_json('{"type":"telemetry","analog":[1],"encoding":"base91_comment"}')

    def test_definition_fields(self) -> None:
        limits = (7, 6, 5, 5, 4, 5, 4, 3, 3, 3, 2, 2, 2)
        for model in (a.Parameters, a.Units):
            full = model(tuple("x" * n for n in limits))
            self.assertEqual(a.from_json(a.to_json(full)), full)
            for i, limit in enumerate(limits):
                values = ["x"] * (i + 1)
                values[i] = "x" * (limit + 1)
                with self.assertRaises(a.ModelError):
                    model(tuple(values))
            for bad in ("a,b", "a|b", "a{b", "a~b"):
                with self.assertRaises(a.ModelError):
                    model((bad,))
        a.Bits((True,) * 8, "x" * 23)
        with self.assertRaises(a.ModelError):
            a.Bits((True,) * 8, "x" * 24)
        with self.assertRaises(a.JSONModelError):
            a.from_json(
                '{"type":"bits","sense":[null,null,null,null,null,null,null,null]}'
            )
