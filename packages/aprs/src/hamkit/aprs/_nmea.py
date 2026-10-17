# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Typed values for the five NMEA sentence kinds cited by the APRS corpus.

Raw time/date/fields are retained; no host clock, checksum success or trusted
fix is inferred from coordinates. Other NMEA sentences need their own grammar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from ._data import Coordinates
from ._validation import Validated, evidence


@dataclass(frozen=True)
class NMEAMetadata(Validated):
    talker: str
    checksum_supplied: str | None = field(default=None, kw_only=True)
    checksum_valid: bool | None = field(default=None, kw_only=True)
    fields_raw: tuple[bytes, ...] = evidence(())


@dataclass(frozen=True)
class GGA(Validated):
    time_utc: str
    coordinates: Coordinates | None
    fix_quality: int
    satellites: int | None = field(default=None, kw_only=True)
    hdop: float | None = field(default=None, kw_only=True)
    altitude_msl_m: float | None = field(default=None, kw_only=True)
    geoid_separation_m: float | None = field(default=None, kw_only=True)
    dgps_age: str | None = field(default=None, kw_only=True)
    dgps_station: str | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class GLL(Validated):
    coordinates: Coordinates | None
    time_utc: str
    fix_status: Literal["A", "V"]


@dataclass(frozen=True)
class RMC(Validated):
    time_utc: str
    date_ddmmyy: str
    fix_status: Literal["A", "V"]
    coordinates: Coordinates | None
    speed_knots: float | None = field(default=None, kw_only=True)
    course_deg: float | None = field(default=None, kw_only=True)
    magnetic_variation: float | None = field(default=None, kw_only=True)
    magnetic_variation_direction: Literal["E", "W"] | None = field(
        default=None, kw_only=True
    )


@dataclass(frozen=True, kw_only=True)
class VTG(Validated):
    course_true_deg: float | None = None
    course_magnetic_deg: float | None = None
    speed_knots: float | None = None
    speed_kmh_reported: float | None = None


@dataclass(frozen=True)
class WPL(Validated):
    coordinates: Coordinates
    name: str


NMEASentence: TypeAlias = GGA | GLL | RMC | VTG | WPL
