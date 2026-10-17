# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""DAO quantization shared by header, position, extension and send validation."""
from __future__ import annotations

import math

from ._data import DAO
from ._errors import FieldError


def split(value: float, encoding: str) -> tuple[float, int]:
    """Round the refined position first, carrying into the hundredth-minute cell."""
    scale = 10 if encoding == "decimal" else 91
    total = round(abs(value) * 6000 * scale)
    coarse, code = divmod(total, scale)
    return math.copysign(coarse / 6000, value), code


def base_coordinates(p) -> tuple[float, float]:
    dao = p.extensions.dao
    if dao is None or dao.encoding is None:
        return p.latitude_deg, p.longitude_deg
    if p.ambiguity:
        raise FieldError("DAO added precision is incompatible with position ambiguity")
    if getattr(p, "compression", None) is not None:
        raise FieldError(
            "DAO added precision requires an uncompressed or Mic-E position"
        )
    return (
        split(p.latitude_deg, dao.encoding)[0],
        split(p.longitude_deg, dao.encoding)[0],
    )


def encode(dao: DAO, coordinates: tuple[float, float] | None) -> bytes:
    if dao.encoding is None:
        return b"!" + dao.datum.encode() + b"  !"
    if coordinates is None:
        raise FieldError("DAO precision encoding requires semantic coordinates")
    bias = 48 if dao.encoding == "decimal" else 33
    pair = bytes(split(v, dao.encoding)[1] + bias for v in coordinates)
    datum = dao.datum if dao.encoding == "decimal" else dao.datum.lower()
    return b"!" + datum.encode() + pair + b"!"
