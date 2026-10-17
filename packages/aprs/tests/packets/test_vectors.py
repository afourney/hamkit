# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

import unittest
from pathlib import Path
from typing import Any

from vector_adapter import load_vectors, semantic_fields

from hamkit.aprs import Packet, parse_packet, serialize_packet


class VectorTests(unittest.TestCase):
    def assert_subset(self, actual: Any, expected: Any) -> None:
        if isinstance(expected, dict):
            for key, value in expected.items():
                self.assertIn(key, actual)
                self.assert_subset(actual[key], value)
        elif isinstance(expected, float):
            self.assertAlmostEqual(actual, expected, delta=1e-8)
        else:
            self.assertEqual(actual, expected)

    def test_focused_fixtures(self) -> None:
        path = Path(__file__).parents[1] / "fixtures" / "foundation.json"
        cases = list(load_vectors(path, profile="core-1.1"))
        self.assertEqual(len(cases), 4)
        for case in cases:
            with self.subTest(id=case["id"]):
                raw = case["packet"].encode("latin-1")
                packet = parse_packet(raw)
                assert isinstance(packet, Packet)
                self.assert_subset(semantic_fields(packet), case["expected"])
                self.assertEqual(serialize_packet(packet), raw)

    def test_profile_selection(self) -> None:
        path = Path(__file__).parents[1] / "fixtures" / "foundation.json"
        self.assertEqual(list(load_vectors(path, profile="compatibility-fap")), [])
