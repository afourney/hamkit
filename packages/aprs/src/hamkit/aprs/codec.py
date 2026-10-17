# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Pure TNC2 parsing/composition; no AX.25, KISS, networking or radio I/O."""

import re
from typing import get_args

from .data import Extensions
from .errors import (
    CodecNotImplemented,
    ContextRequired,
    EnvelopeError,
    FieldError,
    ResourceLimitError,
    UnsupportedFormat,
)
from .fields import (
    decode_coordinate,
    decode_timestamp,
    encode_coordinate,
    encode_timestamp,
)
from .models import (
    Acknowledgment,
    DecodeOptions,
    Diagnostic,
    EncodedPacketFields,
    EncodeOptions,
    Header,
    InvalidTest,
    Message,
    MicE,
    Opaque,
    Packet,
    PathHop,
    Payload,
    Position,
    Reserved,
    Status,
    Symbol,
    ThirdParty,
    UserDefined,
    ValidationProfile,
    WireInput,
)
from .validation import validate_header

_DEFAULT_DECODE = DecodeOptions()
_DEFAULT_ENCODE = EncodeOptions()


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
    if not raw:
        raise FieldError("information must be nonempty")


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


def _decode_payload(
    information: bytes, header: Header | None, options: DecodeOptions, depth: int
) -> Payload:
    """Decode supported data; unsupported families become byte-preserving Opaque.

    Invalid supported fields raise FieldError. This is deliberately not a
    catch-all error recovery parser: malformed and unsupported are distinct.
    """
    _information(information)
    dti, body = information[:1], information[1:]
    if dti in (b"`", b"'", b"\x1c", b"\x1d"):
        if header is None:
            raise ContextRequired("Mic-E decoding requires header=Header(...)")
        raise CodecNotImplemented("Mic-E destination and information decoding")
    if dti == b"}":
        if depth >= options.max_depth:
            raise ResourceLimitError("third-party nesting limit reached")
        try:
            return ThirdParty(_parse_packet(body, "monitor", options, depth + 1))
        except EnvelopeError as exc:
            raise FieldError(f"invalid third-party envelope: {exc}") from exc
    if dti == b"{":
        if len(body) < 2:
            raise FieldError("user-defined payload needs user ID and type")
        return UserDefined(body[:1], body[1:2], body[2:])
    if dti == b",":
        return InvalidTest(body)
    if information.startswith((b"!!", b"$ULTW", b"#", b"*")):
        raise CodecNotImplemented("vendor raw-weather interpretation")
    if dti in (b"!", b"=", b"/", b"@"):
        timestamp = None
        if dti in (b"/", b"@"):
            timestamp, body = decode_timestamp(body[:7]), body[7:]
        if body and body[:1] in b"/\\ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij":
            raise CodecNotImplemented("compressed positions")
        # Compressed numeric overlays can start with a digit, but not a DDMM. field.
        if (
            len(body) >= 5
            and body[4:5] != b"."
            and body[:1] in b"0123456789"
            and body[7:8] not in (b"N", b"S")
            and body[17:18] not in (b"E", b"W")
        ):
            raise CodecNotImplemented("compressed or unsupported position format")
        if len(body) < 19:
            raise FieldError("truncated uncompressed position")
        try:
            lat = decode_coordinate(body[:8], "latitude")
            lon = decode_coordinate(body[9:18], "longitude")
        except UnsupportedFormat as exc:
            raise CodecNotImplemented(str(exc)) from exc
        symbol = Symbol(chr(body[8]), chr(body[18]))
        _symbol(symbol)
        return Position(lat, lon, symbol, dti in (b"=", b"@"), timestamp, body[19:])
    if dti == b">":
        timestamp = None
        if len(body) >= 7 and body[:6].isdigit() and body[6:7] == b"z":
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
            raise CodecNotImplemented("specialized message semantics")
        ack = re.fullmatch(rb"(ack|rej)([A-Za-z0-9]{1,5})", body)
        if ack:
            return Acknowledgment(address, ack[2].decode("ascii"), ack[1] == b"rej")
        text, separator, identifier = body.partition(b"{")
        message_id = identifier.decode("latin-1") if separator else None
        result = Message(address, text, message_id)
        encode_payload(result)
        return result
    raise CodecNotImplemented("unsupported information field family")


def _encode_payload(
    payload: Payload, header: Header | None, options: EncodeOptions, depth: int
) -> bytes:
    """Construct an information field from structured values, validating widths."""
    if isinstance(payload, MicE):
        if header is None:
            raise ContextRequired(
                "Mic-E encoding requires a header; use encode_packet_fields"
            )
        raise CodecNotImplemented("Mic-E joint destination/information encoding")
    if isinstance(payload, ThirdParty):
        if depth >= options.max_depth:
            raise ResourceLimitError("third-party nesting limit reached")
        raw = b"}" + _serialize_packet(payload.packet, "monitor", options, depth + 1)
    elif isinstance(payload, UserDefined):
        if len(payload.user_id) != 1 or len(payload.user_type) != 1:
            raise FieldError("user ID and type must each be one byte")
        raw = b"{" + payload.user_id + payload.user_type + payload.data
    elif isinstance(payload, InvalidTest):
        raw = b"," + payload.data
    elif isinstance(payload, Reserved):
        if not 0 <= payload.dti <= 255:
            raise FieldError("DTI must be one byte")
        raw = bytes([payload.dti]) + payload.data
    elif isinstance(payload, Opaque):
        raw = payload.information
    elif isinstance(payload, Position):
        if (
            payload.encoding != "uncompressed"
            or payload.ambiguity is not None
            or payload.compression is not None
            or payload.extensions != Extensions()
        ):
            raise CodecNotImplemented(
                "structured position encoding/ambiguity/extensions"
            )
        if payload.tail and payload.comment:
            raise FieldError("choose unsliced tail or structured comment, not both")
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
            + (payload.tail or payload.comment)
        )
    elif isinstance(payload, Status):
        if (
            payload.grid is not None
            or payload.symbol is not None
            or payload.beam is not None
        ):
            raise CodecNotImplemented("structured status grid/symbol/beam")
        raw = b">"
        if payload.timestamp is not None:
            if payload.timestamp.kind != "dhm_utc":
                raise FieldError("status timestamp must be DHM UTC")
            raw += encode_timestamp(payload.timestamp)
        elif re.match(rb"[0-9]{6}z", payload.text):
            raise FieldError("status text would be interpreted as a timestamp")
        raw += payload.text
        if len(raw) > 63:
            raise FieldError("status body exceeds 62 bytes")
    elif isinstance(payload, (Message, Acknowledgment)):
        if payload.reply_ack is not None:
            raise CodecNotImplemented("reply-ack message/acknowledgment")
        raw = b":" + _addressee(payload.addressee) + b":"
        if isinstance(payload, Acknowledgment):
            if _special_message(payload.addressee, b""):
                raise CodecNotImplemented("specialized addressee")
            raw += (b"rej" if payload.rejected else b"ack") + _message_id(
                payload.message_id
            )
        else:
            if _special_message(payload.addressee, payload.text):
                raise CodecNotImplemented("specialized message")
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
        if type(payload) in get_args(Payload):
            raise CodecNotImplemented(f"{type(payload).__name__} encoding")
        raise TypeError("unsupported payload model")
    _information(raw)
    return raw


def _check_options(options: DecodeOptions | EncodeOptions) -> None:
    if type(options.max_depth) is not int or not 0 <= options.max_depth <= 32:
        raise ValueError("max_depth must be an integer in 0..32")
    if options.specification not in ("core-1.1", "historical-1.0", "compatibility-fap"):
        raise ValueError("unknown specification profile")
    if options.specification != "core-1.1":
        raise CodecNotImplemented(f"specification profile {options.specification}")
    if isinstance(options, DecodeOptions):
        if options.unsupported not in ("opaque", "raise") or options.malformed not in (
            "opaque",
            "raise",
        ):
            raise ValueError("invalid payload recovery policy")
    elif options.destination not in ("derive", "require_match"):
        raise ValueError("invalid destination policy")


def _recover_payload(
    information: bytes, header: Header | None, options: DecodeOptions, depth: int
) -> Payload:
    try:
        return _decode_payload(information, header, options, depth)
    except CodecNotImplemented as exc:
        if options.unsupported == "raise":
            raise
        return Opaque(information, str(exc), Diagnostic("unsupported", str(exc)))
    except FieldError as exc:
        if options.malformed == "raise":
            raise
        return Opaque(information, str(exc), Diagnostic("malformed", str(exc)))


def decode_payload(
    information: bytes,
    *,
    header: Header | None = None,
    options: DecodeOptions = _DEFAULT_DECODE,
) -> Payload:
    """Decode bytes with optional outer context; Mic-E always requires header.

    Unimplemented formats follow options.unsupported; malformed supported fields
    follow options.malformed. Context/type/resource errors always raise.
    """
    _check_options(options)
    if header is not None:
        validate_header(header)
    return _recover_payload(information, header, options, 0)


def encode_payload(
    payload: Payload,
    *,
    header: Header | None = None,
    options: EncodeOptions = _DEFAULT_ENCODE,
) -> bytes:
    """Encode information only. Header-dependent output must match header.

    Use encode_packet_fields when the codec should derive a destination. This
    convenience API never silently discards a destination produced by a codec.
    """
    _check_options(options)
    if header is None:
        return _encode_payload(payload, None, options, 0)
    result = encode_packet_fields(Packet(header, payload), options=options)
    if result.header != header:
        raise ContextRequired("codec changed header; use encode_packet_fields")
    return result.information


def _parse_packet(
    wire: WireInput, profile: ValidationProfile, options: DecodeOptions, depth: int
) -> Packet:
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
        tuple(PathHop(t.removesuffix("*"), t.endswith("*")) for t in tokens[1:]),
    )
    validate_header(header, profile=profile)
    if profile == "rf" and len(information) > 256:
        raise EnvelopeError("RF information exceeds 256 bytes")
    return Packet(header, _recover_payload(information, header, options, depth), raw)


def parse_packet(
    wire: WireInput,
    *,
    profile: ValidationProfile = "monitor",
    options: DecodeOptions = _DEFAULT_DECODE,
) -> Packet:
    """Parse one unframed TNC2 byte sequence, including binary payload bytes.

    No stripping of CR/LF. Use parse_tnc2_line for line-oriented transport.
    Envelope validation is independent of payload recovery/specification policy.
    """
    _check_options(options)
    return _parse_packet(wire, profile, options, 0)


def _encode_packet_fields(
    packet: Packet, profile: ValidationProfile, options: EncodeOptions, depth: int
) -> EncodedPacketFields:
    validate_header(packet.header, profile=profile)
    # Header-dependent encoders belong HERE. Mic-E will return a derived
    # destination plus information atomically; require_match rejects conflicts.
    # The current Mic-E codec raises explicitly, never fabricating either half.
    raw = _encode_payload(packet.payload, packet.header, options, depth)
    if profile == "rf" and len(raw) > 256:
        raise EnvelopeError("RF information exceeds 256 bytes")
    return EncodedPacketFields(packet.header, raw)


def encode_packet_fields(
    packet: Packet,
    *,
    profile: ValidationProfile = "monitor",
    options: EncodeOptions = _DEFAULT_ENCODE,
) -> EncodedPacketFields:
    """Authoritative joint header/information encoder, including future Mic-E.

    destination='derive' permits replacing the template destination;
    'require_match' requires agreement. No header-dependent codecs exist yet.
    """
    _check_options(options)
    return _encode_packet_fields(packet, profile, options, 0)


def _serialize_packet(
    packet: Packet, profile: ValidationProfile, options: EncodeOptions, depth: int
) -> bytes:
    encoded = _encode_packet_fields(packet, profile, options, depth)
    header = encoded.header.source + ">" + encoded.header.destination
    header += "".join(
        "," + hop.address + ("*" if hop.repeated else "") for hop in encoded.header.path
    )
    return header.encode("ascii") + b":" + encoded.information


def serialize_packet(
    packet: Packet,
    *,
    profile: ValidationProfile = "monitor",
    options: EncodeOptions = _DEFAULT_ENCODE,
) -> bytes:
    """Encode current fields, including binary payloads; never use original_wire."""
    _check_options(options)
    return _serialize_packet(packet, profile, options, 0)


def validate_packet(
    packet: Packet,
    *,
    profile: ValidationProfile = "monitor",
    options: EncodeOptions = _DEFAULT_ENCODE,
) -> None:
    """Wire encodability check; raises CodecNotImplemented for missing codecs."""
    serialize_packet(packet, profile=profile, options=options)
