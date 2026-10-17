# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Regenerate the readable JSON catalog: python packages/aprs/tests/generate_json_reference.py."""

from __future__ import annotations

import dataclasses
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any, Union, cast, get_args, get_origin

import hamkit.aprs as a
from hamkit.aprs._json import _BY_MODEL, _HINTS, _SCHEMAS
from model_examples import field_examples, payload_examples

ROOT = Path(__file__).parents[1]


def examples() -> dict[type[a.JSONModel], a.JSONModel]:
    values = {
        type(cast(a.JSONModel, v)): cast(a.JSONModel, v)
        for v in (*field_examples(), *payload_examples())
        if not isinstance(v, (a.CodecSupport, a.Extent))
    }
    values[a.UserDefined] = a.UserDefined(b"Q", b"1", b"Hello\x00\xff")
    values[a.Weather] = a.Weather(
        wind_direction=a.Measurement(270, "degrees"),
        wind_speed=a.Measurement(12, "mph"),
        gust=a.Measurement(15, "mph"),
        temperature=a.Measurement(68, "fahrenheit"),
        pressure=a.Measurement(1013.2, "hPa"),
        timestamp=a.Timestamp.mdhm(10, 17, 12, 30),
    )
    packet = a.parse_packet(b"N0CALL>APRS:!4903.50N/07201.75W>Hello")
    assert isinstance(packet, a.Packet)
    values[a.Packet] = packet
    return values


def catalog_examples() -> list[a.JSONModel]:
    values = examples()
    # Each field class has its own full example. Nested values are expanded as
    # JSON objects, never pseudo references or ellipses. Separate containers
    # demonstrate every union variant in context, too.
    result = [values[s.model] for s in _SCHEMAS]
    containers: tuple[tuple[Any, Callable[[Any], a.JSONModel]], ...] = (
        (a.TelemetryDefinitionValue, lambda v: a.TelemetryDefinition("N0CALL", v)),
        (a.NMEASentence, lambda v: a.NMEA(v, a.NMEAMetadata("GP"))),
        (a.NTSRecord, lambda v: a.Radiogram("W1AW", v)),
        (a.ResponseValue, lambda v: a.Response("W1AW", v)),
    )
    for union, container in containers:
        result.extend(container(values[model]) for model in get_args(union))
    result.append(
        a.Packet(a.Header("N0CALL", "APRS"), cast(a.Weather, values[a.Weather]))
    )
    return result


def annotation_text(annotation: Any) -> str:
    if annotation in _BY_MODEL:
        name = annotation.__name__
        return f"[{name}](#{name.lower()})"
    if annotation is type(None):
        return "null"
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (Union, types.UnionType):
        return " or ".join(annotation_text(v) for v in args)
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return f"array of {annotation_text(args[0])}"
        return (
            "array of exactly "
            + str(len(args))
            + " items: "
            + ", ".join(annotation_text(v) for v in args)
        )
    if origin is not None:  # Literal values are exhaustive, unlike sample values.
        return ", ".join(f"`{v!r}`" for v in args)
    return {
        bytes: "Latin-1 byte string",
        str: "string",
        float: "finite number",
        int: "integer",
        bool: "boolean",
    }.get(annotation, str(annotation))


def default_text(field: dataclasses.Field[Any]) -> str:
    if (
        field.default is dataclasses.MISSING
        and field.default_factory is dataclasses.MISSING
    ):
        return "**required**"
    default = (
        field.default
        if field.default_factory is dataclasses.MISSING
        else field.default_factory()
    )
    if dataclasses.is_dataclass(default):
        return f"optional; default [{type(default).__name__}](#{type(default).__name__.lower()}) with its defaults"
    if default is None:
        return "optional; default `null`"
    if default in (b"", ""):
        return 'optional; default `""`'
    if default == ():
        return "optional; default `[]`"
    return f"optional; default `{str(default).lower() if isinstance(default, bool) else repr(default)}`"


def generate() -> str:
    samples = catalog_examples()
    doc = f"""# APRS JSON reference

This is the canonical JSON format for `hamkit-aprs`. Examples are
pretty-printed, executable data, with nested values expanded. They illustrate
values, not legal ranges or complete APRS wire support. The field tables are the
shape contract: every field, requiredness, default, allowed enum, unit and nested
model is listed. All {len(_SCHEMAS)} serializable models and all \
{len(get_args(a.Payload))} payload families appear.

## Contents

- [Reading and writing](#reading-and-writing)
- [Tags](#tags)
- [Values, defaults and constraints](#values-defaults-and-constraints)
- [Type map and object catalog](#type-map-and-object-catalog)
- [Nested union examples](#nested-union-examples)
- [Complete weather packet](#complete-weather-packet)
- [Regeneration and validation](#regeneration-and-validation)

## Reading and writing

`to_json(model, indent=2)` returns text. `to_json_dict(model)` returns a JSON-safe
dictionary. `from_json(text)` and `from_json_dict(mapping)` return typed models.
Pass `expected_type=Weather` to check the class; typed overloads preserve the
concrete return annotation. `include_defaults=True` prints all fields, as in this
catalog. Compact output omits fields equal to their defaults. Object property
order is not meaningful. JSON field names match Python attributes.

## Tags

One rule decides where `type` appears:

- The top-level object always has a `type`, such as `packet`, `measurement` or
  `header`, unless the reader passes `expected_type`.
- A field that can hold more than one model requires a `type`: `Packet.payload`,
  telemetry definitions, NMEA sentences, NTS records and query responses. The
  tags allowed there are exactly those of the linked models below.
- Every other nested object is untagged on output, because its field allows only
  one model. A `type` supplied there anyway must name that model.

Tags are explicitly registered protocol names, independent of Python class
names; classes are never loaded by name.

## Values, defaults and constraints

- Free text (messages, bulletins, status, comments) is any Unicode string, sent
  as UTF-8 per the adopted APRS 1.2 draft guidance; `to_json` escapes non-ASCII
  so output stays ASCII.
  Protocol tokens (callsigns, addressees, IDs, names, NMEA fields) are printable
  ASCII. Lone surrogates are never valid.
- Raw `bytes` are Latin-1 JSON strings: each U+0000–U+00FF code point represents
  one byte, so `\\u0000` and `\\u00ff` preserve arbitrary binary data. This is
  not base64 and not UTF-8.
- Tuples become arrays. Fixed tuples require the exact length in the table.
  Integers stay integers, even in number fields. Numbers are finite, booleans are not integers, numeric strings are not numbers,
  and enums match exactly, including case.
- Missing optional fields receive the listed defaults. Explicit null is accepted
  only where the type allows it. Missing required fields fail, even when their
  type permits null.
- An absent weather measurement (`null` or omitted) differs from a present
  measurement with `value: null` (unavailable reading), and both differ from zero.
- Units are the exhaustive `Measurement.unit` enum below; nothing is converted.
- `original_wire`, `diagnostics` and `raw`/`*_raw` evidence fields round-trip,
  although Python equality ignores them. They never override structured values.
- Values that follow from other fields (grid bounds and center, PHG range,
  compression type byte, area offsets, bulletin announcement flag, ambiguity
  cell) are Python properties, not JSON fields.
- Loading JSON runs the same constructor checks as Python: values that cannot
  exist on the wire or contradict another field raise `JSONModelError`. APRS
  limits a transmitter could still break (lengths, required report slots,
  symbol choices) are not load errors; `check_packet` reports them and
  `serialize_packet` refuses to send them. See
  [unresolved specification questions](UNRESOLVED_SPEC.md) and
  [wire coverage](API_COVERAGE.md).
- `parse_packet` returns a Packet, or one top-level Malformed when a field
  cannot be decoded. Malformed holds original_wire, diagnostics with field
  paths, and `recovered` data in the ordinary packet schema with unreadable
  fields omitted. Correct it, then load it with `from_json_dict`.
- Unknown fields, duplicate keys, unknown or incompatible tags and invalid
  values raise `JSONModelError` (an `APRSError` and `ValueError`).
- `max_depth` defaults to 64 and accepts integers 1–128. Cycles and excessive
  nesting fail. This is not an input-size bound. `include_defaults` must be bool;
  `indent` is null or a nonnegative integer.

## Type map and object catalog

Tags in this table are exhaustive. Every example includes optional fields and
defaults so its complete shape is visible; null optional nested objects link to
their own fully expanded examples in the field table.

| Model | Stable type | Role |
| --- | --- | --- |
"""
    payloads = set(get_args(a.Payload))
    for schema in _SCHEMAS:
        name = schema.model.__name__
        doc += f"| [{name}](#{name.lower()}) | `{schema.tag}` | {'payload' if schema.model in payloads else 'field / container'} |\n"
    for schema, value in zip(_SCHEMAS, samples):
        name = schema.model.__name__
        doc += f"\n### {name}\n\nStandalone tag: `{schema.tag}`. [Back to type map](#type-map-and-object-catalog).\n\n"
        if schema.model is a.Weather:
            doc += "Weather measurements are direct JSON properties; `weather` is not a JSON property.\n\n"
        doc += (
            "```json\n"
            + a.to_json(value, include_defaults=True, indent=2)
            + "\n```\n\n"
        )
        doc += "| Field | JSON value / allowed values | Presence / default |\n| --- | --- | --- |\n"
        doc += f'| `type` | `"{schema.tag}"` | see [Tags](#tags) |\n'
        entries = [(f, schema.model) for f in dataclasses.fields(schema.model)]
        for f, owner in entries:
            doc += f"| `{f.name}` | {annotation_text(_HINTS[owner][f.name])} | {default_text(f)} |\n"
    doc += "\n## Nested union examples\n\nEach allowed member is shown in its actual container, where it carries its tag.\n"
    for value in samples[len(_SCHEMAS) : -1]:
        members = [
            getattr(value, name)
            for name in ("definition", "sentence", "record", "response")
            if hasattr(value, name)
        ]
        doc += f"\n### {type(value).__name__} with {type(members[0]).__name__}\n\n```json\n{a.to_json(value, include_defaults=True, indent=2)}\n```\n"
    doc += f"\n## Complete weather packet\n\n```json\n{a.to_json(samples[-1], include_defaults=True, indent=2)}\n```\n"
    doc += """
## Regeneration and validation

Run `python packages/aprs/tests/generate_json_reference.py` from the repository
root with the package installed, then run the repository formatting hooks.
`test_json_reference.py` checks every JSON example against the models, verifies
round trips including raw metadata, and checks catalog coverage against the full
public JSONModel union. This prevents examples from silently diverging from code.
Codec support metadata (`CodecSupport`) and `Extent`, which only properties
return, are not JSON data models.
"""
    return doc


if __name__ == "__main__":
    (ROOT / "docs" / "JSON_FORMAT.md").write_text(generate())
