# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Immutable public values. Validation occurs at codec/validation boundaries."""

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

WireInput: TypeAlias = bytes | str
ValidationProfile: TypeAlias = Literal["monitor", "rf"]
TimestampKind: TypeAlias = Literal["dhm_utc", "dhm_local", "hms_utc"]
CoordinateAxis: TypeAlias = Literal["latitude", "longitude"]


@dataclass(frozen=True)
class PathHop:
    address: str
    repeated: bool = False


Path: TypeAlias = tuple[PathHop, ...]


@dataclass(frozen=True)
class Header:
    source: str
    destination: str
    path: Path = ()


@dataclass(frozen=True)
class Timestamp:
    """Transmitted components only; no inferred date, year or local offset."""

    kind: TimestampKind
    hour: int
    minute: int
    day: int | None = None
    second: int | None = None


@dataclass(frozen=True)
class Symbol:
    table_id: str = "/"
    code: str = "-"


@dataclass(frozen=True)
class Position:
    """Uncompressed, unambiguous coordinates in signed WGS-84 degrees.

    Encoding quantizes to hundredths of minutes. The tail is uninterpreted:
    it can contain extensions, weather and comments, not just human text.
    """

    latitude_deg: float
    longitude_deg: float
    symbol: Symbol = Symbol()
    messaging: bool = False
    timestamp: Timestamp | None = None
    tail: bytes = b""

    @property
    def is_null_position(self) -> bool:
        """APRS unknown-position convention, not every numeric (0, 0)."""
        return (
            self.latitude_deg == 0
            and self.longitude_deg == 0
            and self.symbol == Symbol("\\", ".")
        )


@dataclass(frozen=True)
class Status:
    """Status body; grid/beam extensions within text remain uninterpreted."""

    text: bytes = b""
    timestamp: Timestamp | None = None


@dataclass(frozen=True)
class Message:
    """Basic message container; no station state or delivery policy implied."""

    addressee: str
    text: bytes = b""
    message_id: str | None = None

    @property
    def addressee_raw(self) -> str:
        return self.addressee.ljust(9)


@dataclass(frozen=True)
class Acknowledgment:
    addressee: str
    message_id: str
    rejected: bool = False


@dataclass(frozen=True)
class Opaque:
    """Entire information field, including DTI, retained without interpretation."""

    information: bytes
    reason: str = field(default="unsupported data type", compare=False)


Payload: TypeAlias = Position | Status | Message | Acknowledgment | Opaque


@dataclass(frozen=True)
class Packet:
    header: Header
    payload: Payload
    # Archival evidence only. Serialization always uses current structured fields.
    original_wire: bytes | None = field(default=None, compare=False, repr=False)
