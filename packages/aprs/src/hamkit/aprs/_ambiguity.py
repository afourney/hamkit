# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Shared APRS ambiguity cells for derived geometry and wire encoding."""
from __future__ import annotations

import math
from decimal import Decimal

from ._errors import FieldError

# Cell widths in hundredths of minutes, indexed by hidden minute digits.
_WIDTHS = (10, 100, 1000, 6000)


def _cell(value: float, digits: int) -> tuple[int, int]:
    width = _WIDTHS[digits - 1]
    # Select from semantic decimal degrees before rounding, without an epsilon
    # that could move the float immediately below a boundary into its neighbor.
    index = int(Decimal(str(abs(value))) * 6000 // width)
    return index * width, width


def axis_extent(value: float, digits: int, limit: int) -> tuple[float, float]:
    low, width = _cell(value, digits)
    high = low + width
    if high > limit * 6000:
        raise FieldError("ambiguity cell exceeds coordinate bounds")
    bounds = low / 6000, high / 6000
    if math.copysign(1, value) < 0:
        return -bounds[1], -bounds[0]
    return bounds


def center(value: float, digits: int) -> float:
    if not digits:
        return value
    low, width = _cell(value, digits)
    return math.copysign((low + width / 2) / 6000, value)


def center_wire(value: float, digits: int) -> float:
    """Center decoded hundredth-minute values after recovering their integer units."""
    if not digits:
        return value
    width = _WIDTHS[digits - 1]
    units = round(abs(value) * 6000)
    return math.copysign((units // width + 0.5) * width / 6000, value)
