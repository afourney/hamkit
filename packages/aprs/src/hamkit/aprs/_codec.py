# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Pure TNC2 parsing/composition; no AX.25, KISS, networking or radio I/O."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import get_args

from ._capabilities import codec_support_for
from ._conformance import check
from ._data import Symbol, Timestamp
from ._errors import (
    CodecNotImplementedError,
    ConformanceError,
    ContextRequiredError,
    EnvelopeError,
    FieldError,
    ModelError,
    ResourceLimitError,
)
from ._fields import (
    decode_coordinate,
    decode_timestamp,
    encode_coordinate,
    encode_timestamp,
)
from ._fields.position import CoordinateAxis
from ._models import (
    Acknowledgment,
    Diagnostic,
    EnvelopeProfile,
    Header,
    Hop,
    Invalid,
    Malformed,
    MalformedPolicy,
    Message,
    MicE,
    Opaque,
    Packet,
    Payload,
    Position,
    Reserved,
    Status,
    ThirdParty,
    UnsupportedPolicy,
    UserDefined,
)
from ._recovery import payload_data
from ._text import free_text, token
from ._validation import validate_tree

_ACK = re.compile(rb"(ack|rej)([A-Za-z0-9]{1,5})(?:\}([A-Za-z0-9]{0,5}))?")
_SPECIAL_BODIES = (
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


@dataclass(frozen=True)
class _Options:
    profile: EnvelopeProfile
    unsupported: UnsupportedPolicy
    malformed: MalformedPolicy
    max_depth: int


def _options(
    profile: str, unsupported: str, malformed: str, max_depth: object
) -> _Options:
    if profile not in ("monitor", "rf"):
        raise ValueError("profile must be 'monitor' or 'rf'")
    if unsupported not in ("opaque", "raise"):
        raise ValueError("unsupported must be 'opaque' or 'raise'")
    if malformed not in ("return", "raise"):
        raise ValueError("malformed must be 'return' or 'raise'")
    if type(max_depth) is not int or not 0 <= max_depth <= 32:
        raise ValueError("max_third_party_depth must be an integer in 0..32")
    return _Options(profile, unsupported, malformed, max_depth)  # type: ignore[arg-type]


def _special_message(address: str, body: bytes) -> bool:
    return (
        address.startswith(("BLN", "NWS-"))
        or body.startswith(_SPECIAL_BODIES)
        or bool(re.match(rb"N[1-6]\\", body))
    )


def _prefixed(
    prefix: str, diagnostics: tuple[Diagnostic, ...] | list[Diagnostic]
) -> list[Diagnostic]:
    return [Diagnostic(d.code, d.message, prefix + d.path[1:]) for d in diagnostics]


class _NestedMalformed(Exception):
    def __init__(self, result: Malformed):
        self.result = result


def _timestamp(raw: bytes) -> Timestamp:
    try:
        return decode_timestamp(raw)
    except ModelError as exc:
        raise ModelError("$.timestamp" + exc.path[1:], exc.message) from exc
    except FieldError as exc:
        raise ModelError("$.timestamp", str(exc)) from exc


def _coordinate(raw: bytes, axis: CoordinateAxis) -> float:
    try:
        return decode_coordinate(raw, axis)
    except FieldError as exc:
        raise ModelError(f"$.{axis}_deg", str(exc)) from exc


def _decode_payload(
    information: bytes,
    header: Header | None,
    options: _Options,
    depth: int,
    diagnostics: list[Diagnostic],
) -> Payload:
    """Decode supported families; raise for unsupported or undecodable data."""
    if not information:
        raise ModelError("$", "information field is empty")
    dti, body = information[:1], information[1:]
    if dti in (b"`", b"'", b"\x1c", b"\x1d"):
        if header is None:
            raise ContextRequiredError("Mic-E decoding requires header=Header(...)")
        raise CodecNotImplementedError("Mic-E destination and information decoding")
    if dti == b"}":
        if depth >= options.max_depth:
            raise ResourceLimitError("third-party nesting limit reached")
        inner, inner_diagnostics = _parse(body, options, depth + 1)
        if isinstance(inner, Malformed):
            raise _NestedMalformed(inner)
        diagnostics.extend(_prefixed("$.packet", inner_diagnostics))
        return ThirdParty(inner)
    if dti == b"{":
        if len(body) < 2:
            raise ModelError("$", "user-defined payload needs user ID and type")
        return UserDefined(body[:1], body[1:2], body[2:])
    if dti == b",":
        return Invalid(body)
    if information.startswith((b"!!", b"$ULTW", b"#", b"*")):
        raise CodecNotImplementedError("vendor raw-weather interpretation")
    if dti in (b"!", b"=", b"/", b"@"):
        return _decode_position(dti, body, diagnostics)
    if dti == b">":
        timestamp = None
        if len(body) >= 7 and body[:6].isdigit() and body[6:7] == b"z":
            timestamp, body = _timestamp(body[:7]), body[7:]
        return Status(free_text(body, "$.text", diagnostics), timestamp=timestamp)
    if dti == b":":
        return _decode_message(body, diagnostics)
    raise CodecNotImplementedError("unsupported information field family")


def _decode_position(
    dti: bytes, body: bytes, diagnostics: list[Diagnostic]
) -> Position:
    timestamp = None
    if dti in (b"/", b"@"):
        timestamp, body = _timestamp(body[:7]), body[7:]
    if body and body[:1] in b"/\\ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij":
        raise CodecNotImplementedError("compressed positions")
    # Compressed numeric overlays can start with a digit, but not a DDMM. field.
    if (
        len(body) >= 5
        and body[4:5] != b"."
        and body[:1] in b"0123456789"
        and body[7:8] not in (b"N", b"S")
        and body[17:18] not in (b"E", b"W")
    ):
        raise CodecNotImplementedError("compressed or unsupported position format")
    if len(body) < 19:
        raise ModelError("$", "truncated uncompressed position")
    latitude = _coordinate(body[:8], "latitude")
    longitude = _coordinate(body[9:18], "longitude")
    try:
        symbol = Symbol(chr(body[8]), chr(body[18]))
    except ModelError as exc:
        raise ModelError("$.symbol" + exc.path[1:], exc.message) from exc
    return Position(
        latitude,
        longitude,
        symbol,
        comment=free_text(body[19:], "$.comment", diagnostics),
        messaging=dti in (b"=", b"@"),
        timestamp=timestamp,
    )


def _decode_message(body: bytes, diagnostics: list[Diagnostic]) -> Payload:
    if len(body) < 10 or body[9:10] != b":":
        raise ModelError(
            "$.addressee", "message requires a nine-byte addressee and colon"
        )
    address = token(body[:9], "$.addressee").rstrip(" ")
    body = body[10:]
    if _special_message(address, body):
        raise CodecNotImplementedError("specialized message semantics")
    ack = _ACK.fullmatch(body)
    if ack:
        return Acknowledgment(
            address,
            ack[2].decode("ascii"),
            rejected=ack[1] == b"rej",
            reply_ack=None if ack[3] is None else ack[3].decode("ascii"),
        )
    text, separator, identifier = body.partition(b"{")
    message_id = reply_ack = None
    if separator:
        number, brace, ack_part = identifier.partition(b"}")
        message_id = token(number, "$.message_id")
        reply_ack = token(ack_part, "$.reply_ack") if brace else None
    return Message(
        address,
        free_text(text, "$.text", diagnostics),
        message_id=message_id,
        reply_ack=reply_ack,
    )


def _recover_payload(
    information: bytes,
    header: Header | None,
    options: _Options,
    depth: int,
    diagnostics: list[Diagnostic],
) -> Payload | Malformed:
    try:
        return _decode_payload(information, header, options, depth, diagnostics)
    except _NestedMalformed as exc:
        inner = exc.result
        return Malformed(
            information,
            tuple(_prefixed("$.packet", inner.diagnostics)),
            {"type": "third_party", "packet": inner.recovered},
        )
    except CodecNotImplementedError as exc:
        if options.unsupported == "raise":
            raise
        return Opaque(information, diagnostic=Diagnostic("unsupported", str(exc)))
    except FieldError as exc:
        if options.malformed == "raise":
            raise
        data, found = payload_data(information)
        path, message = (
            (exc.path, exc.message) if isinstance(exc, ModelError) else ("$", str(exc))
        )
        if not any(d.path == path for d in found):
            found.insert(0, Diagnostic("malformed", message, path))
        return Malformed(information, tuple(found), data)


def _parse(
    raw: bytes, options: _Options, depth: int
) -> tuple[Packet | Malformed, list[Diagnostic]]:
    """Parse one packet; also return the decode findings (not conformance)."""
    envelope, separator, information = raw.partition(b":")
    issues: list[Diagnostic] = []
    header_data: dict[str, object] = {}
    recovered: dict[str, object] = {
        "type": "packet",
        "header": header_data,
        "payload": {},
    }

    def issue(path: str, message: str) -> None:
        if options.malformed == "raise":
            raise EnvelopeError(f"{path}: {message}")
        issues.append(Diagnostic("malformed", message, path))

    def address(path: str, raw_token: bytes) -> str | None:
        try:
            return Hop(token(raw_token, path)).address
        except ModelError as exc:
            issue(path, exc.message)
            return None

    if not separator:
        issue("$.payload", "missing information separator")
    source, arrow, route = envelope.partition(b">")
    if not arrow:
        issue("$.header", "missing source separator")
    tokens = route.split(b",") if arrow else []
    for key, raw_token in (
        ("source", source),
        *(("destination", t) for t in tokens[:1]),
    ):
        value = address(f"$.header.{key}", raw_token)
        if value is not None:
            header_data[key] = value
    hops = []
    for i, raw_token in enumerate(tokens[1:]):
        repeated = raw_token.endswith(b"*")
        value = address(f"$.header.path[{i}].address", raw_token.removesuffix(b"*"))
        hops.append(
            {"repeated": repeated} | ({} if value is None else {"address": value})
        )
    if hops:
        header_data["path"] = hops

    header = None
    if not issues:
        header = Header(
            str(header_data["source"]),
            str(header_data["destination"]),
            tuple(Hop(str(h["address"]), bool(h["repeated"])) for h in hops),
        )
    payload: Payload | Malformed | None = None
    found: list[Diagnostic] = []
    if separator:
        try:
            payload = _recover_payload(information, header, options, depth, found)
        except ContextRequiredError as exc:
            # A broken outer header does not prove an unimplemented Mic-E body invalid.
            if not issues:
                raise
            payload = Opaque(
                information, diagnostic=Diagnostic("unsupported", str(exc))
            )
        if isinstance(payload, Malformed):
            recovered["payload"] = payload.recovered
            issues.extend(_prefixed("$.payload", payload.diagnostics))
        elif issues:
            from ._json import to_json_dict

            recovered["payload"] = to_json_dict(payload)
    if issues:
        return Malformed(raw, tuple(issues), recovered), []
    assert header is not None and payload is not None
    assert not isinstance(payload, Malformed)
    found = _prefixed("$.payload", found)
    if options.profile == "rf" and len(information) > 256:
        found.append(
            Diagnostic("nonconforming", "RF information exceeds 256 bytes", "$.payload")
        )
    packet = Packet(header, payload, original_wire=raw)
    # Findings are computed from the finished packet; set them once, in place.
    object.__setattr__(packet, "diagnostics", (*found, *check(packet, options.profile)))
    return packet, found


def parse_packet(
    wire: bytes,
    *,
    profile: EnvelopeProfile = "monitor",
    unsupported: UnsupportedPolicy = "opaque",
    malformed: MalformedPolicy = "return",
    max_third_party_depth: int = 4,
) -> Packet | Malformed:
    """Parse one unframed TNC2 packet, such as ``b"N0CALL>APRS:>Ready"``.

    Returns a Packet whenever every field decodes. Departures from APRS rules
    are listed in Packet.diagnostics as "nonconforming". Fields that cannot be
    decoded yield a Malformed with recovered values (or raise with
    malformed="raise"). Families without a decoder become Opaque (or raise with
    unsupported="raise"). profile="rf" adds AX.25 address and size findings.
    CR/LF is never stripped; use parse_tnc2_line for line-oriented input.
    """
    if not isinstance(wire, bytes):
        raise TypeError(
            "parse_packet requires bytes; encode text first, e.g. line.encode()"
        )
    options = _options(profile, unsupported, malformed, max_third_party_depth)
    return _parse(wire, options, 0)[0]


def parse_payload(
    information: bytes,
    *,
    header: Header | None = None,
    unsupported: UnsupportedPolicy = "opaque",
    malformed: MalformedPolicy = "return",
    max_third_party_depth: int = 4,
) -> Payload | Malformed:
    """Decode an information field alone. Mic-E always requires header.

    Use parse_packet to also receive nonconforming diagnostics.
    """
    if not isinstance(information, bytes):
        raise TypeError("parse_payload requires bytes")
    options = _options("monitor", unsupported, malformed, max_third_party_depth)
    if header is not None:
        validate_tree(header)
    return _recover_payload(information, header, options, 0, [])


def _require_codecs(payload: Payload) -> None:
    """Raise for families without an encoder before judging their content."""
    if isinstance(payload, ThirdParty):
        _require_codecs(payload.packet.payload)
    elif codec_support_for(payload).encode == "unimplemented":
        raise CodecNotImplementedError(f"{type(payload).__name__} encoding")


def _encode_payload(
    payload: Payload, header: Header | None, max_depth: int, depth: int
) -> bytes:
    """Construct an information field from validated, conforming values."""
    if isinstance(payload, MicE):
        if header is None:
            raise ContextRequiredError("Mic-E encoding needs the packet header")
        raise CodecNotImplementedError("Mic-E joint destination/information encoding")
    if isinstance(payload, ThirdParty):
        if depth >= max_depth:
            raise ResourceLimitError("third-party nesting limit reached")
        return b"}" + _serialize(payload.packet, max_depth, depth + 1)
    if isinstance(payload, UserDefined):
        return b"{" + payload.user_id + payload.user_type + payload.data
    if isinstance(payload, Invalid):
        return b"," + payload.data
    if isinstance(payload, Reserved):
        return bytes([payload.dti]) + payload.data
    if isinstance(payload, Opaque):
        return payload.information
    if isinstance(payload, Position):
        if payload.compression is not None or payload.ambiguity or payload.extensions:
            raise CodecNotImplementedError(
                "structured position compression/ambiguity/extensions"
            )
        raw = (
            (b"@" if payload.messaging else b"/")
            if payload.timestamp
            else (b"=" if payload.messaging else b"!")
        )
        if payload.timestamp is not None:
            raw += encode_timestamp(payload.timestamp)
        symbol = payload.symbol
        return (
            raw
            + encode_coordinate(payload.latitude_deg, "latitude")
            + symbol.table_id.encode("ascii")
            + encode_coordinate(payload.longitude_deg, "longitude")
            + symbol.code.encode("ascii")
            + payload.comment.encode("utf-8")
        )
    if isinstance(payload, Status):
        if payload.grid is not None or payload.beam is not None:
            raise CodecNotImplementedError("structured status grid/symbol/beam")
        raw = b">"
        if payload.timestamp is not None:
            raw += encode_timestamp(payload.timestamp)
        return raw + payload.text.encode("utf-8")
    if isinstance(payload, (Message, Acknowledgment)):
        raw = b":" + payload.addressee.ljust(9).encode("ascii") + b":"
        reply = b"" if payload.reply_ack is None else b"}" + payload.reply_ack.encode()
        if isinstance(payload, Acknowledgment):
            if _special_message(payload.addressee, b""):
                raise CodecNotImplementedError("specialized addressee")
            verb = b"rej" if payload.rejected else b"ack"
            return raw + verb + payload.message_id.encode("ascii") + reply
        body = payload.text.encode("utf-8")
        if _special_message(payload.addressee, body):
            raise CodecNotImplementedError("specialized message")
        if payload.message_id is not None:
            body += b"{" + payload.message_id.encode("ascii") + reply
        return raw + body
    if type(payload) in get_args(Payload):
        raise CodecNotImplementedError(f"{type(payload).__name__} encoding")
    raise TypeError("unsupported payload model")


def _serialize(packet: Packet, max_depth: int, depth: int) -> bytes:
    information = _encode_payload(packet.payload, packet.header, max_depth, depth)
    return str(packet.header).encode("ascii") + b":" + information


def _ready_to_send(value: Packet | Payload, profile: EnvelopeProfile) -> None:
    validate_tree(value)
    payload = value.payload if isinstance(value, Packet) else value
    if isinstance(payload, MicE) and not isinstance(value, Packet):
        raise ContextRequiredError(
            "Mic-E encoding needs the header; use serialize_packet"
        )
    _require_codecs(payload)
    findings = check(value, profile)
    if findings:
        raise ConformanceError(findings)


def serialize_packet(
    packet: Packet,
    *,
    profile: EnvelopeProfile = "monitor",
    max_third_party_depth: int = 4,
) -> bytes:
    """Encode a packet for sending. Never replays original_wire.

    Every packet is validated first: ModelError for invalid fields,
    CodecNotImplementedError for families without an encoder, and
    ConformanceError (with all findings) for anything outside APRS rules.
    profile="rf" also applies AX.25 address and information-size limits.
    """
    if not isinstance(packet, Packet):
        raise TypeError("serialize_packet requires a Packet; repair a Malformed first")
    options = _options(profile, "raise", "raise", max_third_party_depth)
    _ready_to_send(packet, options.profile)
    wire = _serialize(packet, options.max_depth, 0)
    information = wire.partition(b":")[2]
    if options.profile == "rf" and len(information) > 256:
        raise ConformanceError(
            (
                Diagnostic(
                    "nonconforming", "RF information exceeds 256 bytes", "$.payload"
                ),
            )
        )
    return wire


def serialize_payload(payload: Payload, *, max_third_party_depth: int = 4) -> bytes:
    """Encode an information field alone, with the same validation as packets."""
    if isinstance(payload, (Packet, Malformed)):
        raise TypeError("serialize_payload requires a payload model")
    options = _options("monitor", "raise", "raise", max_third_party_depth)
    _ready_to_send(payload, options.profile)
    return _encode_payload(payload, None, options.max_depth, 0)


def check_packet(
    packet: Packet, *, profile: EnvelopeProfile = "monitor"
) -> tuple[Diagnostic, ...]:
    """Every conformance finding for a packet, without raising.

    An empty result does not promise an encoder exists; validate_packet does.
    """
    if not isinstance(packet, Packet):
        raise TypeError("check_packet requires a Packet")
    _options(profile, "raise", "raise", 4)
    validate_tree(packet)
    return check(packet, profile)


def validate_packet(
    packet: Packet,
    *,
    profile: EnvelopeProfile = "monitor",
    max_third_party_depth: int = 4,
) -> None:
    """Raise exactly as serialize_packet would; return None when it can be sent."""
    serialize_packet(
        packet, profile=profile, max_third_party_depth=max_third_party_depth
    )
