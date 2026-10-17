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
from hamkit.aprs.json import _BY_MODEL, _HINTS, _SCHEMAS
from model_examples import field_examples, payload_examples

ROOT = Path(__file__).parents[1]


def examples() -> dict[type[a.JSONModel], a.JSONModel]:
    values = {
        type(cast(a.JSONModel, v)): cast(a.JSONModel, v)
        for v in (*field_examples(), *payload_examples())
        if not isinstance(v, a.CodecCapability)
    }
    values[a.UserDefined] = a.UserDefined(b"Q", b"1", b"Hello\x00\xff")
    values[a.Weather] = a.Weather(
        wind_direction=a.Measurement(270, "degrees"),
        wind_speed=a.Measurement(12, "mph"),
        temperature=a.Measurement(68, "fahrenheit"),
        pressure=a.Measurement(1013.2, "hPa"),
        timestamp=a.Timestamp("mdhm_utc", 12, 30, day=17, month=10),
    )
    values[a.Packet] = a.parse_packet(b"N0CALL>APRS:!4903.50N/07201.75W>")
    return values


def catalog_examples() -> list[a.JSONModel]:
    values = examples()
    # Each field class has its own full example. Nested values are expanded as
    # JSON objects, never pseudo references or ellipses. Separate containers
    # demonstrate every union variant in context, too.
    result = [values[s.model] for s in _SCHEMAS]
    containers: tuple[tuple[Any, Callable[[Any], a.JSONModel]], ...] = (
        (a.DefinitionValue, lambda v: a.Definition("N0CALL", v)),
        (a.NMEASentence, a.NMEA),
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
    if default == b"":
        return 'optional; default `""`'
    if default == ():
        return "optional; default `[]`"
    return f"optional; default `{str(default).lower() if isinstance(default, bool) else repr(default)}`"


def generate() -> str:
    samples = catalog_examples()
    doc = """# APRS JSON reference

This is the canonical JSON format for `hamkit-aprs`. Examples are
pretty-printed, executable data, with nested values expanded. They illustrate
values, not legal ranges or complete APRS wire support. The field tables are the
shape contract: every field, requiredness, default, allowed enum, unit and nested
model is listed. All 83 serializable models and all 29 payload families appear.

## Contents

- [Reading and writing](#reading-and-writing)
- [Tags and context](#tags-and-context)
- [Values, defaults and constraints](#values-defaults-and-constraints)
- [Type map and object catalog](#type-map-and-object-catalog)
- [Nested union examples](#nested-union-examples)
- [Complete weather packet](#complete-weather-packet)
- [Regeneration and validation](#regeneration-and-validation)

## Reading and writing

`to_json(model, indent=2)` returns text. `to_json_dict(model)` returns a JSON-safe
dictionary. `from_json(text)` and `from_json_dict(mapping)` return typed models.
Use `expected_type=Weather` to check a particular class; typed overloads
preserve the concrete return annotation. This does not waive payload tags.
`include_defaults=True` prints all fields, as in this catalog. The normal compact
output omits default-valued optional fields, but always retains `type` where
required. Object property order is not meaningful.

## Tags and context

- Every standalone object has a lowercase semantic `type`, including `packet`,
  `measurement`, and `header`. Tags are explicitly registered protocol-independent
  names; Python class names cannot be loaded dynamically.
- Every payload requires its own `type`, whether standalone, in `Packet.payload`,
  or in a fixed payload field such as `LegacyPosition.position`. Shared
  `Weather` and `Telemetry` values in fixed nested fields are untagged, because
  those fields identify their class; when used as payloads they require tags.
- Nested unions of multiple model classes require a tag: telemetry definitions,
  NMEA sentences, NTS records and query responses. The tags allowed at each union
  are exactly those of its linked models in the tables below.
- Fixed nested models are emitted without tags: a measurement's containing field
  already specifies `Measurement`; a header field specifies `Header`. Optional
  fixed models remain untagged when present. Arrays follow the same rule for
  their declared element type. Scalar unions use strict JSON value types.
- An untagged standalone fixed field may be read only with explicit
  `expected_type=Measurement` (or another concrete non-payload class). A supplied
  tag must always agree with that class. There is no structural inference.
- `Weather` and `Telemetry` are shared semantic models, usable as complete
  payloads or fixed nested values. Python and JSON both expose their fields
  directly. Weather carries optional timestamp/comment; telemetry carries a
  comment alongside its channels, sequence and encoding evidence. Nothing is
  discarded when either model is nested. A Weather field can have no observations;
  a full positionless-weather Packet still needs a timestamp. See the [naming guide](NAMING.md) for the meanings
  of short names and the reasons for qualified names.
- Third-party payloads contain `packet`, whose fixed Packet object is untagged;
  the inner `payload` has its own tag. See [ThirdParty](#thirdparty).
- JSON field names match Python attributes.

## Values, defaults and constraints

- Protocol text and identifiers are printable ASCII Python strings, including
  status/message text, comments, names and NMEA time/date tokens. Constructors
  reject control characters, high-bit text and surrogates. Wire decoding never
  silently replaces characters or guesses an encoding: undecodable supported
  text produces a Malformed recovery result with original bytes.
- Genuinely raw `bytes` are Latin-1 JSON strings: each U+0000–U+00FF code point represents one
  byte. JSON escapes such as `\\u0000` and `\\u00ff` preserve arbitrary binary data;
  this is not base64 and does not decode bytes as UTF-8. `to_json` emits ASCII-safe
  escapes. Diagnostic explanations and recovered JSON may contain Unicode scalar
  values; protocol text fields use printable ASCII.
- Tuples become arrays. Fixed tuples require the exact length in the table;
  variadic tuples follow their model constraints (e.g. classic telemetry channel
  counts). Numbers are finite, booleans are not integers,
  numeric strings are not numbers, and enums match exactly, including case.
- Missing optional fields receive the listed Python defaults. Explicit null is
  accepted only where the type allows null. The model does not remember whether
  optional `None` came from omission or explicit null. Missing required fields
  fail, even when their type permits null.
- An absent weather measurement (`null` or omitted) differs from a present
  measurement with `value: null` (unavailable reading), and both differ from zero.
- Unit strings are the exhaustive `Measurement.unit` enum below. Units are
  explicit; conversion performs no unit conversion. Use semantically appropriate
  units for the weather quantity (e.g. degrees, mph, fahrenheit and hPa).
- `original_wire`, raw fields and diagnostic metadata are preserved, including
  fields ignored by dataclass equality. They do not override edited structured
  values. JSON conversion is a semantic round trip, not preservation of JSON
  whitespace, key order, omitted-null history or numeric spelling.
- Unknown fields, duplicate JSON keys, unknown/missing/incompatible tags and
  invalid scalar types raise `JSONModelError` (an `APRSError`/`ValueError`). There
  is no arbitrary class loading or fallback to a different family.
- Normal constructors and JSON imports enforce annotated types plus modeled
  domain invariants: coordinate and timestamp bounds, mandatory timestamp
  components, symbol/address syntax, message widths/IDs, weather quantity units
  and ranges, and fixed-format telemetry/NMEA constraints. Invalid normal models
  raise ModelError; JSON import presents these as JSONModelError. Codec availability
  is separate: an otherwise valid model can still raise CodecNotImplemented.
- Classic Telemetry requires a sequence (integer or MIC), five integer analog
  channels in 0..255 and eight binary channels. Other encodings retain their
  own optional sequence/missing-channel semantics. Weather measurement absence
  is meaningful; a full Packet with Weather requires an MDHM timestamp, while
  a fixed nested Weather field need not have one. Active NMEA fixes require
  coordinates. DHM needs day, HMS needs second, MDHM needs month/day.
- Encoding reconstructs from structured fields and revalidates them. Original
  wire bytes, raw evidence and redundant raw codes do not override edits or
  satisfy required fields. Explicit raw models/portions use bytes as content.
  Unsupported codecs and unspecified external grammars are not claimed valid
  merely because an input can be preserved. See [wire coverage](API_COVERAGE.md).
- `parse_packet` returns Packet or one top-level Malformed; `decode_payload`
  returns a payload or Malformed at that boundary. Malformed has original_wire,
  diagnostics with field paths, and recovered ordinary JSON data. Its recovered
  value uses the normal packet/payload schema, with missing/unreadable fields
  omitted rather than guessed. Correct and complete that data, then use
  from_json_dict to construct a normal model. Malformed is never a Packet payload
  and cannot be serialized to TNC2. Its JSON can be exported/imported for inspection.
  The recovered dictionary does not bypass normal model validation.
- `max_depth` defaults to 64 and accepts integers 1–128. Cycles and excessive
  nesting fail. This is not an input-size bound. `include_defaults` must be bool;
  `indent` is null or a nonnegative integer.

## Type map and object catalog

Tags in this table are exhaustive for standalone models. Payload tags are also
required at any nested payload boundary. Every example includes optional fields
and defaults so its complete shape is visible; null optional nested objects link
to their own fully expanded object examples in the field table.

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
        doc += (
            f'| `type` | `"{schema.tag}"` | required standalone; nested rules above |\n'
        )
        entries = [(f, schema.model) for f in dataclasses.fields(schema.model)]
        for f, owner in entries:
            doc += f"| `{f.name}` | {annotation_text(_HINTS[owner][f.name])} | {default_text(f)} |\n"
    doc += "\n## Nested union examples\n\nEach allowed member is shown in its actual container. Fixed nested fields remain untagged.\n"
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
Runtime capability metadata (`CodecCapability`) is not a JSON data model: its
Python class references belong to the codec registry, not a packet document.
"""
    return doc


if __name__ == "__main__":
    (ROOT / "docs" / "JSON_FORMAT.md").write_text(generate())
