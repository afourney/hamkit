# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Envelope validation is separate from APRS field interpretation."""

import re

from .errors import EnvelopeError
from .models import Header, ValidationProfile


def validate_header(header: Header, *, profile: ValidationProfile = "monitor") -> None:
    """Validate monitor tokens, optionally imposing AX.25 RF address limits.

    Monitor mode retains APRS-IS tokens/case; it is not an APRS-IS server policy.
    RF mode checks syntax and at most eight hops, not callsign allocation.
    """
    if profile not in ("monitor", "rf"):
        raise ValueError("profile must be 'monitor' or 'rf'")
    addresses = [
        header.source,
        header.destination,
        *(hop.address for hop in header.path),
    ]
    for address in addresses:
        if not address or any(
            ord(c) < 33 or ord(c) > 126 or c in ">,:*" for c in address
        ):
            raise EnvelopeError("empty or invalid address token")
        if profile == "rf":
            match = re.fullmatch(r"[A-Z0-9]{1,6}(?:-([0-9]{1,2}))?", address)
            if not match or (match[1] is not None and int(match[1]) > 15):
                raise EnvelopeError("invalid RF address or SSID")
    if profile == "rf" and len(header.path) > 8:
        raise EnvelopeError("RF path exceeds eight hops")
