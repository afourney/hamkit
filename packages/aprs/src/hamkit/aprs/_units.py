# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Physical height conversion, before each format's own quantization."""
import math

from ._data import Measurement
from ._errors import FieldError


def height(reading: Measurement, unit: str) -> float:
    if reading.value is None or reading.unit not in ("feet", "meters"):
        raise FieldError("height requires a known measurement in feet or meters")
    if reading.unit == unit:
        return reading.value
    converted = reading.value * 0.3048 if unit == "meters" else reading.value / 0.3048
    if not math.isfinite(converted):
        raise FieldError("height conversion exceeds the numeric range")
    return converted
