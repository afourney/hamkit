# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Semantic NMEA validation applies equally to Python and JSON construction."""

import json
import unittest
from typing import Any

from hamkit import aprs as a


class NMEAInvariantTests(unittest.TestCase):
    def reject_both(self, model: type[Any], values: dict[str, Any], tag: str) -> None:
        with self.assertRaises(a.ModelError):
            model(**values)
        with self.assertRaises(a.JSONModelError):
            a.from_json(
                json.dumps(
                    {
                        "type": tag,
                        **{
                            k: a.to_json_dict(v)
                            if isinstance(v, (a.UTCTime, a.NMEADate))
                            else v
                            for k, v in values.items()
                        },
                    }
                )
            )

    def test_source_identity_is_explicit(self) -> None:
        missing_talker: dict[str, Any] = {}
        with self.assertRaises(TypeError):
            a.NMEAMetadata(**missing_talker)
        with self.assertRaises(a.JSONModelError):
            a.from_json('{"type": "nmea_metadata"}')
        sentence = a.GLL(None, a.UTCTime(12, 0, 0), "V")
        missing_metadata: dict[str, Any] = {"sentence": sentence}
        with self.assertRaises(TypeError):
            a.NMEA(**missing_metadata)
        with self.assertRaises(a.JSONModelError):
            a.from_json_dict({"type": "nmea", "sentence": a.to_json_dict(sentence)})

    def test_talker_and_checksum_evidence(self) -> None:
        for talker in (",*", "gp", "G1", "G$", "G"):
            self.reject_both(a.NMEAMetadata, {"talker": talker}, "nmea_metadata")
        for validity in (True, False):
            self.reject_both(
                a.NMEAMetadata,
                {"talker": "GP", "checksum_valid": validity},
                "nmea_metadata",
            )
        evidence = a.NMEAMetadata("GN", checksum_supplied="aF", checksum_valid=False)
        self.assertEqual(a.from_json(a.to_json(evidence)), evidence)

    def test_calendar_and_magnetic_variation(self) -> None:
        base = {
            "time_utc": a.UTCTime(12, 0, 0),
            "date": a.NMEADate(1, 1, 24),
            "fix_status": "V",
            "coordinates": None,
        }
        for date in ("310224", "290223", "310424"):
            self.reject_both(
                a.NMEADate,
                {
                    "day": int(date[:2]),
                    "month": int(date[2:4]),
                    "year_mod_100": int(date[4:]),
                },
                "nmea_date",
            )
        for extra in (
            {"magnetic_variation": -1, "magnetic_variation_direction": "E"},
            {"magnetic_variation": 181, "magnetic_variation_direction": "W"},
            {"magnetic_variation": 1},
            {"magnetic_variation_direction": "E"},
        ):
            self.reject_both(a.RMC, {**base, **extra}, "rmc")
        for date in ("290224", "290200", "280223"):
            sentence = a.RMC(
                a.UTCTime(12, 0, 0),
                a.NMEADate(int(date[:2]), int(date[2:4]), int(date[4:])),
                "V",
                None,
            )
            self.assertEqual(a.from_json(a.to_json(sentence)), sentence)
        variation = a.RMC(
            a.UTCTime(12, 0, 0),
            a.NMEADate(1, 1, 24),
            "V",
            None,
            magnetic_variation=0,
            magnetic_variation_direction="E",
        )
        self.assertEqual(a.from_json(a.to_json(variation)), variation)

    def test_differential_fields_and_waypoint_delimiters(self) -> None:
        base = {"time_utc": a.UTCTime(12, 0, 0), "coordinates": None, "fix_quality": 0}
        for age in ("", "-1", "NaN", "1e3", "1,2", " 1"):
            self.reject_both(a.GGA, {**base, "dgps_age": age}, "gga")
        for station in ("A,B", "A*B", "$GP"):
            self.reject_both(a.GGA, {**base, "dgps_station": station}, "gga")
        sentence = a.GGA(
            a.UTCTime(12, 0, 0), None, 0, dgps_age="0.25", dgps_station="TSTR"
        )
        self.assertEqual(a.from_json(a.to_json(sentence)), sentence)
        for name in ("A,B", "A*B", "$GP"):
            with self.assertRaises(a.ModelError):
                a.WPL(a.Coordinates(1, 2), name)
            with self.assertRaises(a.JSONModelError):
                a.from_json(
                    json.dumps(
                        {
                            "type": "wpl",
                            "name": name,
                            "coordinates": {"latitude_deg": 1, "longitude_deg": 2},
                        }
                    )
                )

    def test_usability_cannot_contradict_sentence(self) -> None:
        sentences = (
            a.GLL(None, a.UTCTime(12, 0, 0), "V"),
            a.GLL(a.Coordinates(1, 2), a.UTCTime(12, 0, 0), "V"),
            a.GGA(a.UTCTime(12, 0, 0), a.Coordinates(1, 2), 0),
            a.RMC(a.UTCTime(12, 0, 0), a.NMEADate(1, 1, 24), "V", a.Coordinates(1, 2)),
            a.VTG(),
        )
        for sentence in sentences:
            with self.subTest(sentence=sentence):
                with self.assertRaises(a.ModelError):
                    a.NMEA(sentence, a.NMEAMetadata("GP"), position_usable=True)
                report = a.NMEA(sentence, a.NMEAMetadata("GP"), position_usable=False)
                obj = a.to_json_dict(report)
                obj["position_usable"] = True
                with self.assertRaises(a.JSONModelError):
                    a.from_json_dict(obj)
        valid = a.GLL(a.Coordinates(1, 2), a.UTCTime(12, 0, 0), "A")
        with self.assertRaises(a.ModelError):
            a.NMEA(
                valid,
                a.NMEAMetadata("GP", checksum_supplied="00", checksum_valid=False),
                position_usable=True,
            )
        report = a.NMEA(valid, a.NMEAMetadata("GP"), position_usable=True)
        self.assertEqual(a.from_json(a.to_json(report)), report)
        packet = a.Packet(a.Header("N0CALL", "APRS"), report)
        self.assertEqual(a.parse_packet(a.serialize_packet(packet)), packet)

    def test_receiver_specific_rules_are_not_invented(self) -> None:
        # No received precision is available to establish a speed tolerance.
        a.VTG(speed_knots=1, speed_kmh_reported=1.9)
        # Missing observations are not replaced with a fabricated clock/date.
        a.GLL(None, None, "V")
        a.RMC(a.UTCTime(12, 0, 0), None, "V", None)
