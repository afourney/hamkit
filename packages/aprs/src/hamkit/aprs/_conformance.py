# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""APRS conformance: rules a well-formed model can still break.

Received packets that break these rules still decode; each finding becomes a
nonconforming Diagnostic on the Packet. Serialization refuses to emit them, so
every packet is checked before it can be sent. Lengths are counted in encoded
UTF-8 bytes. UTF-8 free text (messages, bulletins, status and comments) follows
the APRS 1.2 proposed-draft guidance (aprs.org/aprs12/utf-8.txt), adopted for
compatibility rather than as a ratified requirement.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from typing import Any

from . import _extensions
from ._data import (
    Footprint,
    Measurement,
    NTSAddress,
    NTSHeader,
    NTSPhone,
    NTSRouting,
    NTSSignature,
    NTSText,
    Telemetry,
    TelemetryBits,
    TelemetryEquations,
    TelemetryParameters,
    TelemetryUnits,
    Weather,
)
from ._errors import CodecNotImplementedError, FieldError
from ._models import (
    Acknowledgment,
    AutoAnswer,
    Bulletin,
    Capabilities,
    Diagnostic,
    DirectStations,
    EnvelopeProfile,
    Header,
    HeardStation,
    Item,
    Message,
    MicE,
    NWSBulletin,
    Object,
    Packet,
    Position,
    Query,
    Status,
    Trace,
)
from ._validation import _fields, walk

Finding = tuple[str, str]
_Rule = Callable[[Any, EnvelopeProfile], Iterable[Finding]]
_RULES: dict[type, list[_Rule]] = {}


def _conformance(*classes: type) -> Callable[[_Rule], _Rule]:
    def register(rule: _Rule) -> _Rule:
        for cls in classes:
            _RULES.setdefault(cls, []).append(rule)
        return rule

    return register


_CACHE: dict[type, tuple[tuple[str, ...], tuple[_Rule, ...]]] = {}


def _plan(model: type) -> tuple[tuple[str, ...], tuple[_Rule, ...]]:
    """The free-text fields and conformance rules that apply to a model."""
    plan = _CACHE.get(model)
    if plan is None:
        free = tuple(f.name for f in _fields(model) if f.metadata.get("text") == "free")
        rules = tuple(rule for cls in model.__mro__ for rule in _RULES.get(cls, ()))
        plan = _CACHE[model] = (free, rules)
    return plan


def check(value: Any, profile: EnvelopeProfile = "monitor") -> tuple[Diagnostic, ...]:
    """Every conformance finding in a model graph, with JSON-style paths."""
    result = []
    for node, path in walk(value):
        # RF limits apply to the transmitted header, not third-party inner ones.
        node_profile = profile if path in ("$", "$.header") else "monitor"
        free, rules = _plan(type(node))
        for name in free:
            if _has_control(getattr(node, name)):
                result.append(
                    Diagnostic(
                        "nonconforming",
                        "text contains control characters",
                        f"{path}.{name}",
                    )
                )
        for rule in rules:
            for relative, message in rule(node, node_profile):
                result.append(Diagnostic("nonconforming", message, path + relative[1:]))
    return tuple(result)


def _has_control(text: str) -> bool:
    return any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in text)


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


def _text(
    name: str, text: str, limit: int | None, reserved: str = "|~"
) -> Iterator[Finding]:
    if limit is not None and _size(text) > limit:
        yield f"$.{name}", f"exceeds {limit} bytes"
    if any(c in reserved for c in text):
        yield f"$.{name}", f"contains a reserved character ({' '.join(reserved)})"


# Envelope ------------------------------------------------------------------

_RF_ADDRESS = re.compile(r"[A-Z0-9]{1,6}(?:-(?:[0-9]|1[0-5]))?")


@_conformance(Header)
def _header(v: Header, profile: EnvelopeProfile) -> Iterator[Finding]:
    if profile != "rf":
        return
    for name, address in (("source", v.source), ("destination", v.destination)):
        if not _RF_ADDRESS.fullmatch(address):
            yield f"$.{name}", "not a valid AX.25 address or SSID"
    for i, hop in enumerate(v.path):
        if not _RF_ADDRESS.fullmatch(hop.address):
            yield f"$.path[{i}].address", "not a valid AX.25 address or SSID"
    if len(v.path) > 8:
        yield "$.path", "RF paths have at most eight hops"


@_conformance(Packet)
def _packet(v: Packet, profile: EnvelopeProfile) -> Iterator[Finding]:
    payload = v.payload
    if isinstance(payload, Weather):
        yield from _weather_report(payload, "$.payload", positioned=False)
    if isinstance(payload, Telemetry) and payload.encoding not in (
        "classic",
        "compatibility",
    ):
        yield "$.payload.encoding", "comment and Mic-E telemetry need a position report"


# Status and messages -------------------------------------------------------


@_conformance(Status)
def _status(v: Status, profile: EnvelopeProfile) -> Iterator[Finding]:
    yield from _text("text", v.text, None)
    size = _size(v.text) + (7 if v.timestamp is not None else 0)
    if v.grid is not None:
        if v.text and not v.text.startswith(" "):
            yield "$.text", "grid status text begins with a space"
        size += len(v.grid.locator) + 2
    if v.beam is not None:
        size += 3
    if size > 62:
        yield "$.text", "status exceeds 62 bytes"


@_conformance(Message)
def _message(v: Message, profile: EnvelopeProfile) -> Iterator[Finding]:
    yield from _text("text", v.text, 67)
    reply = v.reply_ack
    if reply is not None and v.message_id and len(v.message_id) + 1 + len(reply) > 5:
        yield "$.reply_ack", "reply-ack ID and ack exceed five characters"


@_conformance(Acknowledgment)
def _ack(v: Acknowledgment, profile: EnvelopeProfile) -> Iterator[Finding]:
    if v.reply_ack is not None and len(v.message_id) + 1 + len(v.reply_ack) > 5:
        yield "$.reply_ack", "reply-ack ID and ack exceed five characters"


@_conformance(AutoAnswer)
def _auto_answer(v: AutoAnswer, profile: EnvelopeProfile) -> Iterator[Finding]:
    suffix = 1 + len(v.previous_ack) if v.previous_ack is not None else 0
    yield from _text("text", v.text, 67 - 3 - suffix)
    if v.previous_ack is not None and len(v.previous_ack) > 2:
        yield "$.previous_ack", "auto-answer acknowledgments have two characters"


@_conformance(Bulletin, NWSBulletin)
def _bulletin(v: Any, profile: EnvelopeProfile) -> Iterator[Finding]:
    yield from _text("text", v.text, 67)


_CHANNEL_LIMITS = (7, 6, 5, 5, 4, 5, 4, 3, 3, 3, 2, 2, 2)


@_conformance(TelemetryParameters, TelemetryUnits)
def _labels(v: Any, profile: EnvelopeProfile) -> Iterator[Finding]:
    if not 1 <= len(v.channels) <= len(_CHANNEL_LIMITS):
        yield "$.channels", "requires one to thirteen channels"
    for i, (channel, limit) in enumerate(zip(v.channels, _CHANNEL_LIMITS)):
        if channel is not None:
            yield from _text(f"channels[{i}]", channel, limit, "|~{")


@_conformance(TelemetryEquations)
def _equations(v: TelemetryEquations, profile: EnvelopeProfile) -> Iterator[Finding]:
    if not 1 <= len(v.coefficients) <= 5:
        yield "$.coefficients", "requires one to five channels"


@_conformance(TelemetryBits)
def _bits(v: TelemetryBits, profile: EnvelopeProfile) -> Iterator[Finding]:
    yield from _text("project_title", v.project_title, 23, "|~{")


def _nts_values(v: Any) -> list[str]:
    if isinstance(v, NTSHeader):
        return [
            v.number,
            v.precedence,
            v.handling or "",
            v.originator,
            v.check,
            v.place,
            v.time or "",
            v.date,
        ]
    if isinstance(v, NTSAddress):
        return list(v.lines)
    if isinstance(v, NTSRouting):
        return [v.received_from, v.received_at, v.sent_to, v.sent_at]
    return [v.number if isinstance(v, NTSPhone) else v.text]


@_conformance(NTSHeader, NTSAddress, NTSPhone, NTSText, NTSSignature, NTSRouting)
def _nts(v: Any, profile: EnvelopeProfile) -> Iterator[Finding]:
    if isinstance(v, NTSHeader):
        if not re.fullmatch(r"(?:SVC )?[1-9][0-9]*", v.number):
            yield "$.number", "requires a positive number, optionally after SVC"
        if not re.fullmatch(r"(?:TEST )?(?:R|W|P|EMERGENCY)", v.precedence):
            yield "$.precedence", "requires an ARRL precedence"
        for name in ("originator", "check", "place", "date"):
            if not getattr(v, name).strip():
                yield f"$.{name}", "required preamble value is empty"
        if not re.fullmatch(r"(?:ARL ?)?[0-9]+", v.check):
            yield "$.check", "requires a word count, optionally after ARL"
    if isinstance(v, NTSAddress) and not any(x.strip() for x in v.lines):
        yield "$.lines", "address must identify a recipient"
    if isinstance(v, NTSSignature) and not v.text.strip():
        yield "$.text", "signature must identify the originating party"
    yield from _text("record", "\\".join(_nts_values(v)), 64, "{|~")


# Queries and responses -----------------------------------------------------

_GENERAL_QUERIES = {"APRS", "IGATE", "WX"}
_DIRECTED_QUERIES = {
    "APRSD",
    "APRSH",
    "APRSM",
    "APRSO",
    "APRSP",
    "APRSS",
    "APRST",
    "PING",
}


@_conformance(Query)
def _query(v: Query, profile: EnvelopeProfile) -> Iterator[Finding]:
    if v.name in _GENERAL_QUERIES and v.addressee is not None:
        yield "$.addressee", "general queries have no addressee"
    if v.name in _DIRECTED_QUERIES and v.addressee is None:
        yield "$.addressee", "directed queries require an addressee"
    if v.footprint is not None and (v.name != "APRS" or v.addressee is not None):
        yield "$.footprint", "footprints apply to general APRS queries"
    if v.heard_station is not None and v.name != "APRSH":
        yield "$.heard_station", "a heard-station operand applies to APRSH"
    known = _GENERAL_QUERIES | _DIRECTED_QUERIES
    if v.arguments and (
        v.name in known or v.footprint is not None or v.heard_station is not None
    ):
        yield "$.arguments", "raw arguments apply only to unknown queries"


@_conformance(Footprint)
def _footprint(v: Footprint, profile: EnvelopeProfile) -> Iterator[Finding]:
    if v.radius_miles > 9999 or v.radius_miles != int(v.radius_miles):
        yield "$.radius_miles", "requires whole miles in 0..9999"


@_conformance(DirectStations)
def _direct(v: DirectStations, profile: EnvelopeProfile) -> Iterator[Finding]:
    yield from _text("stations", "Directs= " + " ".join(v.stations), 67)


@_conformance(HeardStation)
def _heard(v: HeardStation, profile: EnvelopeProfile) -> Iterator[Finding]:
    if len(v.counts) != 8:
        yield "$.counts", "requires eight hourly slots (None when unavailable)"
    counts = " ".join("." if x is None else str(x) for x in v.counts)
    yield from _text("counts", f"{v.station} HEARD: {counts}", 67)


@_conformance(Trace)
def _trace(v: Trace, profile: EnvelopeProfile) -> Iterator[Finding]:
    yield from _text("header", str(v.header) + ":", 67)


@_conformance(Capabilities)
def _capabilities(v: Capabilities, profile: EnvelopeProfile) -> Iterator[Finding]:
    if not v.tokens:
        yield "$.tokens", "a capabilities report requires at least one token"
    for i, token in enumerate(v.tokens):
        if token.name in ("MSG_CNT", "LOC_CNT") and (
            token.value is None or not token.value.isdigit()
        ):
            yield f"$.tokens[{i}].value", "counters require a decimal integer"


# Places --------------------------------------------------------------------


@_conformance(Item)
def _item(v: Item, profile: EnvelopeProfile) -> Iterator[Finding]:
    if len(v.name) < 3:
        yield "$.name", "item names have at least three characters"


@_conformance(Position, Object, Item)
def _position(v: Position, profile: EnvelopeProfile) -> Iterator[Finding]:
    """The encoded tail must read back as the same extensions and comment."""
    if any(_located(v, profile)):
        return  # Report structural slot errors without secondary comment errors.
    try:
        extensions = v.extensions
        if v.compression is not None:
            from ._position_codec import compressed_bytes

            _, extensions = compressed_bytes(v)
        prefix = _extensions.write(extensions, v.symbol)
    except CodecNotImplementedError:
        return
    except _extensions.Unrepresentable as exc:
        yield exc.path, exc.message
        return
    except FieldError as exc:
        yield "$.extensions", str(exc)
        return
    comment = v.comment.encode("utf-8")
    if len(prefix) + len(comment) > 43:
        yield "$.comment", "extensions and comment exceed 43 bytes"
    try:
        expected, _ = _extensions.read(prefix, v.symbol)
        actual, rest = _extensions.read(prefix + comment, v.symbol)
    except (CodecNotImplementedError, FieldError):
        yield "$.comment", "contains extension syntax this version cannot decode"
        return
    if (actual, rest) != (expected, comment):
        yield "$.comment", "would be read back as a data extension"
    else:
        yield from _extensions.lookalikes(actual, rest, v.symbol)


@_conformance(Position, Object, Item, MicE)
def _located(v: Any, profile: EnvelopeProfile) -> Iterator[Finding]:
    e = v.extensions
    symbol = (v.symbol.table_id, v.symbol.code)
    primary = [
        name
        for name in ("motion", "phg", "range", "signal", "area")
        if getattr(e, name) is not None
    ]
    if len(primary) > 1:
        yield f"$.extensions.{primary[-1]}", "shares the data-extension slot"
    if e.bearing is not None and e.motion is None:
        yield "$.extensions.bearing", "DF bearing follows a course/speed extension"
    if e.storm is not None:
        if symbol != ("/" if e.storm.predicted else "\\", "@"):
            yield "$.symbol", "storm symbol must agree with predicted/current"
        if e.motion is None:
            yield "$.extensions.motion", "storm reports require direction and speed"
    for name, required in (
        ("bearing", ("/", "\\")),
        ("signal", ("/", "\\")),
        ("area", ("\\", "l")),
        ("signpost", ("\\", "m")),
    ):
        if getattr(e, name) is not None and symbol != required:
            yield "$.symbol", f"{name} requires symbol {''.join(required)}"
    if e.weather is not None:
        if v.symbol.code not in "_W":
            yield "$.symbol", "located weather uses the weather symbol"
        if primary or e.bearing is not None:
            yield "$.extensions.weather", "weather uses the wind extension slot"
        yield from _weather_report(e.weather, "$.extensions.weather", positioned=True)
    if e.telemetry is not None:
        allowed = (
            ("mic_e_hex", "mic_e_binary", "base91_comment")
            if isinstance(v, MicE)
            else ("base91_comment",)
        )
        if e.telemetry.encoding not in allowed:
            yield "$.extensions.telemetry.encoding", "requires " + " or ".join(allowed)
    if isinstance(v, MicE):
        if e.motion is None:
            yield "$.extensions.motion", "Mic-E always carries course and speed"
        return
    if v.compression is not None:
        yield from _compressed(v)


def _compressed(v: Any) -> Iterator[Finding]:
    e, csT = v.extensions, v.compression
    if any(getattr(e, n) is not None for n in ("phg", "signal", "area", "bearing")):
        yield "$.extensions", "not available in the compressed position layout"
    altitude = e.altitude is not None and e.altitude.encoding == "compressed"
    if csT.ignored:
        if e.motion is not None or e.range is not None or altitude:
            yield "$.compression", "ignored csT cannot carry motion, range or altitude"
        return
    if not altitude and e.motion is None and e.range is None and e.weather is None:
        yield "$.compression", "csT requires motion, range, altitude or weather wind"
    if (csT.nmea_source == "GGA") != altitude:
        yield "$.compression", "compressed altitude and the GGA source go together"
    if altitude and (e.motion is not None or e.range is not None):
        yield "$.compression", "compressed altitude shares the motion/range slot"


# Weather and telemetry -----------------------------------------------------


def _weather_report(w: Weather, path: str, positioned: bool) -> Iterator[Finding]:
    if positioned and w.timestamp is not None:
        yield f"{path}.timestamp", "located weather uses the report timestamp"
    if not positioned and w.timestamp is None:
        yield f"{path}.timestamp", "positionless weather requires an MDHM timestamp"
    for name in ("wind_direction", "wind_speed", "gust", "temperature"):
        if getattr(w, name) is None:
            yield (
                f"{path}.{name}",
                "required report slot; use Measurement(None, unit) if unavailable",
            )
    if not positioned and w.snow_24h is not None:
        yield f"{path}.snow_24h", "positionless reports cannot carry snow"


@_conformance(Weather)
def _weather(v: Weather, profile: EnvelopeProfile) -> Iterator[Finding]:
    for name in (
        "wind_direction",
        "wind_speed",
        "gust",
        "temperature",
        "humidity",
        "pressure",
        "rain_1h",
        "rain_24h",
        "rain_since_midnight",
        "snow_24h",
        "luminosity",
        "rain_counter",
    ):
        reading: Measurement | None = getattr(v, name)
        if reading is None or reading.value is None:
            continue
        low = {"celsius": -273.15, "fahrenheit": -459.67}.get(reading.unit, 0)
        high = {"humidity": 100, "wind_direction": 360}.get(name, float("inf"))
        if not low <= reading.value <= high:
            yield f"$.{name}.value", "reading outside the quantity's range"
    if v.software_code is not None and len(v.software_code) != 1:
        yield "$.software_code", "requires one character"
    if v.device_code is not None and not 2 <= len(v.device_code) <= 4:
        yield "$.device_code", "requires two to four characters"


@_conformance(Telemetry)
def _telemetry(v: Telemetry, profile: EnvelopeProfile) -> Iterator[Finding]:
    def analog(low: int, high: int, missing: tuple[int, ...] = ()) -> Iterator[Finding]:
        for i, value in enumerate(v.analog):
            if i in missing and value is None:
                continue
            if (
                value is None
                or not float(value).is_integer()
                or not low <= value <= high
            ):
                yield f"$.analog[{i}]", f"requires an integer in {low}..{high}"

    if v.encoding == "classic":
        if len(v.analog) != 5:
            yield "$.analog", "classic telemetry has five analog channels"
        if len(v.digital) != 8 or None in v.digital:
            yield "$.digital", "classic telemetry has eight binary channels"
        yield from analog(0, 255)
        if v.sequence != "MIC" and not (
            isinstance(v.sequence, int) and v.sequence <= 999
        ):
            yield "$.sequence", "classic telemetry requires 0..999 or MIC"
    elif v.encoding in ("mic_e_hex", "mic_e_binary"):
        counts = (2, 5) if v.encoding == "mic_e_hex" else (5,)
        if len(v.analog) not in counts:
            yield "$.analog", f"{v.encoding} carries {' or '.join(map(str, counts))} channels"
        missing = (
            (1, 3, 4)
            if v.encoding == "mic_e_hex"
            and len(v.analog) == 5
            and all(v.analog[i] is None for i in (1, 3, 4))
            else ()
        )
        yield from analog(0, 255, missing)
        if v.digital:
            yield "$.digital", "Mic-E telemetry has no digital channels"
        if v.sequence is not None:
            yield "$.sequence", "Mic-E telemetry has no sequence"
        if v.comment:
            yield "$.comment", "Mic-E telemetry replaces the status text"
    elif v.encoding == "base91_comment":
        if not (isinstance(v.sequence, int) and v.sequence <= 8280):
            yield "$.sequence", "base91 telemetry requires a sequence in 0..8280"
        if not v.analog:
            yield "$.analog", "base91 telemetry requires an analog channel"
        yield from analog(0, 8280)
        if v.digital and (
            len(v.analog) != 5 or len(v.digital) != 8 or None in v.digital
        ):
            yield "$.digital", "eight binary channels follow five analog channels"
        if v.comment:
            yield "$.comment", "base91 telemetry uses the report comment"
    elif not v.analog and not v.digital:
        yield "$.analog", "at least one channel is required"
