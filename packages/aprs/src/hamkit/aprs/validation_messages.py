# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""APRS101 chapters 14–16 and APRS1.1 reply-ack construction constraints."""
from __future__ import annotations

import re
from typing import Any

from .model_validation import ModelError


def validate_messages(v: Any, path: str) -> None:
    """Validate message-family semantics independently of wire codec availability."""
    name = type(v).__name__

    def fail(field: str, reason: str) -> None:
        raise ModelError(f"{path}.{field}", reason)

    def text(field: str, value: str, maximum: int, forbidden: str = "|~") -> None:
        if len(value) > maximum or any(c in forbidden for c in value):
            fail(field, f"requires at most {maximum} characters without {forbidden!r}")

    def station(field: str, value: str) -> None:
        if not 1 <= len(value) <= 9 or any(c in " :>,*" for c in value):
            fail(field, "requires a nonempty station token of at most nine characters")

    # The extension occupies the original five-character line-number slot.
    if name == "ReplyAck" and len(v.message_number) + 1 + len(v.previous_ack or "") > 5:
        fail("previous_ack", "combined reply-ack identifier exceeds five characters")
    if (
        name in ("Message", "Acknowledgment")
        and v.reply_ack is not None
        and v.message_id is not None
        and v.message_id != v.reply_ack.message_number
    ):
        fail("message_id", "must agree with reply_ack.message_number")
    if name == "Status":
        text("text", v.text, 62)
        if (v.grid is None) != (v.symbol is None):
            fail("grid", "grid and symbol must be supplied together")
        size = len(v.text) + (7 if v.timestamp is not None else 0)
        if v.grid is not None:
            if v.timestamp is not None:
                fail("timestamp", "grid status cannot include a timestamp")
            if v.text and not v.text.startswith(" "):
                fail("text", "grid status text must begin with a space")
            size += len(v.grid.locator) + 2
        if v.beam is not None:
            size += 3
        if size > 62:
            fail("text", "complete status body exceeds 62 characters")
    if name == "AutoAnswer":
        # text is the message body; AA: and the optional acknowledgment are framing.
        suffix = 1 + len(v.previous_ack) if v.previous_ack is not None else 0
        text("text", v.text, 67 - 3 - suffix, "{|~")
        if v.previous_ack is not None and len(v.previous_ack) > 2:
            fail("previous_ack", "auto-answer acknowledgment exceeds two characters")
    if name == "Bulletin":
        pattern = r"[A-Z]" if v.announcement else r"[0-9]"
        if not re.fullmatch(pattern, v.identifier):
            fail(
                "identifier",
                "requires one uppercase announcement letter or bulletin digit",
            )
        if v.group is not None:
            if v.announcement:
                fail("group", "group bulletins require a digit identifier")
            if not 1 <= len(v.group) <= 5 or ":" in v.group or v.group.endswith(" "):
                fail("group", "requires 1..5 unpadded characters without colon")
        text("text", v.text, 67)
    if name == "NWSBulletin":
        if not v.addressee.startswith("NWS-") or len(v.addressee) <= 4:
            fail("addressee", "requires NWS- followed by an application address")
        text("text", v.text, 67)
        if v.reference_id is not None and not re.fullmatch(
            r"[A-Za-z0-9]{1,5}", v.reference_id
        ):
            fail("reference_id", "requires 1..5 alphanumeric characters")
    if name in ("NTSHeader", "Address", "Phone", "Text", "Signature", "Routing"):
        if name == "NTSHeader":
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
            if not re.fullmatch(r"(?:SVC )?[1-9][0-9]*", v.number):
                fail("number", "requires a positive number, optionally prefixed by SVC")
            if not re.fullmatch(r"(?:TEST )?(?:R|W|P|EMERGENCY)", v.precedence):
                fail(
                    "precedence",
                    "requires an ARRL precedence, optionally prefixed by TEST",
                )
            for field in ("originator", "check", "place", "date"):
                if not getattr(v, field).strip():
                    fail(field, "required preamble value cannot be empty")
            if not re.fullmatch(r"(?:ARL ?)?[0-9]+", v.check):
                fail("check", "requires a word count, optionally prefixed by ARL")
        elif name == "Address":
            values = list(v.lines)
            if not any(x.strip() for x in values):
                fail("lines", "address must identify a recipient")
        elif name == "Routing":
            # Blank not-yet-known routing slots are meaningful during handling.
            values = [v.received_from, v.received_at, v.sent_to, v.sent_at]
        else:
            field = "number" if name == "Phone" else "text"
            values = [getattr(v, field)]
            if name == "Signature" and not v.text.strip():
                fail("text", "signature must identify the originating party")
        body = "\\".join(values)
        if any("\\" in x for x in values):
            fail("record", "NTS values cannot contain the backslash separator")
        text("record", body, 64, "{|~")
    if name == "Footprint" and (
        v.radius_miles > 9999 or v.radius_miles != int(v.radius_miles)
    ):
        fail("radius_miles", "requires whole miles in 0..9999")
    if name == "Capability":
        if any(c in " ,=" for c in v.name):
            fail("name", "capability token cannot contain spaces, comma or equals")
        if v.value is not None and "," in v.value:
            fail("value", "capability value cannot contain comma")
        if v.name in ("MSG_CNT", "LOC_CNT") and (
            v.value is None or not re.fullmatch(r"[0-9]+", v.value)
        ):
            fail("value", "counter capability requires a nonnegative decimal integer")
    if name == "Capabilities" and not v.tokens:
        fail("tokens", "complete capabilities report requires at least one token")
    if name == "Query":
        if not re.fullmatch(r"[A-Z][A-Z0-9]*", v.name):
            fail(
                "name", "requires an uppercase query token without framing punctuation"
            )
        if v.message_id is not None:
            fail("message_id", "queries do not carry message identifiers")
        general = {"APRS", "IGATE", "WX"}
        directed = {
            "APRSD",
            "APRSH",
            "APRSM",
            "APRSO",
            "APRSP",
            "APRSS",
            "APRST",
            "PING",
        }
        if v.name in general and v.addressee is not None:
            fail("addressee", "general query cannot have an addressee")
        if v.name in directed and v.addressee is None:
            fail("addressee", "directed query requires an addressee")
        if v.footprint is not None and (v.name != "APRS" or v.addressee is not None):
            fail("footprint", "footprint is defined for general APRS queries")
        if v.heard_station is not None:
            if v.name != "APRSH":
                fail("heard_station", "heard-station operand is defined for APRSH")
            station("heard_station", v.heard_station)
        if v.arguments and (
            v.name in general | directed
            or v.footprint is not None
            or v.heard_station is not None
        ):
            fail("arguments", "raw arguments are only available for unknown queries")
    if name == "DirectStations":
        for i, s in enumerate(v.stations):
            station(f"stations[{i}]", s)
        text("stations", "Directs= " + " ".join(v.stations), 67)
    if name == "HeardStation":
        station("station", v.station)
        if len(v.counts) != 8:
            fail(
                "counts", "requires eight hourly slots; use None for unavailable hours"
            )
        text(
            "counts",
            v.station
            + " HEARD: "
            + " ".join("." if x is None else str(x) for x in v.counts),
            67,
        )
    if name == "Trace":
        h = v.header
        route = ",".join(hop.address + ("*" if hop.repeated else "") for hop in h.path)
        body = h.source + ">" + h.destination + ("," + route if route else "") + ":"
        text("header", body, 67)
