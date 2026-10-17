# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Fixture provenance and regression guards, independent of codec progress."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from generate_vectors import records
from packets.test_corpus import KnownGap, check, differences

from hamkit import aprs as a

VECTORS = Path(__file__).parent / "vectors"


def all_rows() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for file in sorted(VECTORS.glob("*.jsonl"))
        for line in file.read_text().splitlines()
    ]


def test_complete_source_extraction() -> None:
    rows = all_rows()
    assert len(list(VECTORS.glob("*.jsonl"))) == 18
    assert len(rows) == 1561  # 1,538 individual packets + 23 sequence occurrences.
    assert len({row["id"] for row in rows}) == len(rows)
    assert sorted(rows, key=lambda r: r["id"]) == sorted(
        records(), key=lambda r: r["id"]
    )
    assert len({row.get("sequence", row["id"]) for row in rows}) == 1545


def test_comparator_checks_missing_null_lists_and_tolerances() -> None:
    assert differences({}, {"x": None})
    assert differences([1], [1, 2])
    assert differences(True, 1)
    assert differences(1.0, 1.001, "$.latitude_deg")
    assert not differences(1.0, 1.0000000001, "$.latitude_deg")


def test_known_gap_does_not_hide_an_unrelated_regression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = next(r for r in all_rows() if r["id"] == "STA-008")
    packet = a.parse_packet(row["packet"].encode("latin-1"))
    assert isinstance(packet, a.Packet) and isinstance(packet.payload, a.Status)
    with pytest.raises(KnownGap):
        check(row)
    bad = replace(packet, header=a.Header("WRONG", "APRS"))
    monkeypatch.setattr(a, "parse_packet", lambda *args, **kwargs: bad)
    with pytest.raises(AssertionError) as error:
        check(row)
    assert not isinstance(error.value, KnownGap)


def test_completed_gap_returns_success_for_strict_xpass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = next(r for r in all_rows() if r["id"] == "STA-008")
    packet = a.parse_packet(row["packet"].encode("latin-1"))
    assert isinstance(packet, a.Packet) and isinstance(packet.payload, a.Status)
    status = a.Status(" Home", grid=a.Grid("IO91"), symbol=a.Symbol("/", "-"))
    fixed = replace(packet, payload=status)
    monkeypatch.setattr(a, "parse_packet", lambda *args, **kwargs: fixed)
    check(row)  # The parametrized test's strict mark turns this into XPASS/failure.


def test_parser_exception_is_not_an_expected_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = next(r for r in all_rows() if r["id"] == "MIC-001")

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("unexpected parser crash")

    monkeypatch.setattr(a, "parse_packet", broken)
    with pytest.raises(RuntimeError, match="unexpected parser crash"):
        check(row)


def test_projection_keys_belong_to_public_json_models() -> None:
    """Catch adapter typos and invalid enum values, even for missing codecs."""
    import dataclasses
    import types
    from typing import Literal, Union, get_args, get_origin, get_type_hints

    from hamkit.aprs._json import _SCHEMAS

    tags = {schema.tag: schema.model for schema in _SCHEMAS}

    def validate(value: Any, annotation: Any, path: str) -> None:
        if value is None:
            return
        model: Any
        origin, args = get_origin(annotation), get_args(annotation)
        # Enforce enums only where every non-null option is a Literal.
        options = args if origin in (Union, types.UnionType) else (annotation,)
        options = tuple(t for t in options if t is not type(None))
        if options and all(get_origin(t) is Literal for t in options):
            allowed = [v for t in options for v in get_args(t)]
            assert value in allowed, (path, value, allowed)
            return
        if isinstance(value, dict):
            if "type" in value:
                assert value["type"] in tags, (path, value["type"])
                model = tags[value["type"]]
            elif origin in (Union, types.UnionType):
                models = [
                    t
                    for t in args
                    if isinstance(t, type) and dataclasses.is_dataclass(t)
                ]
                if len(models) != 1:
                    return
                model = models[0]
            else:
                model = annotation
            if not isinstance(model, type) or not dataclasses.is_dataclass(model):
                return
            hints = get_type_hints(model)
            assert set(value) <= hints.keys() | {"type"}, (
                path,
                set(value) - hints.keys(),
            )
            for key, child in value.items():
                if key != "type":
                    validate(child, hints[key], f"{path}.{key}")
        elif isinstance(value, list) and origin is tuple:
            for child in value:
                validate(child, args[0], path + "[]")

    for row in all_rows():
        if row["expected"] is not None:
            validate(row["expected"], a.Packet, row["id"])
