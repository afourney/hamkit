# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Check single-result examples and explicitly adjacent parsing continuations."""

import ast
import contextlib
import dataclasses
import io
import re
import unittest
from pathlib import Path
from typing import Any, ClassVar, get_args
from unittest.mock import patch

import hamkit.aprs as a


class ReadmeTests(unittest.TestCase):
    examples: ClassVar[list[tuple[str, str, str, str]]]

    @classmethod
    def setUpClass(cls) -> None:
        document = (Path(__file__).parents[1] / "README.md").read_text()
        blocks = list(re.finditer(r"```(\w+)\n(.*?)\n```", document, re.DOTALL))
        cls.examples = []
        for index in range(0, len(blocks), 2):
            source, output = blocks[index : index + 2]
            if source[1] != "python" or output[1] != "text":
                raise AssertionError(
                    "Each runnable Python input must pair with text output"
                )
            if document[source.end() : output.start()] != "\n\nOutput:\n\n":
                raise AssertionError("Input must have an immediate Output block")
            literals = [
                node.args[0].value
                for node in ast.walk(ast.parse(source[2]))
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "from_json"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ]
            if len(literals) > 1:
                raise AssertionError("Only one JSON input per block")
            cls.examples.append(
                (
                    (
                        "json"
                        if literals
                        else (
                            "continuation"
                            if source[2] == "print(aprs.to_json(packet, indent=2))"
                            else (
                                "repair"
                                if source[2].startswith("import copy\n")
                                else "python"
                            )
                        )
                    ),
                    literals[0] if literals else source[2],
                    source[2],
                    output[2] + "\n",
                )
            )

    def run_example(
        self,
        language: str,
        source: str,
        code: str,
        expected: str,
        namespace: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Share context only for the explicitly adjacent JSON display.
        if namespace is None:
            namespace = {"__name__": "readme_example"}
        ast.parse(code, feature_version=(3, 11))
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured), patch(
            "builtins.print", wraps=print
        ) as printed:
            exec(compile(code, "README example", "exec"), namespace)  # noqa: S102
        self.assertEqual(
            printed.call_count, 1, "Each example must print exactly one result"
        )
        self.assertEqual(captured.getvalue(), expected)
        return namespace

    def test_every_example_runs_with_only_declared_context_and_exact_output(
        self,
    ) -> None:
        self.assertEqual(len(self.examples), 74)
        namespace: dict[str, Any] | None = None
        for index, example in enumerate(self.examples):
            with self.subTest(example=index + 1):
                if example[0] == "continuation":
                    self.assertGreater(index, 0)
                    self.assertIn("aprs.parse_packet(", self.examples[index - 1][2])
                    self.assertIsNotNone(namespace)
                    namespace = self.run_example(*example, namespace=namespace)
                elif example[0] == "repair":
                    self.assertEqual(self.examples[index - 1][0], "continuation")
                    assert namespace is not None
                    self.assertIsInstance(namespace["packet"], a.Malformed)
                    namespace = self.run_example(*example, namespace=namespace)
                else:
                    namespace = self.run_example(*example)

    def test_one_input_per_block_without_loops_or_shared_helpers(self) -> None:
        for language, source, code, _ in self.examples:
            with self.subTest(source=source[:80]):
                if language == "continuation":
                    self.assertEqual(code, "print(aprs.to_json(packet, indent=2))")
                    continue
                if language == "json":
                    self.assertIsInstance(a.from_json(source), a.Packet)
                if language == "repair":
                    self.assertIn("copy.deepcopy(packet.recovered)", code)
                else:
                    self.assertIn("from hamkit import aprs", code)
                tree = ast.parse(code)
                forbidden = (
                    ast.For,
                    ast.While,
                    ast.ListComp,
                    ast.SetComp,
                    ast.DictComp,
                    ast.GeneratorExp,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                )
                self.assertFalse(any(isinstance(n, forbidden) for n in ast.walk(tree)))
                inputs = [
                    n
                    for n in ast.walk(tree)
                    if isinstance(n, ast.Assign)
                    and any(
                        isinstance(t, ast.Name) and t.id == "packet" for t in n.targets
                    )
                ]
                self.assertEqual(len(inputs), 1)
                value = inputs[0].value
                self.assertIsInstance(value, ast.Call)
                assert isinstance(value, ast.Call)
                self.assertIsInstance(value.func, ast.Attribute)
                assert isinstance(value.func, ast.Attribute)
                self.assertIn(
                    value.func.attr,
                    ("Packet", "parse_packet", "from_json", "from_json_dict"),
                )
                for call in ast.walk(tree):
                    if (
                        isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Attribute)
                        and call.func.attr == "serialize_packet"
                    ):
                        self.assertEqual(len(call.args), 1)
                        self.assertIsInstance(call.args[0], ast.Name)
                        assert isinstance(call.args[0], ast.Name)
                        self.assertEqual(call.args[0].id, "packet")
                if language == "json":
                    self.assertEqual(value.func.attr, "from_json")
                    self.assertEqual(ast.literal_eval(value.args[0]), source)
                if value.func.attr == "parse_packet":
                    self.assertEqual(len(value.args), 1)
                    self.assertIsInstance(value.args[0], ast.Constant)
                    self.assertIsInstance(ast.literal_eval(value.args[0]), bytes)

    def test_every_family_has_equivalent_python_and_json_construction(self) -> None:
        families = set()
        for index, (language, source, _, _) in enumerate(self.examples):
            if language != "json":
                continue
            previous = self.examples[index - 1]
            self.assertEqual(previous[0], "python")
            python_packet = self.run_example(*previous)["packet"]
            json_packet = a.from_json(source, expected_type=a.Packet)
            self.assertEqual(
                dataclasses.asdict(python_packet), dataclasses.asdict(json_packet)
            )
            families.add(type(json_packet.payload))
            wire = a.serialize_packet(
                json_packet,
                policy=a.APRS_IS(
                    legacy_positions=isinstance(json_packet.payload, a.LegacyPosition)
                ),
            )
            # Construction examples print the model name; wire examples print
            # the encoded line. Both must be valid compositions now.
            if self.examples[index][3] != type(json_packet.payload).__name__ + "\n":
                self.assertEqual(
                    (
                        repr(wire)
                        if isinstance(json_packet.payload, a.MicE)
                        else wire.decode("utf-8")
                    )
                    + "\n",
                    self.examples[index][3],
                )

        self.assertEqual(families, set(get_args(a.Payload)))

    def test_successful_parsing_shows_both_object_and_pretty_json(self) -> None:
        count = 0
        for index, (language, source, _, _) in enumerate(self.examples):
            if (
                language != "python"
                or "aprs.parse_packet(" not in source
                or "try:" in source
            ):
                continue
            self.assertIn("print(packet)", source)
            self.assertNotIn("aprs.to_json", source)
            self.assertEqual(self.examples[index + 1][0], "continuation")
            count += 1
        self.assertEqual(count, 6)
