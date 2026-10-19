# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Compare decoded values by meaning, ignoring received wire evidence."""

from __future__ import annotations

import dataclasses
import math
from typing import Any


def without_evidence(value: Any) -> Any:
    """Clear received raw evidence (hidden fields); wire metadata stays visible."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.replace(
            value,
            **{
                f.name: without_evidence(getattr(value, f.name))
                if f.repr
                else f.default
                for f in dataclasses.fields(value)
            },
        )
    if isinstance(value, tuple):
        return tuple(without_evidence(v) for v in value)
    return value


def same_semantics(x: Any, y: Any, path="$") -> None:
    assert (
        type(x) is type(y)
        or isinstance(x, (int, float))
        and isinstance(y, (int, float))
    ), path
    if dataclasses.is_dataclass(x):
        for f in dataclasses.fields(x):
            if f.compare:
                same_semantics(
                    getattr(x, f.name), getattr(y, f.name), path + "." + f.name
                )
    elif isinstance(x, tuple):
        assert len(x) == len(y), path
        for i, (v, w) in enumerate(zip(x, y)):
            same_semantics(v, w, f"{path}[{i}]")
    elif isinstance(x, (float, int)) and not isinstance(x, bool):
        if path.endswith((".wind_direction.value", ".course_deg")) and {x, y} == {
            0,
            360,
        }:
            return  # Both are north; north is sent as 360 (APRS101 p27).
        assert math.isclose(x, y, abs_tol=1e-8, rel_tol=1e-9), (path, x, y)
        if x == y == 0:
            assert math.copysign(1, x) == math.copysign(1, y), (
                path,
                "hemisphere changed",
            )
    else:
        assert x == y, (path, x, y)
