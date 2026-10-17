# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Best-effort extraction into ordinary JSON data, never partially valid models."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ._errors import APRSError
from ._fields import decode_coordinate
from ._models import Diagnostic
from ._text import free_text, token


def _timestamp(raw: bytes) -> dict[str, object]:
    # Retain independently readable components; absence is never replaced by zero.
    data: dict[str, object] = {}
    if len(raw) == 7 and raw[-1:] in (b"z", b"/", b"h"):
        hms = raw[-1:] == b"h"
        data["kind"] = (
            "hms_utc" if hms else "dhm_utc" if raw[-1:] == b"z" else "dhm_local"
        )
        for key, segment, low, high in (
            ("hour" if hms else "day", raw[:2], 0 if hms else 1, 23 if hms else 31),
            ("minute" if hms else "hour", raw[2:4], 0, 59 if hms else 23),
            ("second" if hms else "minute", raw[4:6], 0, 59),
        ):
            if segment.isdigit() and low <= int(segment) <= high:
                data[key] = int(segment)
    return data


def payload_data(raw: bytes) -> tuple[dict[str, object], list[Diagnostic]]:
    """Recover implemented-family components independently after a decode failure."""
    data: dict[str, object] = {}
    diagnostics: list[Diagnostic] = []
    ignored: list[Diagnostic] = []  # Text findings are not decode failures.

    def keep(key: str, operation: Callable[[], Any]) -> None:
        try:
            data[key] = operation()
        except (APRSError, ValueError) as exc:
            message = getattr(exc, "message", str(exc))
            diagnostics.append(Diagnostic("malformed", message, "$." + key))

    dti, body = raw[:1], raw[1:]
    if dti in (b"!", b"=", b"/", b"@"):
        data = {"type": "position", "messaging": dti in (b"=", b"@")}
        if dti in (b"/", b"@"):
            data["timestamp"] = _timestamp(body[:7])
            body = body[7:]
        for field, needed in (
            ("latitude_deg", 8),
            ("longitude_deg", 18),
            ("symbol", 19),
        ):
            if len(body) < needed:
                diagnostics.append(
                    Diagnostic("malformed", "missing or truncated field", "$." + field)
                )
        if len(body) >= 8:
            keep("latitude_deg", lambda: decode_coordinate(body[:8], "latitude"))
        if len(body) >= 18:
            keep("longitude_deg", lambda: decode_coordinate(body[9:18], "longitude"))
        symbol: dict[str, object] = {}
        if len(body) >= 9 and 33 <= body[8] <= 126:
            symbol["table_id"] = chr(body[8])
        if len(body) >= 19:
            if 33 <= body[18] <= 126:
                symbol["code"] = chr(body[18])
            data["comment"] = free_text(body[19:], "$.comment", ignored)
        if symbol:
            data["symbol"] = symbol
    elif dti == b">":
        data["type"] = "status"
        if len(body) >= 7 and body[:6].isdigit() and body[6:7] == b"z":
            data["timestamp"] = _timestamp(body[:7])
            body = body[7:]
        data["text"] = free_text(body, "$.text", ignored)
    elif dti == b":":
        data["type"] = "message"
        if len(body) >= 10 and body[9:10] == b":":
            address, message = body[:9], body[10:]
        else:
            # A short addressee with a clear separator still gives reliable text.
            address, _, message = body.partition(b":")
        keep("addressee", lambda: token(address, "$.addressee").rstrip(" "))
        text, separator, identifier = message.partition(b"{")
        data["text"] = free_text(text, "$.text", ignored)
        if separator:
            # A present but invalid ID must not become an absent ID. Keep its
            # spelling so strict import still rejects it until it is repaired.
            number, brace, ack = identifier.partition(b"}")
            data["message_id"] = number.decode("latin-1")
            if brace:
                data["reply_ack"] = ack.decode("latin-1")
    elif dti == b"{":
        data["type"] = "user_defined"
        if body:
            data["user_id"] = body[:1].decode("latin-1")
        if len(body) >= 2:
            data["user_type"] = body[1:2].decode("latin-1")
            data["data"] = body[2:].decode("latin-1")
    return data, diagnostics
