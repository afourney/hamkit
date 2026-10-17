# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Execute the README cookbook and verify its advertised output and source bytes."""

import ast
import contextlib
import io
import json
import re
import unittest
from pathlib import Path
from typing import Any, ClassVar, get_args

from hamkit.aprs import Payload


class ReadmeTests(unittest.TestCase):
    namespace: ClassVar[dict[str, Any]]
    outputs: ClassVar[list[tuple[str, str]]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.namespace = {"__name__": "readme_examples"}
        cls.outputs = []
        readme = (Path(__file__).parents[1] / "README.md").read_text()
        pattern = r"```python\n(.*?)\n```(?:\n\nOutput:\n\n```text\n(.*?)\n```)?"
        for index, match in enumerate(re.finditer(pattern, readme, re.DOTALL)):
            code, expected = match.groups()
            ast.parse(code, feature_version=(3, 10))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(  # noqa: S102 - execute trusted repository documentation as tests
                    compile(code, f"README example {index + 1}", "exec"), cls.namespace
                )
            cls.outputs.append((output.getvalue(), expected + "\n" if expected else ""))

    def test_printed_results_match_documentation(self) -> None:
        self.assertGreaterEqual(len(self.outputs), 14)
        for index, (actual, expected) in enumerate(self.outputs):
            with self.subTest(example=index + 1):
                self.assertEqual(actual, expected)

    def test_every_payload_has_a_construction_and_decode_example(self) -> None:
        constructed = self.namespace["constructed"]
        received = self.namespace["received"]
        self.assertEqual(constructed.keys(), received.keys())
        self.assertEqual(
            {type(p.payload) for p in constructed.values()}, set(get_args(Payload))
        )

    def test_referenced_vector_bytes_are_exact(self) -> None:
        document = (
            Path(__file__).parents[1] / "docs" / "APRS_COMPLIANCE_VECTORS.md"
        ).read_text()
        cases = {}
        for block in re.findall(r"```json\n(.*?)\n```", document, re.DOTALL):
            case = json.loads(block)
            if "id" in case:
                cases[case["id"]] = case
        for name, packet in self.namespace["received"].items():
            with self.subTest(vector=name):
                if name in ("Agrelo", "external-vendor"):
                    continue  # Explicit grammar/vendor-wrapper illustrations, not corpus IDs.
                self.assertIn(name, cases)
                case = cases[name]
                raw = case["packet"].encode("latin-1")
                self.assertEqual(packet.original_wire, raw)
                self.assertEqual(len(raw), case["packet_length_bytes"])
                if "packet_hex" in case:
                    self.assertEqual(raw, bytes.fromhex(case["packet_hex"]))
