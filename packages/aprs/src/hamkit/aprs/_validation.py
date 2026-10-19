# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Constructor invariants: values that cannot exist on the wire or contradict.

Constructors validate their own fields once. Nested models were validated when
they were built, so construction is shallow. Serialization and JSON export call
validate_tree, which re-checks the whole graph defensively. APRS limits that a
transmitter could still violate (lengths, required slots, symbol choices) are
conformance rules instead; see _conformance.py.
"""
from __future__ import annotations

import math
import types
from collections.abc import Callable, Iterator
from dataclasses import Field, field, fields, is_dataclass
from functools import cache
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

from ._errors import ModelError

# Field metadata naming a str field's character policy. Unmarked str fields are
# protocol tokens (printable ASCII). Free text may hold any Unicode, sent as
# UTF-8 per the adopted APRS 1.2 draft guidance; control characters are a
# conformance matter.
FREE_TEXT = {"text": "free"}
ANY_TEXT = {"text": "any"}


def evidence(default: Any = None) -> Any:
    """Raw received evidence: kept and serialized, but ignored by equality."""
    return field(default=default, compare=False, repr=False, kw_only=True)


_LIBRARY: set[type] = set()


class Validated:
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.__module__.startswith("hamkit.aprs."):
            _LIBRARY.add(cls)

    def __post_init__(self) -> None:
        validate_node(self)


class _Deep:
    """Traversal state for validate_tree: cycle detection and a depth budget."""

    def __init__(self, limit: int):
        self.limit = limit
        self.depth = 0
        self.active: set[int] = set()


_Rule = Callable[[Any], None]
_RULES: dict[type, list[_Rule]] = {}


def invariant(*classes: type) -> Callable[[_Rule], _Rule]:
    """Register a constructor rule; it applies to subclasses as well."""

    def register(rule: _Rule) -> _Rule:
        for cls in classes:
            _RULES.setdefault(cls, []).append(rule)
        _RULE_CACHE.clear()
        return rule

    return register


_RULE_CACHE: dict[type, tuple[_Rule, ...]] = {}


def _rules_for(model: type) -> tuple[_Rule, ...]:
    rules = _RULE_CACHE.get(model)
    if rules is None:
        rules = tuple(rule for cls in model.__mro__ for rule in _RULES.get(cls, ()))
        _RULE_CACHE[model] = rules
    return rules


def fail(field_name: str, message: str) -> None:
    """Raise from inside a rule, relative to the model being validated."""
    raise ModelError(f"$.{field_name}", message)


@cache
def hints(model: type[Any]) -> dict[str, Any]:
    return get_type_hints(model)


_FIELD_CACHE: dict[type, tuple[Field[Any], ...]] = {}


def _fields(model: type) -> tuple[Field[Any], ...]:
    result = _FIELD_CACHE.get(model)
    if result is None:
        result = _FIELD_CACHE[model] = fields(model)
    return result


def json_data(value: object, path: str = "$", depth: int = 0, limit: int = 64) -> None:
    if depth > limit:
        raise ModelError(path, "JSON nesting limit exceeded")
    if value is None or type(value) in (bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is str and not _has_surrogate(value):
        return
    if type(value) is list:
        for i, child in enumerate(value):
            json_data(child, f"{path}[{i}]", depth + 1, limit)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for key, child in value.items():
            if _has_surrogate(key):
                raise ModelError(path, "JSON keys cannot contain surrogates")
            json_data(child, f"{path}.{key}", depth + 1, limit)
        return
    raise ModelError(path, "expected finite, surrogate-free JSON data")


def _has_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(c) <= 0xDFFF for c in value)


def _check_text(value: str, policy: str, path: str) -> None:
    if _has_surrogate(value):
        raise ModelError(path, "text cannot contain surrogate code points")
    if policy == "token" and any(not 32 <= ord(c) <= 126 for c in value):
        raise ModelError(path, "protocol token must be printable ASCII")


def _check(
    value: Any, annotation: Any, path: str, policy: str, deep: _Deep | None
) -> None:
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (Union, types.UnionType):
        # A model instance is checked against its own variant, so specific
        # errors (nesting limits, subclasses) are not hidden by the union.
        for variant in args:
            if (
                isinstance(variant, type)
                and issubclass(variant, Validated)
                and isinstance(value, variant)
            ):
                _check(value, variant, path, policy, deep)
                return
        for variant in args:
            try:
                _check(value, variant, path, policy, deep)
                return
            except ModelError:
                pass
        raise ModelError(path, "value does not match the declared field type")
    if origin is Literal:
        if any(type(value) is type(v) and value == v for v in args):
            return
    elif origin is tuple and type(value) is tuple:
        repeated = len(args) == 2 and args[1] is Ellipsis
        if repeated or len(value) == len(args):
            for i, child in enumerate(value):
                item = args[0] if repeated else args[i]
                _check(child, item, f"{path}[{i}]", policy, deep)
            return
    elif origin is dict and type(value) is dict:
        json_data(value, path)
        return
    elif annotation is float and type(value) in (float, int):
        try:
            if math.isfinite(value):
                return
        except OverflowError:
            pass
    elif isinstance(annotation, type) and issubclass(annotation, Validated):
        if isinstance(value, annotation):
            if deep is not None:
                validate_tree(value, path, _deep=deep)
            return
    elif type(value) is annotation:
        if type(value) is str:
            _check_text(value, policy, path)
        return
    raise ModelError(path, f"invalid value for {annotation!r}")


def validate_node(value: Any, path: str = "$", deep: _Deep | None = None) -> None:
    if not isinstance(value, Validated) or not is_dataclass(value):
        raise ModelError(path, "expected a validated APRS model")
    model = type(value)
    annotations = hints(model)
    for f in _fields(model):
        _check(
            getattr(value, f.name),
            annotations[f.name],
            f"{path}.{f.name}",
            f.metadata.get("text", "token"),
            deep,
        )
    for rule in _rules_for(model):
        try:
            rule(value)
        except ModelError as exc:
            if path == "$":
                raise
            raise ModelError(path + exc.path[1:], exc.message) from exc


def validate_tree(
    value: Any, path: str = "$", *, limit: int = 128, _deep: _Deep | None = None
) -> None:
    """Re-validate a whole model graph, e.g. after a frozen-dataclass bypass.

    Subclasses of the public models are rejected here, so wire serialization
    and JSON export accept exactly the same values.
    """
    deep = _Deep(limit) if _deep is None else _deep
    if deep.depth >= deep.limit:
        raise ModelError(path, "model nesting limit exceeded")
    if isinstance(value, Validated) and type(value) not in _LIBRARY:
        raise ModelError(path, "subclasses of APRS models are not supported")
    if id(value) in deep.active:
        raise ModelError(path, "cyclic model graph")
    deep.active.add(id(value))
    deep.depth += 1
    try:
        validate_node(value, path, deep)
    finally:
        deep.depth -= 1
        deep.active.remove(id(value))


def walk(value: object, path: str = "$") -> Iterator[tuple[object, str]]:
    """Yield every model in a validated graph with its JSON-style path."""
    yield value, path
    for f in _fields(type(value)):
        child = getattr(value, f.name)
        children = child if type(child) is tuple else (child,)
        for i, item in enumerate(children):
            if isinstance(item, Validated):
                suffix = f"[{i}]" if type(child) is tuple else ""
                yield from walk(item, f"{path}.{f.name}{suffix}")
