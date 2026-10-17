# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Domain-shaped JSON for APRS models, independent of wire codec availability.

Field aliases and required inference fields are the schema, not class-name tags.
See docs/JSON_FORMAT.md before changing them: they are a public data contract.
"""
from __future__ import annotations

import json
import math
import types
from collections.abc import Mapping
from dataclasses import MISSING, dataclass, fields
from typing import (
    Any,
    Literal,
    TypeAlias,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from . import data as d
from . import models as m
from . import nmea as n
from .errors import APRSError

JSONValue: TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
)
JSONObject: TypeAlias = dict[str, JSONValue]
JSONModel: TypeAlias = (
    d.Measurement
    | d.Timestamp
    | d.Coordinates
    | d.CellBounds
    | d.Ambiguity
    | d.Symbol
    | d.GridLocator
    | d.Motion
    | d.Altitude
    | d.RadioRange
    | d.PHG
    | d.DFSignal
    | d.DFBearing
    | d.Compression
    | d.DAO
    | d.Area
    | d.Signpost
    | d.WaterHeight
    | d.Weather
    | d.Storm
    | d.TelemetryData
    | d.Extensions
    | d.Location
    | d.Beam
    | d.ReplyAck
    | d.TelemetryParameters
    | d.TelemetryUnits
    | d.Calibration
    | d.TelemetryEquations
    | d.TelemetryBits
    | d.NTSHeader
    | d.NTSAddress
    | d.NTSPhone
    | d.NTSText
    | d.NTSSignature
    | d.NTSRouting
    | d.QueryFootprint
    | d.CapabilityToken
    | n.NMEAMetadata
    | n.GGA
    | n.GLL
    | n.RMC
    | n.VTG
    | n.WPL
    | m.DecodeOptions
    | m.EncodeOptions
    | m.PathHop
    | m.Header
    | m.HeaderSemantics
    | m.Position
    | m.MicE
    | m.ObjectReport
    | m.ItemReport
    | m.WeatherReport
    | m.Telemetry
    | m.TelemetryDefinition
    | m.Status
    | m.Message
    | m.Acknowledgment
    | m.AutoAnswer
    | m.Bulletin
    | m.NWSBulletin
    | m.NTSMessage
    | m.Query
    | m.DirectStations
    | m.HeardStation
    | m.TraceRoute
    | m.QueryResponse
    | m.Capabilities
    | m.NMEAReport
    | m.ThirdParty
    | m.UserDefined
    | m.RawWeather
    | m.Agrelo
    | m.MaidenheadBeacon
    | m.LegacyPosition
    | m.NonAPRSBeacon
    | m.InvalidTest
    | m.Reserved
    | m.ExternalExtension
    | m.Diagnostic
    | m.Opaque
    | m.Packet
    | m.EncodedPacketFields
)

_T = TypeVar("_T", bound=JSONModel)


class JSONModelError(APRSError):
    """Malformed JSON, an unknown/conflicting shape, or invalid field types."""


class AmbiguousJSONError(JSONModelError):
    """More than one model fits; provide semantic fields or expected_type."""


@dataclass(frozen=True)
class _Schema:
    model: type[JSONModel]
    aliases: Mapping[str, str]
    anchors: tuple[str, ...] = ()

    def key(self, name: str) -> str:
        return self.aliases.get(name, name)

    @property
    def allowed(self) -> set[str]:
        return {self.key(f.name) for f in fields(self.model)}

    @property
    def required(self) -> set[str]:
        return {
            self.key(f.name)
            for f in fields(self.model)
            if f.default is MISSING and f.default_factory is MISSING
        }

    @property
    def signature(self) -> set[str]:
        return self.required | {self.key(name) for name in self.anchors}


_SCHEMAS = (
    _Schema(d.Measurement, {}, ()),
    _Schema(d.Timestamp, {"kind": "timestamp_format"}, ()),
    _Schema(d.Coordinates, {}, ()),
    _Schema(d.CellBounds, {}, ()),
    _Schema(d.Ambiguity, {"digits": "ambiguity_digits"}, ()),
    _Schema(d.Symbol, {}, ("table_id", "code")),
    _Schema(d.GridLocator, {}, ()),
    _Schema(d.Motion, {}, ("course_deg",)),
    _Schema(d.Altitude, {}, ()),
    _Schema(d.RadioRange, {}, ()),
    _Schema(d.PHG, {}, ()),
    _Schema(d.DFSignal, {}, ()),
    _Schema(d.DFBearing, {}, ()),
    _Schema(d.Compression, {}, ()),
    _Schema(d.DAO, {}, ()),
    _Schema(d.Area, {}, ()),
    _Schema(d.Signpost, {}, ()),
    _Schema(d.WaterHeight, {}, ()),
    _Schema(d.Weather, {}, ("wind_speed",)),
    _Schema(d.Storm, {"kind": "storm_category"}, ()),
    _Schema(d.TelemetryData, {}, ("analog", "digital")),
    _Schema(d.Extensions, {}, ("motion",)),
    _Schema(d.Location, {}, ("symbol",)),
    _Schema(d.Beam, {}, ()),
    _Schema(d.ReplyAck, {}, ()),
    _Schema(d.TelemetryParameters, {"channels": "channel_names"}, ()),
    _Schema(d.TelemetryUnits, {"channels": "channel_units"}, ()),
    _Schema(d.Calibration, {}, ()),
    _Schema(d.TelemetryEquations, {}, ()),
    _Schema(d.TelemetryBits, {"sense": "sense_bits"}, ()),
    _Schema(d.NTSHeader, {}, ()),
    _Schema(d.NTSAddress, {"lines": "address_lines"}, ()),
    _Schema(d.NTSPhone, {"number": "phone_number"}, ()),
    _Schema(d.NTSText, {"text": "line_text"}, ()),
    _Schema(d.NTSSignature, {"text": "signature_text"}, ()),
    _Schema(d.NTSRouting, {}, ()),
    _Schema(d.QueryFootprint, {}, ()),
    _Schema(d.CapabilityToken, {"name": "capability_name"}, ()),
    _Schema(n.NMEAMetadata, {}, ("talker",)),
    _Schema(n.GGA, {}, ()),
    _Schema(n.GLL, {}, ()),
    _Schema(n.RMC, {}, ()),
    _Schema(n.VTG, {}, ("course_true_deg",)),
    _Schema(n.WPL, {}, ()),
    _Schema(m.DecodeOptions, {}, ("unsupported",)),
    _Schema(m.EncodeOptions, {}, ("destination",)),
    _Schema(m.PathHop, {}, ()),
    _Schema(m.Header, {}, ()),
    _Schema(m.HeaderSemantics, {}, ("q_construct",)),
    _Schema(m.Position, {}, ("messaging",)),
    _Schema(m.MicE, {}, ()),
    _Schema(m.ObjectReport, {"name": "object_name"}, ()),
    _Schema(m.ItemReport, {"name": "item_name"}, ()),
    _Schema(m.WeatherReport, {}, ()),
    _Schema(m.Telemetry, {"data": "telemetry"}, ()),
    _Schema(m.TelemetryDefinition, {}, ()),
    _Schema(m.Status, {"text": "status_text"}, ("text",)),
    _Schema(m.Message, {"text": "message_text"}, ("text",)),
    _Schema(m.Acknowledgment, {"message_id": "acknowledgment_id"}, ()),
    _Schema(m.AutoAnswer, {"text": "auto_answer_text"}, ()),
    _Schema(m.Bulletin, {"identifier": "bulletin_id"}, ()),
    _Schema(m.NWSBulletin, {"text": "nws_text"}, ()),
    _Schema(m.NTSMessage, {}, ()),
    _Schema(m.Query, {"name": "query_name"}, ()),
    _Schema(m.DirectStations, {}, ()),
    _Schema(m.HeardStation, {}, ()),
    _Schema(m.TraceRoute, {}, ()),
    _Schema(m.QueryResponse, {}, ()),
    _Schema(m.Capabilities, {"tokens": "capability_tokens"}, ()),
    _Schema(m.NMEAReport, {}, ()),
    _Schema(m.ThirdParty, {"packet": "third_party_packet"}, ()),
    _Schema(m.UserDefined, {}, ()),
    _Schema(m.RawWeather, {"format": "weather_format"}, ()),
    _Schema(m.Agrelo, {}, ()),
    _Schema(m.MaidenheadBeacon, {}, ()),
    _Schema(m.LegacyPosition, {}, ()),
    _Schema(m.NonAPRSBeacon, {"text": "beacon_text"}, ()),
    _Schema(m.InvalidTest, {"data": "test_data"}, ()),
    _Schema(m.Reserved, {}, ()),
    _Schema(m.ExternalExtension, {"name": "extension_name"}, ()),
    _Schema(m.Diagnostic, {}, ()),
    _Schema(m.Opaque, {}, ()),
    _Schema(m.Packet, {}, ()),
    _Schema(m.EncodedPacketFields, {}, ()),
)
_BY_MODEL = {schema.model: schema for schema in _SCHEMAS}


_HINTS = {model: get_type_hints(model) for model in _BY_MODEL}


def _hints(model: type[JSONModel]) -> dict[str, Any]:
    return _HINTS[model]


def _limit(depth: int, maximum: int, path: str) -> None:
    if depth > maximum:
        raise JSONModelError(f"{path}: JSON nesting limit exceeded")


def _check_limit(max_depth: int) -> None:
    if type(max_depth) is not int or not 1 <= max_depth <= 128:
        raise ValueError("max_depth must be an integer in 1..128")


def _object(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(k) is not str for k in value):
        raise JSONModelError(f"{path}: expected an object with string keys")
    return value


def _infer(
    value: Mapping[str, object], candidates: tuple[type[JSONModel], ...], path: str
) -> type[JSONModel]:
    keys = set(value)
    structural = [
        s
        for model in candidates
        if (s := _BY_MODEL.get(model)) is not None and s.required <= keys <= s.allowed
    ]
    matches = [s for s in structural if s.signature <= keys]
    if len(matches) == 1:
        return matches[0].model
    if len(matches) > 1 or (not matches and len(structural) > 1):
        names = ", ".join(s.model.__name__ for s in (matches or structural))
        raise AmbiguousJSONError(
            f"{path}: ambiguous shape ({names}); supply distinguishing fields or expected_type"
        )
    if structural:
        missing = sorted(structural[0].signature - keys)
        raise JSONModelError(
            f"{path}: inference needs fields {missing}; alternatively supply expected_type"
        )
    raise JSONModelError(
        f"{path}: no model matches these fields (unknown, conflicting, or missing fields)"
    )


def _decode(value: object, annotation: Any, path: str, depth: int, maximum: int) -> Any:
    _limit(depth, maximum, path)
    if annotation is type(None):
        if value is None:
            return None
        raise JSONModelError(f"{path}: expected null")
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (Union, types.UnionType):
        models = tuple(t for t in args if t in _BY_MODEL)
        if isinstance(value, Mapping) and models:
            raw = _object(value, path)
            return _decode_model(raw, _infer(raw, models, path), path, depth, maximum)
        successes = []
        for variant in args:
            try:
                successes.append(_decode(value, variant, path, depth, maximum))
            except JSONModelError:
                pass
        if len(successes) == 1:
            return successes[0]
        if len(successes) > 1:
            raise AmbiguousJSONError(f"{path}: multiple union members accept the value")
        raise JSONModelError(f"{path}: value does not match the declared field types")
    if origin is Literal:
        if any(type(value) is type(v) and value == v for v in args):
            return value
        raise JSONModelError(f"{path}: expected one of {args!r}")
    if annotation in _BY_MODEL:
        return _decode_model(_object(value, path), annotation, path, depth, maximum)
    if origin is tuple:
        if type(value) is not list:
            raise JSONModelError(f"{path}: expected JSON array")
        variadic = len(args) == 2 and args[1] is Ellipsis
        if not variadic and len(value) != len(args):
            raise JSONModelError(f"{path}: expected array length {len(args)}")
        return tuple(
            _decode(
                item,
                args[0] if variadic else args[i],
                f"{path}[{i}]",
                depth + 1,
                maximum,
            )
            for i, item in enumerate(value)
        )
    if annotation is bytes:
        if type(value) is not str:
            raise JSONModelError(f"{path}: byte fields require Latin-1 JSON strings")
        try:
            return value.encode("latin-1")
        except UnicodeEncodeError as exc:
            raise JSONModelError(
                f"{path}: byte string contains a code point above U+00FF"
            ) from exc
    if annotation is float:
        if type(value) not in (float, int):
            raise JSONModelError(f"{path}: expected a finite number")
        try:
            result = float(cast(float | int, value))
        except (OverflowError, ValueError) as exc:
            raise JSONModelError(
                f"{path}: number is outside floating-point range"
            ) from exc
        if not math.isfinite(result):
            raise JSONModelError(
                f"{path}: non-finite numbers are not JSON model values"
            )
        return result
    if annotation in (str, int, bool) and type(value) is annotation:
        return value
    raise JSONModelError(f"{path}: expected {annotation!r}")


def _decode_model(
    value: Mapping[str, object],
    model: type[JSONModel],
    path: str,
    depth: int,
    maximum: int,
) -> JSONModel:
    _limit(depth, maximum, path)
    schema = _BY_MODEL[model]
    extra, missing = set(value) - schema.allowed, schema.required - set(value)
    if extra or missing:
        raise JSONModelError(
            f"{path}: unexpected fields {sorted(extra)}; missing fields {sorted(missing)}"
        )
    hints = _hints(model)
    kwargs = {
        f.name: _decode(
            value[schema.key(f.name)],
            hints[f.name],
            path + "." + schema.key(f.name),
            depth + 1,
            maximum,
        )
        for f in fields(model)
        if schema.key(f.name) in value
    }
    return model(**kwargs)


def _python_matches(value: object, annotation: Any) -> bool:
    """Check Python-side types before bytes/tuples lose their identity in JSON."""
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (Union, types.UnionType):
        return any(_python_matches(value, variant) for variant in args)
    if origin is Literal:
        return any(type(value) is type(v) and value == v for v in args)
    if origin is tuple:
        if type(value) is not tuple:
            return False
        variadic = len(args) == 2 and args[1] is Ellipsis
        return (variadic or len(value) == len(args)) and all(
            _python_matches(item, args[0] if variadic else args[i])
            for i, item in enumerate(value)
        )
    if annotation is float:
        return type(value) in (float, int)
    return type(value) is annotation


def _encode(
    value: object,
    include_defaults: bool,
    path: str,
    depth: int,
    maximum: int,
    active: set[int],
) -> JSONValue:
    _limit(depth, maximum, path)
    if value is None or type(value) in (str, bool, int):
        return cast(JSONValue, value)
    if type(value) is float:
        if not math.isfinite(value):
            raise JSONModelError(f"{path}: non-finite number")
        return value
    if type(value) is bytes:
        return value.decode("latin-1")
    if type(value) is tuple:
        return [
            _encode(item, include_defaults, f"{path}[{i}]", depth + 1, maximum, active)
            for i, item in enumerate(value)
        ]
    if type(value) not in _BY_MODEL:
        raise JSONModelError(f"{path}: unsupported value {type(value).__name__}")
    if id(value) in active:
        raise JSONModelError(f"{path}: cyclic model graph")
    active.add(id(value))
    try:
        model = cast(JSONModel, value)
        schema = _BY_MODEL[type(model)]
        result: JSONObject = {}
        # Validate ALL fields, even ones omitted from compact output. Never let
        # Python's True == 1 or a default comparison hide an invalid field type.
        hints = _hints(type(model))
        for f in fields(model):
            key, item = schema.key(f.name), getattr(model, f.name)
            if not _python_matches(item, hints[f.name]):
                raise JSONModelError(
                    f"{path}.{key}: invalid Python field type for {hints[f.name]!r}"
                )
            encoded = _encode(
                item, include_defaults, path + "." + key, depth + 1, maximum, active
            )
            _decode(encoded, hints[f.name], path + "." + key, depth + 1, maximum)
            default = f.default
            if f.default_factory is not MISSING:
                default = f.default_factory()
            if (
                include_defaults
                or key in schema.signature
                or default is MISSING
                or item != default
            ):
                result[key] = encoded
        return result
    finally:
        active.remove(id(value))


def to_json_dict(
    value: JSONModel, *, include_defaults: bool = False, max_depth: int = 64
) -> JSONObject:
    """Convert a supported model to a domain-shaped JSON object, with no type tag.

    Byte fields use Latin-1 strings. Compact output keeps semantic fields needed
    for inference. Validation checks model field types, not APRS wire grammar.
    """
    _check_limit(max_depth)
    if type(include_defaults) is not bool:
        raise ValueError("include_defaults must be bool")
    if type(value) not in _BY_MODEL:
        raise JSONModelError("expected a supported APRS packet, payload or field model")
    result = _encode(value, include_defaults, "$", 0, max_depth, set())
    assert isinstance(result, dict)
    return result


@overload
def from_json_dict(
    value: Mapping[str, object], *, expected_type: type[_T], max_depth: int = 64
) -> _T:
    ...


@overload
def from_json_dict(
    value: Mapping[str, object], *, expected_type: None = None, max_depth: int = 64
) -> JSONModel:
    ...


def from_json_dict(
    value: Mapping[str, object],
    *,
    expected_type: type[Any] | None = None,
    max_depth: int = 64,
) -> JSONModel:
    """Infer a model from semantic fields, or check an explicitly expected model.

    Unknown/conflicting keys, ambiguous shapes and invalid scalar types raise
    JSONModelError. expected_type supplies context for sparse standalone fields.
    """
    _check_limit(max_depth)
    raw = _object(value, "$")
    if expected_type is not None and expected_type not in _BY_MODEL:
        raise JSONModelError("expected_type must be a supported concrete APRS model")
    model = expected_type or _infer(raw, tuple(_BY_MODEL), "$")
    return _decode_model(raw, model, "$", 0, max_depth)


def to_json(
    value: JSONModel,
    *,
    indent: int | None = None,
    include_defaults: bool = False,
    max_depth: int = 64,
) -> str:
    """Serialize a model to JSON text. Non-ASCII bytes are escaped, never UTF-8 encoded."""
    if indent is not None and (type(indent) is not int or indent < 0):
        raise ValueError("indent must be a nonnegative integer or None")
    value_dict = to_json_dict(
        value, include_defaults=include_defaults, max_depth=max_depth
    )
    try:
        return json.dumps(
            value_dict,
            ensure_ascii=True,
            allow_nan=False,
            indent=indent,
            separators=(",", ":") if indent is None else None,
        )
    except (ValueError, RecursionError) as exc:
        raise JSONModelError(f"model cannot be encoded as JSON: {exc}") from exc


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise JSONModelError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise JSONModelError(f"non-standard JSON number: {value}")


@overload
def from_json(text: str, *, expected_type: type[_T], max_depth: int = 64) -> _T:
    ...


@overload
def from_json(
    text: str, *, expected_type: None = None, max_depth: int = 64
) -> JSONModel:
    ...


def from_json(
    text: str, *, expected_type: type[Any] | None = None, max_depth: int = 64
) -> JSONModel:
    """Deserialize strict JSON text, rejecting duplicate keys and NaN/Infinity."""
    _check_limit(max_depth)
    if type(text) is not str:
        raise JSONModelError("JSON text must be str")
    try:
        raw = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
        return from_json_dict(raw, expected_type=expected_type, max_depth=max_depth)
    except JSONModelError:
        raise
    except (ValueError, RecursionError) as exc:
        raise JSONModelError(f"invalid or excessively nested JSON: {exc}") from exc
