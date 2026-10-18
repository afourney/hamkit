# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Pure TNC2 parsing/composition; no AX.25, KISS, networking or radio I/O."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import get_args

from . import _data as d
from . import _extensions, _messages
from . import _models as m
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
    encode_timestamp,
)
from ._fields.position import CoordinateAxis
from ._models import (
    Acknowledgment,
    Diagnostic,
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
    ThirdParty,
    UnsupportedPolicy,
    UserDefined,
)
from ._policy import _DEFAULT_POLICY, EnvelopePolicy
from ._recovery import payload_data
from ._text import free_text, token
from ._validation import validate_tree
from ._wire_forms import resolve as resolve_wire_forms

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
    policy: EnvelopePolicy
    unsupported: UnsupportedPolicy
    malformed: MalformedPolicy
    max_depth: int


def _options(
    policy: EnvelopePolicy,
    unsupported: str,
    malformed: str,
    max_depth: object,
    legacy_positions: object = None,
) -> _Options:
    if not isinstance(policy, EnvelopePolicy):
        raise TypeError("policy must be an EnvelopePolicy")
    if unsupported not in ("opaque", "raise"):
        raise ValueError("unsupported must be 'opaque' or 'raise'")
    if malformed not in ("return", "raise"):
        raise ValueError("malformed must be 'return' or 'raise'")
    if type(max_depth) is not int or not 0 <= max_depth <= 32:
        raise ValueError("max_third_party_depth must be an integer in 0..32")
    if legacy_positions is not None and type(legacy_positions) is not bool:
        raise TypeError("legacy_positions must be a bool")
    if legacy_positions is not None:
        policy = replace(policy, legacy_positions=legacy_positions)
    return _Options(policy, unsupported, malformed, max_depth)  # type: ignore[arg-type]


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
    policy = options.policy
    dti, body = information[:1], information[1:]
    if dti in (b"`", b"'", b"\x1c", b"\x1d"):
        if header is None:
            raise ContextRequiredError("Mic-E decoding requires header=Header(...)")
        from . import _mic_e

        return _mic_e.read(information, header, diagnostics, policy)
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
        from . import _weather

        return m.RawWeather(
            (
                "ultimeter_2000"
                if information.startswith((b"!!", b"$ULTW"))
                else "ultimeter_ii"
            ),
            information,
            weather=_weather.vendor(information),
        )
    if dti in (b"!", b"=", b"/", b"@"):
        return _decode_position(dti, body, diagnostics, policy)
    if dti == b">":
        return _messages.status(body, diagnostics, policy)
    if dti == b"?":
        return _messages.query(information)
    if dti == b"<":
        tokens = []
        for part in token(body, "$.tokens").split(","):
            name, sep, value = part.partition("=")
            tokens.append(d.Capability(name, value if sep else None))
        return m.Capabilities(tuple(tokens))
    if information.startswith(b"T#"):
        return _messages.telemetry(information, diagnostics, policy)
    if dti == b"_":
        from . import _weather

        return _weather.read(body, diagnostics=diagnostics, policy=policy)[0]
    if dti == b";":
        if len(body) < 17 or body[9:10] not in (b"*", b"_"):
            raise FieldError("invalid object name or alive marker")
        name = token(body[:9], "$.name").rstrip()
        position = _decode_position(b"/", body[10:], diagnostics, policy)
        assert position.timestamp is not None
        return m.Object(
            name,
            position.latitude_deg,
            position.longitude_deg,
            position.symbol,
            timestamp=position.timestamp,
            alive=body[9:10] == b"*",
            comment=position.comment,
            ambiguity=position.ambiguity,
            compression=position.compression,
            extensions=position.extensions,
        )
    if dti == b")":
        match = re.match(rb"([^!_]{1,9})([!_])(.*)", body, re.DOTALL)
        if not match:
            raise FieldError("invalid item name or marker")
        position = _decode_position(b"!", match[3], diagnostics, policy)
        return m.Item(
            token(match[1], "$.name"),
            position.latitude_deg,
            position.longitude_deg,
            position.symbol,
            alive=match[2] == b"!",
            comment=position.comment,
            ambiguity=position.ambiguity,
            compression=position.compression,
            extensions=position.extensions,
        )
    if dti == b"$":
        from . import _nmea_codec

        return _nmea_codec.read(information, header, diagnostics, policy)
    if dti == b"[":
        match = re.match(rb"([A-Ra-r]{2}\d{2}(?:[A-Xa-x]{2})?)\](.*)", body, re.DOTALL)
        if not match:
            raise FieldError("invalid Maidenhead locator")
        return m.Maidenhead(
            d.Grid(match[1].decode().upper()),
            comment=free_text(match[2], "$.comment", diagnostics, policy),
        )
    if dti == b"%":
        match = re.fullmatch(rb"%(\d{3})/(\d)", information)
        if match:
            return m.Agrelo(int(match[1]), int(match[2]), raw=information)
    if dti == b":":
        return _decode_message(body, diagnostics, policy)
    # APRS101 p.18 lets a position start within the first 40 bytes of other
    # text (X1J); the APRS 1.1 addendum deprecates that search, so it is opt-in.
    offset = information.find(b"!") if options.policy.legacy_positions else -1
    if 0 < offset < 40:
        return m.LegacyPosition(
            information[:offset],
            _decode_position(b"!", information[offset + 1 :], diagnostics, policy),
        )
    if (
        header is not None
        and (header.destination or "").split("-")[0] in ("BEACON", "ID", "UIDIGI", "CQ")
        or len(information) > 1
        and information[:1].isalpha()
        and b" " in information
    ):
        return m.Beacon(free_text(information, "$.text", diagnostics, policy))
    raise CodecNotImplementedError("unsupported information field family")


def _decode_position(
    dti: bytes, body: bytes, diagnostics: list[Diagnostic], policy: EnvelopePolicy
) -> Position:
    timestamp = None
    if dti in (b"/", b"@"):
        timestamp, body = _timestamp(body[:7]), body[7:]
    from . import _position_codec as pc

    compressed = bool(
        body
        and (
            body[:1] in b"/\\ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
            or (len(body) >= 13 and body[4:5] != b"." and body[7:8] not in (b"N", b"S"))
        )
    )
    if compressed:
        latitude, longitude, symbol, compression, primary, rest = pc.compressed(body)
        if body[10] != 32 and body[12] - 33 >= 64:
            diagnostics.append(
                Diagnostic(
                    "nonconforming", "reserved compression type bit", "$.compression"
                )
            )
        extensions, rest = _extensions.read(rest, symbol, policy)
        for name in ("motion", "altitude", "range"):
            value = getattr(primary, name)
            if value is not None:
                extensions = replace(extensions, **{name: value})
        if symbol.code in "_W" and primary.motion is not None:
            weather = extensions.weather or d.Weather()
            weather = replace(
                weather,
                wind_direction=d.Measurement(primary.motion.course_deg, "degrees"),
                wind_speed=d.Measurement(primary.motion.speed_knots, "knots"),
            )
            extensions = replace(extensions, motion=None, weather=weather)
        return Position(
            latitude,
            longitude,
            symbol,
            compression=compression,
            extensions=extensions,
            timestamp=timestamp,
            messaging=dti in (b"=", b"@"),
            comment=free_text(rest, "$.comment", diagnostics, policy),
        )
    if len(body) < 19:
        raise ModelError("$", "truncated uncompressed position")
    latitude, longitude, ambiguity = pc.coordinates(body[:8], body[9:18])
    try:
        symbol = Symbol(chr(body[8]), chr(body[18]))
    except ModelError as exc:
        raise ModelError("$.symbol" + exc.path[1:], exc.message) from exc
    extensions, rest = _extensions.read(body[19:], symbol, policy)
    return Position(
        pc.dao_offset(latitude, extensions.dao, "latitude")
        if not ambiguity
        else latitude,
        pc.dao_offset(longitude, extensions.dao, "longitude")
        if not ambiguity
        else longitude,
        symbol,
        comment=free_text(rest, "$.comment", diagnostics, policy),
        messaging=dti in (b"=", b"@"),
        timestamp=timestamp,
        extensions=extensions,
        ambiguity=ambiguity,
    )


def _decode_message(
    body: bytes, diagnostics: list[Diagnostic], policy: EnvelopePolicy
) -> Payload:
    if len(body) < 10 or body[9:10] != b":":
        raise ModelError(
            "$.addressee", "message requires a nine-byte addressee and colon"
        )
    address = token(body[:9], "$.addressee").rstrip(" ")
    body = body[10:]
    if _special_message(address, body):
        special = _messages.specialized(address, body, diagnostics, policy)
        if special is not None:
            return special
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
    if not separator:
        response = _messages.response(address, text)
        if response is not None:
            return response
    return Message(
        address,
        free_text(text, "$.text", diagnostics, policy),
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
    if envelope.count(b">") > 1 and b"," not in envelope:
        parts = envelope.split(b">")
        if all(parts):
            envelope = parts[0] + b">" + parts[-1] + b"," + b",".join(parts[1:-1])
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
    policy = options.policy if depth == 0 else None
    if policy is not None:
        found.extend(_envelope_sizes(policy, len(information), len(raw) + 2))
    packet = Packet(header, payload, original_wire=raw)
    # Findings are computed from the finished packet; set them once, in place.
    object.__setattr__(
        packet,
        "diagnostics",
        (*found, *check(packet, options.policy, check_envelope=depth == 0)),
    )
    return packet, found


def parse_packet(
    wire: bytes,
    *,
    policy: EnvelopePolicy = _DEFAULT_POLICY,
    unsupported: UnsupportedPolicy = "opaque",
    malformed: MalformedPolicy = "return",
    max_third_party_depth: int = 4,
    legacy_positions: bool | None = None,
) -> Packet | Malformed:
    """Parse one unframed TNC2 packet, such as ``b"N0CALL>APRS:>Ready"``.

    Returns a Packet whenever every field decodes. Departures from APRS rules
    are listed in Packet.diagnostics as "nonconforming". Fields that cannot be
    decoded yield a Malformed with recovered values (or raise with
    malformed="raise"). Families without a decoder become Opaque (or raise with
    unsupported="raise"). The policy defaults to APRS_IS(); pass RF() for
    AX.25 address and size constraints, or supply a custom EnvelopePolicy.
    CR/LF is never stripped; use parse_tnc2_line for line-oriented input.
    legacy_positions=True restores the deprecated APRS101 search for a "!"
    position within the first 40 bytes of other text (LegacyPosition).
    """
    if not isinstance(wire, bytes):
        raise TypeError(
            "parse_packet requires bytes; encode text first, e.g. line.encode()"
        )
    options = _options(
        policy, unsupported, malformed, max_third_party_depth, legacy_positions
    )
    return _parse(wire, options, 0)[0]


def parse_payload(
    information: bytes,
    *,
    header: Header | None = None,
    policy: EnvelopePolicy = _DEFAULT_POLICY,
    unsupported: UnsupportedPolicy = "opaque",
    malformed: MalformedPolicy = "return",
    max_third_party_depth: int = 4,
    legacy_positions: bool | None = None,
) -> Payload | Malformed:
    """Decode an information field alone. Mic-E always requires header.

    Use parse_packet to also receive nonconforming diagnostics.
    """
    if not isinstance(information, bytes):
        raise TypeError("parse_payload requires bytes")
    options = _options(
        policy, unsupported, malformed, max_third_party_depth, legacy_positions
    )
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
    payload: Payload,
    header: Header | None,
    max_depth: int,
    depth: int,
    policy: EnvelopePolicy,
) -> bytes:
    """Construct an information field from validated, conforming values."""
    application = _messages.write(payload)
    if application is not None:
        return application
    if isinstance(payload, m.Weather):
        from . import _weather

        return _weather.write(payload, policy=policy)
    if isinstance(payload, (m.Object, m.Item)):
        p = payload
        position = Position(
            p.latitude_deg,
            p.longitude_deg,
            p.symbol,
            comment=p.comment,
            ambiguity=p.ambiguity,
            compression=p.compression,
            extensions=p.extensions,
        )
        raw = _encode_payload(position, header, max_depth, depth, policy)[1:]
        if isinstance(p, m.Object):
            return (
                b";"
                + p.name.ljust(9).encode()
                + (b"*" if p.alive else b"_")
                + encode_timestamp(p.timestamp)
                + raw
            )
        return b")" + p.name.encode() + (b"!" if p.alive else b"_") + raw
    if isinstance(payload, m.NMEA):
        from . import _nmea_codec

        if payload.symbol is not None and payload.symbol != _nmea_codec.header_symbol(
            header
        ):
            raise FieldError("NMEA symbol does not match the packet header")
        return _nmea_codec.write(payload)
    if isinstance(payload, (m.RawWeather, m.ExternalExtension)):
        return payload.information
    if isinstance(payload, m.Agrelo):
        return b"%%%03d/%d" % (round(payload.bearing_deg), payload.quality_code)
    if isinstance(payload, m.Maidenhead):
        if payload.symbol is not None:
            raise FieldError("bracketed Maidenhead beacons have no symbol field")
        return b"[" + payload.grid.locator.encode() + b"]" + payload.comment.encode()
    if isinstance(payload, m.Beacon):
        return payload.text.encode()
    if isinstance(payload, m.LegacyPosition):
        return payload.prefix + _encode_payload(
            payload.position, header, max_depth, depth, policy
        )
    if isinstance(payload, MicE):
        from . import _mic_e

        return _mic_e.write(payload, header, policy)
    if isinstance(payload, ThirdParty):
        if depth >= max_depth:
            raise ResourceLimitError("third-party nesting limit reached")
        return b"}" + _serialize(payload.packet, max_depth, depth + 1, policy)
    if isinstance(payload, UserDefined):
        return b"{" + payload.user_id + payload.user_type + payload.data
    if isinstance(payload, Invalid):
        return b"," + payload.data
    if isinstance(payload, Reserved):
        return bytes([payload.dti]) + payload.data
    if isinstance(payload, Opaque):
        return payload.information
    if isinstance(payload, Position):
        raw = (
            (b"@" if payload.messaging else b"/")
            if payload.timestamp
            else (b"=" if payload.messaging else b"!")
        )
        if payload.timestamp is not None:
            raw += encode_timestamp(payload.timestamp)
        from . import _position_codec as pc

        symbol = payload.symbol
        extensions = payload.extensions
        from ._dao import base_coordinates

        semantic_coordinates = (payload.latitude_deg, payload.longitude_deg)
        latitude, longitude = base_coordinates(payload)
        payload = replace(payload, latitude_deg=latitude, longitude_deg=longitude)
        if payload.compression is not None:
            position_wire, extensions = pc.compressed_bytes(payload)
        else:
            position_wire = (
                pc.coordinate_bytes(payload.latitude_deg, "latitude", payload.ambiguity)
                + symbol.table_id.encode()
                + pc.coordinate_bytes(
                    payload.longitude_deg, "longitude", payload.ambiguity
                )
                + symbol.code.encode()
            )
        return (
            raw
            + position_wire
            + _extensions.write(
                extensions,
                symbol,
                payload.comment.encode("utf-8"),
                policy,
                coordinates=semantic_coordinates,
            )
            + payload.comment.encode("utf-8")
        )
    if isinstance(payload, (Message, Acknowledgment)):
        raw = b":" + payload.addressee.ljust(9).encode("ascii") + b":"
        reply = b"" if payload.reply_ack is None else b"}" + payload.reply_ack.encode()
        if isinstance(payload, Acknowledgment):
            if _special_message(payload.addressee, b""):
                raise CodecNotImplementedError("specialized addressee")
            verb = b"rej" if payload.rejected else b"ack"
            return raw + verb + payload.message_id.encode("ascii") + reply
        body = payload.text.encode("utf-8")
        if (
            payload.message_id is None
            and _messages.response(payload.addressee, body) is not None
        ):
            raise FieldError(
                "message text would be interpreted as a query response; use Response"
            )
        if _special_message(payload.addressee, body):
            raise CodecNotImplementedError("specialized message")
        if payload.message_id is not None:
            body += b"{" + payload.message_id.encode("ascii") + reply
        return raw + body
    if type(payload) in get_args(Payload):
        raise CodecNotImplementedError(f"{type(payload).__name__} encoding")
    raise TypeError("unsupported payload model")


def _wire_header(packet: Packet) -> Header:
    if isinstance(packet.payload, MicE):
        from ._mic_e import resolve_header

        return resolve_header(packet.header, packet.payload)
    return packet.header


def _serialize(
    packet: Packet, max_depth: int, depth: int, policy: EnvelopePolicy
) -> bytes:
    information = _encode_payload(
        packet.payload, packet.header, max_depth, depth, policy
    )
    return str(_wire_header(packet)).encode("ascii") + b":" + information


def _bound_depth(value: Packet | Payload, max_depth: int) -> None:
    """Count third-party wrappers iteratively, before any recursive traversal."""
    payload = value.payload if isinstance(value, Packet) else value
    depth = 0
    while isinstance(payload, ThirdParty) and isinstance(payload.packet, Packet):
        depth += 1
        if depth > max_depth:
            raise ResourceLimitError("third-party nesting limit reached")
        payload = payload.packet.payload


def _envelope_sizes(
    policy: EnvelopePolicy, information_bytes: int, line_bytes: int
) -> tuple[Diagnostic, ...]:
    """Measure the outer envelope, including canonical CRLF for line limits."""
    result = []
    if (
        policy.max_information_bytes is not None
        and information_bytes > policy.max_information_bytes
    ):
        result.append(
            Diagnostic(
                "nonconforming",
                f"information exceeds {policy.max_information_bytes} bytes",
                "$.payload",
            )
        )
    if (
        policy.max_tnc2_line_bytes is not None
        and line_bytes > policy.max_tnc2_line_bytes
    ):
        result.append(
            Diagnostic(
                "nonconforming",
                f"TNC2 line exceeds {policy.max_tnc2_line_bytes} bytes including CRLF",
                "$",
            )
        )
    return tuple(result)


def _findings(
    value: Packet | Payload, policy: EnvelopePolicy, max_depth: int
) -> tuple[Diagnostic, ...]:
    """Conformance findings, including the encoded outer envelope size."""
    findings = check(value, policy)
    if isinstance(value, Packet) and (
        policy.max_information_bytes is not None
        or policy.max_tnc2_line_bytes is not None
    ):
        try:
            header = _wire_header(value)
            information = _encode_payload(
                value.payload, value.header, max_depth, 0, policy
            )
        except (CodecNotImplementedError, ContextRequiredError, FieldError):
            return findings  # Reported elsewhere; there are no bytes to measure.
        line_bytes = len(str(header).encode("ascii")) + 1 + len(information) + 2
        findings = (*findings, *_envelope_sizes(policy, len(information), line_bytes))
    return findings


def _ready_to_send(
    value: Packet | Payload, policy: EnvelopePolicy, max_depth: int
) -> None:
    _bound_depth(value, max_depth)
    validate_tree(value)
    payload = value.payload if isinstance(value, Packet) else value
    if (
        isinstance(payload, m.NMEA)
        and payload.symbol is not None
        and not isinstance(value, Packet)
    ):
        raise ContextRequiredError(
            "NMEA symbol encoding needs the header; use serialize_packet"
        )
    _require_codecs(payload)
    findings = _findings(value, policy, max_depth)
    if findings:
        raise ConformanceError(findings)


def serialize_packet(
    packet: Packet,
    *,
    policy: EnvelopePolicy = _DEFAULT_POLICY,
    max_third_party_depth: int = 4,
) -> bytes:
    """Encode a packet for sending. Never replays original_wire.

    Every packet is validated first: ResourceLimitError for excessive
    third-party nesting, ModelError for invalid fields, CodecNotImplementedError
    for families without an encoder, and ConformanceError (with every finding)
    for anything outside APRS rules or the selected envelope policy. The default
    policy is APRS_IS(); pass RF() or a custom EnvelopePolicy as needed.
    """
    if not isinstance(packet, Packet):
        raise TypeError("serialize_packet requires a Packet; repair a Malformed first")
    options = _options(policy, "raise", "raise", max_third_party_depth)
    _bound_depth(packet, options.max_depth)
    packet = resolve_wire_forms(packet, options.policy)
    _ready_to_send(packet, options.policy, options.max_depth)
    return _serialize(packet, options.max_depth, 0, options.policy)


def serialize_payload(
    payload: Payload,
    *,
    policy: EnvelopePolicy = _DEFAULT_POLICY,
    max_third_party_depth: int = 4,
) -> bytes:
    """Encode an information field alone, with the same payload validation as packets.

    Mic-E destination bits are derived from the payload. To obtain the matching
    header too, use serialize_packet with Header(source). NMEA with an explicit
    symbol still needs header context.
    """
    if isinstance(payload, (Packet, Malformed)):
        raise TypeError("serialize_payload requires a payload model")
    options = _options(policy, "raise", "raise", max_third_party_depth)
    _bound_depth(payload, options.max_depth)
    payload = resolve_wire_forms(payload, options.policy)
    _ready_to_send(payload, options.policy, options.max_depth)
    return _encode_payload(payload, None, options.max_depth, 0, options.policy)


def check_packet(
    packet: Packet,
    *,
    policy: EnvelopePolicy = _DEFAULT_POLICY,
    max_third_party_depth: int = 4,
) -> tuple[Diagnostic, ...]:
    """Every conformance finding serialize_packet would raise, without raising.

    An empty result does not promise an encoder exists; validate_packet does.
    """
    if not isinstance(packet, Packet):
        raise TypeError("check_packet requires a Packet")
    options = _options(policy, "raise", "raise", max_third_party_depth)
    _bound_depth(packet, options.max_depth)
    validate_tree(packet)
    packet = resolve_wire_forms(packet, options.policy)
    return _findings(packet, options.policy, options.max_depth)


def validate_packet(
    packet: Packet,
    *,
    policy: EnvelopePolicy = _DEFAULT_POLICY,
    max_third_party_depth: int = 4,
) -> None:
    """Raise exactly as serialize_packet would; return None when it can be sent."""
    serialize_packet(packet, policy=policy, max_third_party_depth=max_third_party_depth)
