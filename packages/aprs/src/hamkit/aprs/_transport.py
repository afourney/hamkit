# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Explicit line framing, separate from binary-safe packet codecs."""

from ._codec import parse_packet, serialize_packet
from ._errors import EnvelopeError
from ._models import (
    Malformed,
    MalformedPolicy,
    Packet,
    UnsupportedPolicy,
)
from ._policy import APRS_IS, EnvelopePolicy


def parse_tnc2_line(
    line: bytes,
    *,
    policy: EnvelopePolicy = APRS_IS,
    unsupported: UnsupportedPolicy = "opaque",
    malformed: MalformedPolicy = "return",
    max_third_party_depth: int = 4,
    legacy_positions: bool = False,
) -> Packet | Malformed:
    """Parse one LF- or CRLF-terminated line, as read from APRS-IS or a TNC.

    Embedded line delimiters are rejected. original_wire excludes the terminator.
    """
    if not isinstance(line, bytes):
        raise TypeError("line must be bytes")
    if line.endswith(b"\r\n"):
        raw = line[:-2]
    elif line.endswith(b"\n"):
        raw = line[:-1]
    else:
        raise EnvelopeError("TNC2 line needs LF or CRLF terminator")
    if b"\r" in raw or b"\n" in raw:
        raise EnvelopeError(
            "embedded line delimiter; use unframed parse_packet for binary data"
        )
    return parse_packet(
        raw,
        policy=policy,
        unsupported=unsupported,
        malformed=malformed,
        max_third_party_depth=max_third_party_depth,
        legacy_positions=legacy_positions,
    )


def serialize_tnc2_line(
    packet: Packet,
    *,
    policy: EnvelopePolicy = APRS_IS,
    max_third_party_depth: int = 4,
) -> bytes:
    """Encode one CRLF-terminated line, rejecting non-line-safe payloads."""
    raw = serialize_packet(
        packet, policy=policy, max_third_party_depth=max_third_party_depth
    )
    if b"\r" in raw or b"\n" in raw:
        raise EnvelopeError("payload cannot be represented in line-oriented TNC2")
    return raw + b"\r\n"
