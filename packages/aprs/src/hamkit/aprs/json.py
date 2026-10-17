# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Domain-shaped JSON for APRS models, independent of wire codec availability.

Stable semantic tags identify standalone models and polymorphic boundaries.
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


@dataclass(frozen=True)
class _Schema:
    model: type[JSONModel]
    tag: str

    def key(self, name: str) -> str:
        return name

    @property
    def allowed(self) -> set[str]:
        return {f.name for f in fields(self.model)}

    @property
    def required(self) -> set[str]:
        return {
            f.name
            for f in fields(self.model)
            if f.default is MISSING and f.default_factory is MISSING
        }


# Explicit wire-independent identifiers: renaming a Python class does not change JSON.
_SCHEMAS = (
    _Schema(d.Measurement, "measurement"),
    _Schema(d.Timestamp, "timestamp"),
    _Schema(d.Coordinates, "coordinates"),
    _Schema(d.CellBounds, "cell_bounds"),
    _Schema(d.Ambiguity, "ambiguity"),
    _Schema(d.Symbol, "symbol"),
    _Schema(d.GridLocator, "grid_locator"),
    _Schema(d.Motion, "motion"),
    _Schema(d.Altitude, "altitude"),
    _Schema(d.RadioRange, "radio_range"),
    _Schema(d.PHG, "phg"),
    _Schema(d.DFSignal, "df_signal"),
    _Schema(d.DFBearing, "df_bearing"),
    _Schema(d.Compression, "compression"),
    _Schema(d.DAO, "dao"),
    _Schema(d.Area, "area"),
    _Schema(d.Signpost, "signpost"),
    _Schema(d.WaterHeight, "water_height"),
    _Schema(d.Weather, "weather_fields"),
    _Schema(d.Storm, "storm"),
    _Schema(d.TelemetryData, "telemetry_data"),
    _Schema(d.Extensions, "extensions"),
    _Schema(d.Location, "location"),
    _Schema(d.Beam, "beam"),
    _Schema(d.ReplyAck, "reply_ack"),
    _Schema(d.TelemetryParameters, "telemetry_parameters"),
    _Schema(d.TelemetryUnits, "telemetry_units"),
    _Schema(d.Calibration, "calibration"),
    _Schema(d.TelemetryEquations, "telemetry_equations"),
    _Schema(d.TelemetryBits, "telemetry_bits"),
    _Schema(d.NTSHeader, "nts_header"),
    _Schema(d.NTSAddress, "nts_address"),
    _Schema(d.NTSPhone, "nts_phone"),
    _Schema(d.NTSText, "nts_text"),
    _Schema(d.NTSSignature, "nts_signature"),
    _Schema(d.NTSRouting, "nts_routing"),
    _Schema(d.QueryFootprint, "query_footprint"),
    _Schema(d.CapabilityToken, "capability_token"),
    _Schema(n.NMEAMetadata, "nmea_metadata"),
    _Schema(n.GGA, "gga"),
    _Schema(n.GLL, "gll"),
    _Schema(n.RMC, "rmc"),
    _Schema(n.VTG, "vtg"),
    _Schema(n.WPL, "wpl"),
    _Schema(m.DecodeOptions, "decode_options"),
    _Schema(m.EncodeOptions, "encode_options"),
    _Schema(m.PathHop, "path_hop"),
    _Schema(m.Header, "header"),
    _Schema(m.HeaderSemantics, "header_semantics"),
    _Schema(m.Position, "position"),
    _Schema(m.MicE, "mic_e"),
    _Schema(m.ObjectReport, "object"),
    _Schema(m.ItemReport, "item"),
    _Schema(m.WeatherReport, "weather"),
    _Schema(m.Telemetry, "telemetry"),
    _Schema(m.TelemetryDefinition, "telemetry_definition"),
    _Schema(m.Status, "status"),
    _Schema(m.Message, "message"),
    _Schema(m.Acknowledgment, "acknowledgment"),
    _Schema(m.AutoAnswer, "auto_answer"),
    _Schema(m.Bulletin, "bulletin"),
    _Schema(m.NWSBulletin, "nws_bulletin"),
    _Schema(m.NTSMessage, "nts_message"),
    _Schema(m.Query, "query"),
    _Schema(m.DirectStations, "direct_stations"),
    _Schema(m.HeardStation, "heard_station"),
    _Schema(m.TraceRoute, "trace_route"),
    _Schema(m.QueryResponse, "query_response"),
    _Schema(m.Capabilities, "capabilities"),
    _Schema(m.NMEAReport, "nmea"),
    _Schema(m.ThirdParty, "third_party"),
    _Schema(m.UserDefined, "user_defined"),
    _Schema(m.RawWeather, "raw_weather"),
    _Schema(m.Agrelo, "agrelo"),
    _Schema(m.MaidenheadBeacon, "maidenhead_beacon"),
    _Schema(m.LegacyPosition, "legacy_position"),
    _Schema(m.NonAPRSBeacon, "non_aprs_beacon"),
    _Schema(m.InvalidTest, "invalid_test"),
    _Schema(m.Reserved, "reserved"),
    _Schema(m.ExternalExtension, "external_extension"),
    _Schema(m.Diagnostic, "diagnostic"),
    _Schema(m.Opaque, "opaque"),
    _Schema(m.Packet, "packet"),
    _Schema(m.EncodedPacketFields, "encoded_packet_fields"),
)
_BY_MODEL = {schema.model: schema for schema in _SCHEMAS}
_BY_TAG = {schema.tag: schema.model for schema in _SCHEMAS}
_PAYLOAD_MODELS = set(get_args(m.Payload))

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


def _tagged_model(
    value: Mapping[str, object], candidates: tuple[type[JSONModel], ...], path: str
) -> type[JSONModel]:
    tag = value.get("type")
    if type(tag) is not str:
        raise JSONModelError(f"{path}.type: required semantic type string")
    model = _BY_TAG.get(tag)
    if model is None:
        raise JSONModelError(f"{path}.type: unknown type {tag!r}")
    if model not in candidates:
        raise JSONModelError(f"{path}.type: incompatible type {tag!r} for this field")
    return model


def _contextualize(value: JSONValue, annotation: Any) -> JSONValue:
    """Omit tags only where the declared field identifies exactly one model."""
    origin, args = get_origin(annotation), get_args(annotation)
    models = tuple(t for t in args if t in _BY_MODEL)
    if isinstance(value, dict):
        fixed = (
            annotation
            if annotation in _BY_MODEL
            else (models[0] if len(models) == 1 else None)
        )
        if fixed is not None and fixed not in _PAYLOAD_MODELS:
            return {k: v for k, v in value.items() if k != "type"}
    if origin is tuple and isinstance(value, list):
        variadic = len(args) == 2 and args[1] is Ellipsis
        return [
            _contextualize(item, args[0] if variadic else args[i])
            for i, item in enumerate(value)
        ]
    return value


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
            model = _tagged_model(raw, models, path) if len(models) > 1 else models[0]
            return _decode_model(raw, model, path, depth, maximum)
        successes = []
        for variant in args:
            try:
                successes.append(_decode(value, variant, path, depth, maximum))
            except JSONModelError:
                pass
        if len(successes) == 1:
            return successes[0]
        if len(successes) > 1:
            raise JSONModelError(f"{path}: multiple union members accept the value")
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
    if "type" in value or model in _PAYLOAD_MODELS:
        _tagged_model(value, (model,), path)
    value = {k: v for k, v in value.items() if k != "type"}
    if model is m.WeatherReport:
        if "weather" in value:
            raise JSONModelError(
                f"{path}.weather: use direct weather measurement fields"
            )
        weather_keys = _BY_MODEL[d.Weather].allowed
        value = {
            **{k: v for k, v in value.items() if k not in weather_keys},
            "weather": {k: v for k, v in value.items() if k in weather_keys},
        }
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
        result: JSONObject = {"type": schema.tag}
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
            if include_defaults or default is MISSING or item != default:
                if isinstance(model, m.WeatherReport) and key == "weather":
                    assert isinstance(encoded, dict)
                    result.update({k: v for k, v in encoded.items() if k != "type"})
                else:
                    result[key] = _contextualize(encoded, hints[f.name])
        return result
    finally:
        active.remove(id(value))


def to_json_dict(
    value: JSONModel, *, include_defaults: bool = False, max_depth: int = 64
) -> JSONObject:
    """Convert a supported model to a JSON object with a stable semantic type tag.

    Byte fields use Latin-1 strings. Compact output keeps required fields needed
    for construction. Validation checks model field types, not APRS wire grammar.
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
    """Read a tagged model, or an untagged fixed field with expected_type.

    Unknown/conflicting keys, missing/incompatible tags and invalid scalar types raise
    JSONModelError. expected_type supplies context for sparse standalone fields.
    """
    _check_limit(max_depth)
    raw = _object(value, "$")
    if expected_type is not None and expected_type not in _BY_MODEL:
        raise JSONModelError("expected_type must be a supported concrete APRS model")
    model = expected_type or _tagged_model(raw, tuple(_BY_MODEL), "$")
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
