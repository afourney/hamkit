# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

import dataclasses
import json
import re
import unittest
from typing import get_args

from generate_json_reference import ROOT, catalog_examples, generate

import hamkit.aprs as a


class JSONReferenceTests(unittest.TestCase):
    def test_complete_catalog_and_every_documented_example(self) -> None:
        document = (ROOT / "docs" / "JSON_FORMAT.md").read_text()
        blocks = re.findall(r"```json\n(.*?)\n```", document, re.DOTALL)
        samples = catalog_examples()
        self.assertEqual(len(blocks), len(samples))
        self.assertEqual({type(v) for v in samples}, set(get_args(a.JSONModel)))
        for block, sample in zip(blocks, samples):
            with self.subTest(model=type(sample).__name__):
                self.assertEqual(
                    json.loads(block), a.to_json_dict(sample, include_defaults=True)
                )
                decoded = a.from_json(block)
                self.assertEqual(
                    dataclasses.asdict(decoded), dataclasses.asdict(sample)
                )
                self.assertEqual(
                    a.to_json_dict(decoded, include_defaults=True), json.loads(block)
                )
                self.assertEqual(a.from_json(a.to_json(decoded)), decoded)

    def test_field_tables_match_registered_annotations_and_defaults(self) -> None:
        def rows(document: str) -> list[list[str]]:
            return [
                [cell.strip() for cell in line.split("|")]
                for line in document.splitlines()
                if line.startswith("|") and not re.match(r"^\|[ :|-]+$", line)
            ]

        self.assertEqual(
            rows((ROOT / "docs" / "JSON_FORMAT.md").read_text()), rows(generate())
        )
