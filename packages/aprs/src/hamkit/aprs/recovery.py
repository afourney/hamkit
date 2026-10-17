# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Best-effort extraction into ordinary JSON data, never partially valid models."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .errors import APRSError
from .fields import decode_coordinate
from .models import Diagnostic


def text(raw: bytes) -> str:
    if any(c < 32 or c > 126 for c in raw):
        raise ValueError("protocol text requires printable ASCII")
    return raw.decode("ascii")


def timestamp(raw: bytes) -> dict[str, object]:
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

    def keep(key: str, operation: Callable[[], Any]) -> None:
        try:
            data[key] = operation()
        except (APRSError, ValueError) as exc:
            diagnostics.append(Diagnostic("malformed", str(exc), "$." + key))

    dti, body = raw[:1], raw[1:]
    if dti in (b"!", b"=", b"/", b"@"):
        data = {"type": "position", "messaging": dti in (b"=", b"@")}
        if dti in (b"/", b"@"):
            data["timestamp"] = timestamp(body[:7])
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
        if len(body) >= 9:
            try:
                symbol["table_id"] = text(body[8:9])
            except ValueError:
                pass
        if len(body) >= 19:
            try:
                symbol["code"] = text(body[18:19])
            except ValueError:
                pass
            data["tail"] = body[19:].decode("latin-1")
        if symbol:
            data["symbol"] = symbol
    elif dti == b">":
        data["type"] = "status"
        if len(body) >= 7 and body[:6].isdigit() and body[6:7] == b"z":
            data["timestamp"] = timestamp(body[:7])
            body = body[7:]
        keep("text", lambda: text(body))
    elif dti == b":":
        data["type"] = "message"
        if len(body) >= 10 and body[9:10] == b":":
            keep("addressee", lambda: text(body[:9]).rstrip(" "))
            message, sep, identifier = body[10:].partition(b"{")
            keep("text", lambda: text(message))
            if sep:
                keep("message_id", lambda: text(identifier))
        else:
            # A short addressee with a clear separator still gives reliable text.
            address, sep, message = body.partition(b":")
            if sep:
                keep("addressee", lambda: text(address).rstrip(" "))
                keep("text", lambda: text(message))
    elif dti == b"{":
        data["type"] = "user_defined"
        if body:
            data["user_id"] = body[:1].decode("latin-1")
        if len(body) >= 2:
            data["user_type"] = body[1:2].decode("latin-1")
            data["data"] = body[2:].decode("latin-1")
    return data, diagnostics
