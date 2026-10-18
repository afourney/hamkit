# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Typed values for the five NMEA sentence kinds cited by the APRS corpus.

Partial UTC times and century-less dates remain structured. No host clock,
century or trusted fix is inferred. Other sentences need their own grammar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias, get_args

from ._data import Coordinates, Measurement
from ._validation import Validated, evidence


@dataclass(frozen=True)
class NMEAMetadata(Validated):
    talker: str
    checksum_supplied: str | None = field(default=None, kw_only=True)
    checksum_valid: bool | None = field(default=None, kw_only=True)
    fields_raw: tuple[bytes, ...] = evidence(())


@dataclass(frozen=True)
class UTCTime(Validated):
    """UTC clock components, without a date; None second means unknown, not zero."""

    hour: int
    minute: int
    second: float | None = None


@dataclass(frozen=True)
class NMEADate(Validated):
    """Calendar components with an unresolved century (00..99, never a full year)."""

    day: int | None = None
    month: int | None = None
    year_mod_100: int | None = None


# NMEA 0183 GGA fix quality indicator, in code order (0-8).
GGAFixQuality: TypeAlias = Literal[
    "invalid",
    "gps",
    "dgps",
    "pps",
    "rtk",
    "float_rtk",
    "estimated",
    "manual",
    "simulation",
]
GGA_FIX_QUALITIES: tuple[GGAFixQuality, ...] = get_args(GGAFixQuality)
# GLL/RMC status: A (active, valid) or V (void).
FixStatus: TypeAlias = Literal["active", "void"]


@dataclass(frozen=True)
class GGA(Validated):
    time_utc: UTCTime | None
    coordinates: Coordinates | None
    fix_quality: GGAFixQuality
    satellites: int | None = field(default=None, kw_only=True)
    hdop: float | None = field(default=None, kw_only=True)
    altitude_msl: Measurement | None = field(default=None, kw_only=True)
    geoid_separation: Measurement | None = field(default=None, kw_only=True)
    dgps_age: str | None = field(default=None, kw_only=True)
    dgps_station: str | None = field(default=None, kw_only=True)


@dataclass(frozen=True)
class GLL(Validated):
    coordinates: Coordinates | None
    time_utc: UTCTime | None
    fix_status: FixStatus


@dataclass(frozen=True)
class RMC(Validated):
    time_utc: UTCTime | None
    date: NMEADate | None
    fix_status: FixStatus
    coordinates: Coordinates | None
    speed_knots: float | None = field(default=None, kw_only=True)
    course_deg: float | None = field(default=None, kw_only=True)
    # Signed degrees: east is positive, west negative.
    magnetic_variation_deg: float | None = field(default=None, kw_only=True)


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
