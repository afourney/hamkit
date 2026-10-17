# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""NMEA semantic invariants independent of receiver-specific wire profiles.

Clock/date presence for void fixes remains governed by the current model;
this validator does not claim that all NMEA versions require populated fields.
VTG speed agreement is not inferred: the model lacks the received precisions
needed to compare independently rounded knot and kilometre/hour fields.
"""
from __future__ import annotations

import calendar
import re
from typing import Any

from .model_validation import ModelError


def validate_nmea(v: Any, path: str) -> None:
    """Reject contradictions in NMEA values after generic type validation."""
    name = type(v).__name__

    def fail(field: str, message: str) -> None:
        raise ModelError(f"{path}.{field}", message)

    def token(field: str) -> None:
        value = getattr(v, field)
        if value is not None and any(c in value for c in ",*$"):
            fail(field, "NMEA field cannot contain sentence delimiters")

    if name == "NMEAMetadata":
        if not re.fullmatch(r"[A-Z]{2}", v.talker):
            fail("talker", "requires two uppercase ASCII letters")
        if v.checksum_valid is not None and v.checksum_supplied is None:
            fail("checksum_valid", "checksum validity requires a supplied checksum")
    elif name == "GGA":
        if v.dgps_age is not None and not re.fullmatch(
            r"[0-9]+(?:\.[0-9]+)?", v.dgps_age
        ):
            fail("dgps_age", "requires a nonnegative decimal duration in seconds")
        token("dgps_station")
    elif name == "RMC":
        # The generic validator checks DDMMYY syntax first. Year 00 permits
        # February 29 without inventing which century the sender intended.
        date = v.date_ddmmyy
        day, month, year = int(date[:2]), int(date[2:4]), int(date[4:])
        if day > calendar.monthrange(2000 + year, month)[1]:
            fail("date_ddmmyy", "day does not exist in the supplied month/year")
        if v.magnetic_variation is not None and not 0 <= v.magnetic_variation <= 180:
            fail("magnetic_variation", "magnitude must be in 0..180 degrees")
        if (v.magnetic_variation is None) != (v.magnetic_variation_direction is None):
            fail(
                "magnetic_variation_direction",
                "magnetic variation magnitude and direction must occur together",
            )
    elif name == "WPL":
        token("name")
    elif name == "NMEA" and v.position_usable is True:
        sentence = v.sentence
        kind = type(sentence).__name__
        if getattr(sentence, "coordinates", None) is None:
            fail("position_usable", "usable position requires coordinates")
        if (kind in ("GLL", "RMC") and sentence.fix_status == "V") or (
            kind == "GGA" and sentence.fix_quality == 0
        ):
            fail("position_usable", "cannot mark an invalid fix as usable")
        if v.metadata.checksum_valid is False:
            fail("position_usable", "cannot mark a failed-checksum report as usable")
