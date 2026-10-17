# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Explicit line framing, separate from binary-safe packet codecs."""

from .codec import parse_packet, serialize_packet
from .errors import EnvelopeError
from .models import DecodeOptions, EncodeOptions, Malformed, Packet, ValidationProfile

_DEFAULT_DECODE = DecodeOptions()
_DEFAULT_ENCODE = EncodeOptions()


def parse_tnc2_line(
    line: bytes,
    *,
    profile: ValidationProfile = "monitor",
    options: DecodeOptions = _DEFAULT_DECODE,
) -> Packet | Malformed:
    """Require one LF or CRLF terminator and reject embedded line delimiters.

    original_wire on the result excludes the transport terminator.
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
    return parse_packet(raw, profile=profile, options=options)


def serialize_tnc2_line(
    packet: Packet,
    *,
    profile: ValidationProfile = "monitor",
    options: EncodeOptions = _DEFAULT_ENCODE,
) -> bytes:
    """Encode one CRLF-terminated line, rejecting non-line-safe payloads."""
    raw = serialize_packet(packet, profile=profile, options=options)
    if b"\r" in raw or b"\n" in raw:
        raise EnvelopeError("payload cannot be represented in line-oriented TNC2")
    return raw + b"\r\n"
