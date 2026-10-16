# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Pure TNC2 parsing/composition; no AX.25, KISS, networking or radio I/O."""

import re

from .errors import EnvelopeError, FieldError, UnsupportedFormat
from .fields import (
    decode_coordinate,
    decode_timestamp,
    encode_coordinate,
    encode_timestamp,
)
from .models import (
    Acknowledgment,
    Header,
    Message,
    Opaque,
    Packet,
    PathHop,
    Payload,
    Position,
    Status,
    Symbol,
    ValidationProfile,
    WireInput,
)
from .validation import validate_header


def _wire(value: WireInput) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        try:
            return value.encode("latin-1")
        except UnicodeEncodeError as exc:
            raise EnvelopeError("text input must be a Latin-1 byte carrier") from exc
    raise TypeError("wire input must be bytes or str")


def _information(raw: bytes) -> None:
    if not isinstance(raw, bytes):
        raise TypeError("information and text fields must be bytes")
    if not raw or any(c in raw for c in (b"\r", b"\n")):
        raise EnvelopeError("information must be nonempty and contain no CR/LF framing")


def _symbol(symbol: Symbol) -> bytes:
    if (
        len(symbol.table_id) != 1
        or symbol.table_id not in "/\\0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ):
        raise FieldError("invalid uncompressed symbol table/overlay")
    if len(symbol.code) != 1 or not 33 <= ord(symbol.code) <= 126:
        raise FieldError("invalid symbol code")
    return (symbol.table_id + symbol.code).encode("ascii")


def _addressee(value: str) -> bytes:
    if (
        not 1 <= len(value) <= 9
        or value != value.rstrip(" ")
        or any(not 32 <= ord(c) <= 126 or c == ":" for c in value)
    ):
        raise FieldError(
            "addressee requires 1..9 printable characters without trailing padding or colon"
        )
    return value.ljust(9).encode("ascii")


def _message_id(value: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9]{1,5}", value):
        raise FieldError("message ID requires 1..5 alphanumeric characters")
    return value.encode("ascii")


def _special_message(address: str, body: bytes) -> bool:
    return (
        address.startswith(("BLN", "NWS-"))
        or body.startswith(
            (
                b"PARM.",
                b"UNIT.",
                b"EQNS.",
                b"BITS.",
                b"?",
                b"AA:",
                b"N#\\",
                b"NA\\",
                b"NP\\",
                b"NS\\",
                b"NR\\",
            )
        )
        or bool(re.match(rb"N[1-6]\\", body))
        or b"}" in body
    )


def decode_payload(information: bytes) -> Payload:
    """Decode supported data; unsupported families become byte-preserving Opaque.

    Invalid supported fields raise FieldError. This is deliberately not a
    catch-all error recovery parser: malformed and unsupported are distinct.
    """
    _information(information)
    dti, body = information[:1], information[1:]
    if dti in (b"!", b"=", b"/", b"@"):
        timestamp = None
        if dti in (b"/", b"@"):
            timestamp, body = decode_timestamp(body[:7]), body[7:]
        if body and body[:1] in b"/\\ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij":
            return Opaque(information, "compressed positions are not implemented")
        # Compressed numeric overlays can start with a digit, but not a DDMM. field.
        if (
            len(body) >= 5
            and body[4:5] != b"."
            and body[:1] in b"0123456789"
            and body[7:8] not in (b"N", b"S")
            and body[17:18] not in (b"E", b"W")
        ):
            return Opaque(information, "compressed or unsupported position format")
        if len(body) < 19:
            raise FieldError("truncated uncompressed position")
        try:
            lat = decode_coordinate(body[:8], "latitude")
            lon = decode_coordinate(body[9:18], "longitude")
        except UnsupportedFormat as exc:
            return Opaque(information, str(exc))
        symbol = Symbol(chr(body[8]), chr(body[18]))
        _symbol(symbol)
        return Position(lat, lon, symbol, dti in (b"=", b"@"), timestamp, body[19:])
    if dti == b">":
        timestamp = None
        if len(body) >= 7 and body[:6].isdigit() and body[6:7] in (b"z", b"/", b"h"):
            timestamp, body = decode_timestamp(body[:7]), body[7:]
            if timestamp.kind != "dhm_utc":
                raise FieldError("status timestamp must be DHM UTC")
        if len(information) > 63:
            raise FieldError("status body exceeds 62 bytes")
        return Status(body, timestamp)
    if dti == b":":
        if len(body) < 10 or body[9:10] != b":":
            raise FieldError("message requires a nine-byte addressee and colon")
        address = body[:9].decode("latin-1").rstrip(" ")
        _addressee(address)
        body = body[10:]
        if _special_message(address, body):
            return Opaque(
                information, "specialized message semantics are not implemented"
            )
        ack = re.fullmatch(rb"(ack|rej)([A-Za-z0-9]{1,5})", body)
        if ack:
            return Acknowledgment(address, ack[2].decode("ascii"), ack[1] == b"rej")
        text, separator, identifier = body.partition(b"{")
        message_id = identifier.decode("latin-1") if separator else None
        result = Message(address, text, message_id)
        encode_payload(result)
        return result
    return Opaque(information)


def encode_payload(payload: Payload) -> bytes:
    """Construct an information field from structured values, validating widths."""
    if isinstance(payload, Opaque):
        raw = payload.information
    elif isinstance(payload, Position):
        symbol = _symbol(payload.symbol)
        raw = b"@" if payload.messaging else b"/"
        if payload.timestamp is None:
            raw = b"=" if payload.messaging else b"!"
        else:
            raw += encode_timestamp(payload.timestamp)
        raw += encode_coordinate(payload.latitude_deg, "latitude") + symbol[:1]
        raw += (
            encode_coordinate(payload.longitude_deg, "longitude")
            + symbol[1:]
            + payload.tail
        )
    elif isinstance(payload, Status):
        raw = b">"
        if payload.timestamp is not None:
            if payload.timestamp.kind != "dhm_utc":
                raise FieldError("status timestamp must be DHM UTC")
            raw += encode_timestamp(payload.timestamp)
        elif re.match(rb"[0-9]{6}[z/h]", payload.text):
            raise FieldError("status text would be interpreted as a timestamp")
        raw += payload.text
        if len(raw) > 63:
            raise FieldError("status body exceeds 62 bytes")
    elif isinstance(payload, (Message, Acknowledgment)):
        raw = b":" + _addressee(payload.addressee) + b":"
        if isinstance(payload, Acknowledgment):
            if _special_message(payload.addressee, b""):
                raise UnsupportedFormat("specialized addressee requires Opaque")
            raw += (b"rej" if payload.rejected else b"ack") + _message_id(
                payload.message_id
            )
        else:
            if _special_message(payload.addressee, payload.text):
                raise UnsupportedFormat("specialized messages require Opaque")
            if len(payload.text) > 67 or any(
                c < 32 or c > 126 or c in b"{|~" for c in payload.text
            ):
                raise FieldError(
                    "message text requires up to 67 printable bytes excluding { | ~"
                )
            if (
                re.fullmatch(rb"(ack|rej)[A-Za-z0-9]{1,5}", payload.text)
                and payload.message_id is None
            ):
                raise FieldError(
                    "message text would be interpreted as an acknowledgment"
                )
            raw += payload.text
            if payload.message_id is not None:
                raw += b"{" + _message_id(payload.message_id)
    else:
        raise TypeError("unsupported payload model")
    _information(raw)
    return raw


def parse_packet(wire: WireInput, *, profile: ValidationProfile = "monitor") -> Packet:
    """Parse one unterminated TNC2 packet. str is a Latin-1 byte carrier."""
    raw = _wire(wire)
    envelope, separator, information = raw.partition(b":")
    if not separator:
        raise EnvelopeError("missing information separator")
    source, separator, route = envelope.partition(b">")
    if not separator:
        raise EnvelopeError("missing source separator")
    tokens = route.decode("latin-1").split(",")
    header = Header(
        source.decode("latin-1"),
        tokens[0],
        tuple(PathHop(t.rstrip("*"), t.endswith("*")) for t in tokens[1:]),
    )
    if any(t.endswith("**") for t in tokens[1:]):
        raise EnvelopeError("multiple repeated markers on a hop")
    validate_header(header, profile=profile)
    _information(information)
    if profile == "rf" and len(information) > 256:
        raise EnvelopeError("RF information exceeds 256 bytes")
    return Packet(header, decode_payload(information), raw)


def serialize_packet(
    packet: Packet, *, profile: ValidationProfile = "monitor"
) -> bytes:
    """Serialize current fields. Never reuse potentially stale original_wire."""
    validate_header(packet.header, profile=profile)
    raw = encode_payload(packet.payload)
    if profile == "rf" and len(raw) > 256:
        raise EnvelopeError("RF information exceeds 256 bytes")
    header = packet.header.source + ">" + packet.header.destination
    header += "".join(
        "," + hop.address + ("*" if hop.repeated else "") for hop in packet.header.path
    )
    return header.encode("ascii") + b":" + raw


def validate_packet(packet: Packet, *, profile: ValidationProfile = "monitor") -> None:
    """Validate fields and envelope; Opaque payloads get framing checks only."""
    serialize_packet(packet, profile=profile)
