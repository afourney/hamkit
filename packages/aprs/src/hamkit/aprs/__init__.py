# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Dependency-free APRS packet parsing and composition foundation."""

from .codec import (
    decode_payload,
    encode_payload,
    parse_packet,
    serialize_packet,
    validate_packet,
)
from .errors import APRSError, EnvelopeError, FieldError, UnsupportedFormat
from .models import (
    Acknowledgment,
    CoordinateAxis,
    Header,
    Message,
    Opaque,
    Packet,
    Path,
    PathHop,
    Payload,
    Position,
    Status,
    Symbol,
    Timestamp,
    TimestampKind,
    ValidationProfile,
    WireInput,
)
from .validation import validate_header

__all__ = [
    "APRSError",
    "Acknowledgment",
    "CoordinateAxis",
    "EnvelopeError",
    "FieldError",
    "Header",
    "Message",
    "Opaque",
    "Packet",
    "Path",
    "PathHop",
    "Payload",
    "Position",
    "Status",
    "Symbol",
    "Timestamp",
    "TimestampKind",
    "UnsupportedFormat",
    "ValidationProfile",
    "WireInput",
    "decode_payload",
    "encode_payload",
    "parse_packet",
    "serialize_packet",
    "validate_header",
    "validate_packet",
]
