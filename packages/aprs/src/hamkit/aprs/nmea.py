# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Typed values for the five NMEA sentence kinds cited by the APRS corpus.

Raw time/date/fields are retained; no host clock, checksum success or trusted
fix is inferred from coordinates. Other NMEA sentences need their own grammar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .data import Coordinates, RawFields


@dataclass(frozen=True)
class NMEAMetadata:
    talker: str = "GP"
    checksum_supplied: str | None = None
    checksum_valid: bool | None = None
    fields_raw: RawFields = ()


@dataclass(frozen=True)
class GGA:
    time_utc: bytes
    coordinates: Coordinates | None
    fix_quality: int
    satellites: int | None = None
    hdop: float | None = None
    altitude_msl_m: float | None = None
    geoid_separation_m: float | None = None
    dgps_age: bytes | None = None
    dgps_station: bytes | None = None


@dataclass(frozen=True)
class GLL:
    coordinates: Coordinates | None
    time_utc: bytes
    fix_status: Literal["A", "V"]


@dataclass(frozen=True)
class RMC:
    time_utc: bytes
    date_ddmmyy: bytes
    fix_status: Literal["A", "V"]
    coordinates: Coordinates | None
    speed_knots: float | None = None
    course_deg: float | None = None
    magnetic_variation: float | None = None
    magnetic_variation_direction: Literal["E", "W"] | None = None


@dataclass(frozen=True)
class VTG:
    course_true_deg: float | None = None
    course_magnetic_deg: float | None = None
    speed_knots: float | None = None
    speed_kmh_reported: float | None = None


@dataclass(frozen=True)
class WPL:
    coordinates: Coordinates
    name: bytes


NMEASentence: TypeAlias = GGA | GLL | RMC | VTG | WPL
