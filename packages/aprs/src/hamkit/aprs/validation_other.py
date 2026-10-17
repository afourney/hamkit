# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Envelope interpretations and explicitly raw/historical family invariants.

APRS101 pp15,17–18,62,89; APRS-IS q construct syntax. Raw vendor bytes are
content; optional interpreted observations remain non-authoritative annotations.
"""
from __future__ import annotations

import re
from typing import Any

from .model_validation import ModelError

# Only identifiers explicitly unused/reserved by APRS101 p17. Assigned formats
# and 'do not use' characters are not reserved packets. Opaque preserves all
# other unknown bytes without asserting a family classification.
_RESERVED = frozenset(b'"&(+.-\\]^')


def validate_other(v: Any, path: str) -> None:
    name = type(v).__name__

    def fail(field: str, message: str) -> None:
        raise ModelError(f"{path}.{field}", message)

    if name == "Reserved" and v.dti not in _RESERVED:
        fail(
            "dti",
            "requires an unused/reserved APRS101 identifier; use Opaque for other raw data",
        )
    if name == "LegacyPosition":
        if len(v.prefix) > 39 or b"!" in v.prefix:
            fail(
                "prefix",
                "historical position marker must be the first ! and within 40 bytes",
            )
        if v.position.timestamp is not None or v.position.messaging:
            fail("position", "historical ! position has no timestamp or messaging flag")
    if name == "RawWeather":
        prefixes = {
            "ultimeter_ii": (b"*", b"#"),
            "ultimeter_2000": (b"!!", b"$ULTW"),
            "ultw": (b"$ULTW",),
            "peet_logging": (b"!!",),
        }
        if not v.information.startswith(prefixes[v.format]):
            fail("information", "prefix does not match the declared vendor format")
    if name == "Beacon" and not v.text:
        fail("text", "a beacon requires nonempty information")
    if (
        name == "Opaque"
        and v.diagnostic is not None
        and v.diagnostic.code != "unsupported"
    ):
        fail("diagnostic.code", "opaque classification is unsupported, not malformed")
    if name == "HeaderSemantics":
        if (
            v.destination_ssid_route is not None
            and not 0 <= v.destination_ssid_route <= 15
        ):
            fail("destination_ssid_route", "SSID route must be in 0..15")
        if v.q_construct is not None and not re.fullmatch(r"qA[A-Za-z]", v.q_construct):
            fail("q_construct", "requires an APRS-IS qA token")
    if name == "Packet" and v.header_semantics is not None:
        semantics = v.header_semantics
        if semantics.destination_ssid_route is not None:
            destination = v.header.destination
            match = re.fullmatch(r"[A-Z0-9]{1,6}(?:-([0-9]{1,2}))?", destination)
            if match is None or int(match[1] or 0) != semantics.destination_ssid_route:
                fail(
                    "header_semantics.destination_ssid_route",
                    "does not match destination SSID",
                )
        if semantics.q_construct is not None:
            tokens = [hop.address for hop in v.header.path]
            if semantics.q_construct not in tokens:
                fail("header_semantics.q_construct", "not present in header path")
            index = tokens.index(semantics.q_construct)
            if index == len(tokens) - 1:
                fail("header.path", "q construct requires a following entry station")
