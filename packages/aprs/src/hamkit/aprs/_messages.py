# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Addressed APRS applications, queries, status, and telemetry definitions."""

from __future__ import annotations

import re
from typing import Any, cast

from . import _data as d
from . import _models as m
from ._errors import APRSError, FieldError
from ._fields import decode_timestamp, encode_timestamp
from ._text import free_text, token


def query(body: bytes, address: str | None = None) -> m.Query:
    match = re.match(rb"\?([A-Z][A-Z0-9]*)(\??)(.*)", body, re.DOTALL)
    if not match:
        raise FieldError("invalid query")
    name = match[1].decode()
    rest = match[3]
    footprint = None
    heard = None
    if address is None and name == "APRS" and rest:
        values = rest.strip().split(b",")
        if len(values) == 3:
            try:
                footprint = d.Footprint(
                    d.Coordinates(float(values[0]), float(values[1])), float(values[2])
                )
                rest = b""
            except ValueError as exc:
                raise FieldError("invalid query footprint") from exc
    elif name == "APRSH" and rest:
        heard = token(rest.strip(), "$.heard_station")
        rest = b""
    return m.Query(
        name,
        addressee=address,
        footprint=footprint,
        heard_station=heard,
        arguments=rest,
    )


def status(body: bytes, diagnostics: list) -> m.Status:
    timestamp = None
    grid = None
    symbol = None
    beam = None
    if re.match(rb"\d{6}z", body):
        timestamp = decode_timestamp(body[:7])
        body = body[7:]
    else:
        match = re.match(
            rb"([A-Ra-r]{2}\d{2}(?:[A-Xa-x]{2})?)([/\\0-9A-Z])([!-~])", body
        )
        if match:
            grid = d.Grid(match[1].decode().upper())
            symbol = d.Symbol(match[2].decode(), match[3].decode())
            body = body[match.end() :]
    match = re.search(rb"\^([0-9A-Z])([0-K])$", body)
    if match:
        heading = int(chr(match[1][0]), 36) * 10
        beam = d.Beam(heading, 10 * (match[2][0] - 48) ** 2, raw=match[0])
        body = body[: match.start()]
    return m.Status(
        free_text(body, "$.text", diagnostics),
        timestamp=timestamp,
        grid=grid,
        symbol=symbol,
        beam=beam,
    )


def definition(address: str, body: bytes) -> m.TelemetryDefinition:
    tag = body[:5]
    values = token(body[5:], "$.definition").split(",")
    value: d.TelemetryDefinitionValue
    if tag in (b"PARM.", b"UNIT."):
        value = (d.TelemetryParameters if tag == b"PARM." else d.TelemetryUnits)(
            tuple(v or None for v in values) + (None,) * max(0, 13 - len(values))
        )
    elif tag == b"EQNS.":
        if len(values) % 3:
            raise FieldError("EQNS requires complete triples")
        triples = []
        for i in range(0, len(values), 3):
            v = values[i : i + 3]
            try:
                triples.append(
                    None if v == ["", "", ""] else d.Calibration(*map(float, v))
                )
            except ValueError as exc:
                raise FieldError("invalid EQNS coefficient") from exc
        value = d.TelemetryEquations(tuple(triples))
    else:
        if not re.fullmatch("[01]{8}", values[0]):
            raise FieldError("BITS requires eight bits")
        value = d.TelemetryBits(
            cast(Any, tuple(v == "1" for v in values[0])),
            project_title=",".join(values[1:]),
        )
    return m.TelemetryDefinition(address, value)


def specialized(address: str, body: bytes, diagnostics: list):
    if body.startswith((b"PARM.", b"UNIT.", b"EQNS.", b"BITS.")):
        return definition(address, body)
    if body.startswith(b"?"):
        return query(body, address)
    if body.startswith(b"AA:"):
        text, sep, ack = body[3:].rpartition(b"}")
        return m.AutoAnswer(
            address,
            free_text(text if sep else body[3:], "$.text", diagnostics),
            previous_ack=token(ack, "$.previous_ack") if sep else None,
        )
    if address.startswith("BLN"):
        if len(address) < 4:
            raise FieldError("bulletin requires identifier")
        return m.Bulletin(
            address[3],
            free_text(body, "$.text", diagnostics),
            group=address[4:] or None,
        )
    if address.startswith("NWS-"):
        text, sep, ref = body.partition(b"{")
        return m.NWSBulletin(
            address,
            free_text(text, "$.text", diagnostics),
            reference_id=token(ref, "$.reference_id") if sep else None,
        )
    if re.match(rb"N[#AP1-6SR]\\", body):
        content, sep, identifier = body.partition(b"{")
        values = token(content, "$.record").split("\\")
        tag = values.pop(0)
        if values and values[-1] == "":
            values.pop()
        record: d.NTSRecord
        try:
            if tag == "N#":
                if len(values) != 8:
                    raise ValueError("NTS header requires eight fields")
                record = d.NTSHeader(
                    **dict(
                        zip(
                            (
                                "number",
                                "precedence",
                                "handling",
                                "originator",
                                "check",
                                "place",
                                "time",
                                "date",
                            ),
                            values,
                        )
                    )
                )
            elif tag == "NA":
                record = d.NTSAddress(cast(Any, tuple(values)))
            elif tag == "NP":
                record = d.NTSPhone(*values)
            elif tag == "NS":
                record = d.NTSSignature(*values)
            elif tag == "NR":
                if len(values) != 4:
                    raise ValueError("NTS routing requires four fields")
                record = d.NTSRouting(
                    **dict(
                        zip(
                            ("received_from", "received_at", "sent_to", "sent_at"),
                            values,
                        )
                    )
                )
            else:
                record = d.NTSText(cast(Any, int(tag[1])), *values)
        except (ValueError, TypeError) as exc:
            raise FieldError("invalid NTS record") from exc
        return m.Radiogram(
            address,
            record,
            message_id=token(identifier, "$.message_id") if sep else None,
        )
    return None


def response(address: str, body: bytes):
    """Recognize the three documented directed-query response grammars.

    Text that does not match a grammar completely is an ordinary message.
    """
    try:
        if re.fullmatch(rb"Directs=(?: [A-Za-z0-9-]{1,9})+", body):
            return m.Response(
                address,
                m.DirectStations(tuple(body[9:].decode("ascii").split())),
            )
        match = re.fullmatch(
            rb"([A-Za-z0-9-]+) HEARD: ((?:[0-9]+|\.)(?: (?:[0-9]+|\.)){7})", body
        )
        if match:
            return m.Response(
                address,
                m.HeardStation(
                    match[1].decode(),
                    tuple(None if c == b"." else int(c) for c in match[2].split()),
                ),
            )
        if re.fullmatch(rb"[A-Za-z0-9-]+>[A-Za-z0-9,*-]+:", body):
            return m.Response(address, m.Trace(m.Header.parse(body[:-1].decode())))
    except APRSError:
        pass
    return None


def telemetry(raw: bytes, diagnostics: list) -> d.Telemetry:
    match = re.match(rb"T#(MIC|\d+),?", raw)
    if not match:
        raise FieldError("invalid telemetry sequence")
    sequence = match[1]
    if len(sequence) > 32:
        raise FieldError("telemetry sequence exceeds numeric field budget")
    fields = raw[match.end() :].split(b",", 5)
    if len(fields) != 6:
        raise FieldError("telemetry requires five analog channels and digital bits")
    analog = []
    try:
        for value in fields[:5]:
            analog.append(None if not value else float(value))
    except ValueError as exc:
        raise FieldError("invalid telemetry channel") from exc
    bits = fields[5][:8]
    if len(bits) != 8 or any(v not in b"01" for v in bits):
        raise FieldError("telemetry requires eight binary digits")
    return d.Telemetry(
        tuple(analog),
        tuple(v == 49 for v in bits),
        sequence="MIC" if sequence == b"MIC" else int(sequence),
        sequence_raw=sequence,
        comment=free_text(fields[5][8:], "$.comment", diagnostics),
    )


def write(payload):
    p = payload
    if isinstance(p, m.Status):
        raw = b">" + (encode_timestamp(p.timestamp) if p.timestamp else b"")
        if p.grid:
            raw += (
                p.grid.locator.encode()
                + p.symbol.table_id.encode()
                + p.symbol.code.encode()
            )
        raw += p.text.encode()
        if p.beam:
            h = round(p.beam.heading_deg / 10) % 36
            power = round((p.beam.erp_w / 10) ** 0.5)
            if (
                not 0 <= h <= 35
                or not 0 <= power <= 27
                or abs(power**2 * 10 - p.beam.erp_w) > 1e-6
            ):
                raise FieldError("beam/ERP not representable")
            raw += (
                b"^"
                + b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[h : h + 1]
                + bytes([48 + power])
            )
        decoded = status(raw[1:], [])
        if (
            decoded.text,
            decoded.timestamp,
            decoded.grid,
            decoded.symbol,
            bool(decoded.beam),
        ) != (p.text, p.timestamp, p.grid, p.symbol, bool(p.beam)):
            raise FieldError("status text would be interpreted as structured fields")
        return raw
    if isinstance(p, m.Query):
        raw = (
            b"?"
            + p.name.encode()
            + (b"?" if p.addressee is None or p.name == "PING" else b"")
        )
        if p.footprint:
            raw += f" {p.footprint.center.latitude_deg:g},{p.footprint.center.longitude_deg:g},{p.footprint.radius_miles:g}".encode()
        if p.heard_station:
            raw += b" " + p.heard_station.encode()
        raw += p.arguments
        return (
            b":" + p.addressee.ljust(9).encode() + b":" if p.addressee else b""
        ) + raw
    if isinstance(p, m.Capabilities):
        return b"<" + b",".join(
            c.name.encode() + (b"=" + c.value.encode() if c.value is not None else b"")
            for c in p.tokens
        )
    if isinstance(p, d.Telemetry):
        if p.encoding not in ("classic", "compatibility"):
            raise FieldError("telemetry encoding requires an enclosing position")
        seq = b"MIC" if p.sequence in (None, "MIC") else f"{p.sequence:03d}".encode()
        values = b",".join(
            (
                b""
                if v is None
                else (f"{int(v):03d}" if v == int(v) else f"{v:g}").encode()
            )
            for v in p.analog
        )
        return (
            b"T#"
            + seq
            + b","
            + values
            + b","
            + bytes(49 if v else 48 for v in p.digital)
            + p.comment.encode()
        )
    if isinstance(p, m.Bulletin):
        address = "BLN" + p.identifier + (p.group or "")
        body = p.text.encode()
    elif isinstance(p, m.AutoAnswer):
        address = p.addressee
        body = (
            b"AA:"
            + p.text.encode()
            + (b"}" + p.previous_ack.encode() if p.previous_ack else b"")
        )
    elif isinstance(p, m.NWSBulletin):
        address = p.addressee
        body = p.text.encode() + (
            b"{" + p.reference_id.encode() if p.reference_id else b""
        )
    elif isinstance(p, m.TelemetryDefinition):
        address = p.addressee
        v = p.definition
        if isinstance(v, (d.TelemetryParameters, d.TelemetryUnits)):
            body = (
                b"PARM." if isinstance(v, d.TelemetryParameters) else b"UNIT."
            ) + ",".join(x or "" for x in v.channels).encode()
        elif isinstance(v, d.TelemetryEquations):
            body = (
                b"EQNS."
                + ",".join(
                    ",," if x is None else ",".join(f"{a:g}" for a in (x.a, x.b, x.c))
                    for x in v.coefficients
                ).encode()
            )
        else:
            body = (
                b"BITS."
                + bytes(49 if x else 48 for x in v.sense)
                + b","
                + v.project_title.encode()
            )
    elif isinstance(p, m.Radiogram):
        address = p.addressee
        v = p.record
        if isinstance(v, d.NTSHeader):
            tag = "N#"
            values = [
                v.number,
                v.precedence,
                v.handling or "",
                v.originator,
                v.check,
                v.place,
                v.time or "",
                v.date,
            ]
        elif isinstance(v, d.NTSAddress):
            tag = "NA"
            values = v.lines
        elif isinstance(v, d.NTSPhone):
            tag = "NP"
            values = [v.number]
        elif isinstance(v, d.NTSText):
            tag = f"N{v.line}"
            values = [v.text]
        elif isinstance(v, d.NTSSignature):
            tag = "NS"
            values = [v.text]
        else:
            tag = "NR"
            values = [v.received_from, v.received_at, v.sent_to, v.sent_at]
        body = (tag + "\\" + "\\".join(values)).encode() + (
            b"{" + p.message_id.encode() if p.message_id else b""
        )
    elif isinstance(p, m.Response):
        address = p.addressee
        v = p.response
        if isinstance(v, m.DirectStations):
            body = ("Directs= " + " ".join(v.stations)).encode()
        elif isinstance(v, m.HeardStation):
            body = (
                v.station
                + " HEARD: "
                + " ".join("." if c is None else str(c) for c in v.counts)
            ).encode()
        else:
            body = str(v.header).encode() + b":"
    else:
        return None
    return b":" + address.ljust(9).encode() + b":" + body
