# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Declarative constraints for the outer TNC2 packet envelope."""

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EnvelopePolicy:
    """Address fullmatch patterns and optional, nonnegative envelope limits.

    Path addresses exclude their trailing repeated marker (``*``). Information
    length includes third-party encapsulation. TNC2 line length includes a
    canonical CRLF, even for unframed input. None means no limit.

    These constraints apply to the outer envelope, not encapsulated headers.
    Basic TNC2 token syntax and payload conformance still apply independently.
    """

    source_pattern: str
    destination_pattern: str
    path_address_pattern: str
    max_path_entries: int | None = None
    max_information_bytes: int | None = None
    max_tnc2_line_bytes: int | None = None

    def __post_init__(self) -> None:
        for name in (
            "source_pattern",
            "destination_pattern",
            "path_address_pattern",
        ):
            pattern = getattr(self, name)
            if not isinstance(pattern, str):
                raise TypeError(f"{name} must be a string")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(
                    f"{name} is not a valid regular expression: {exc}"
                ) from exc
        for name in (
            "max_path_entries",
            "max_information_bytes",
            "max_tnc2_line_bytes",
        ):
            limit = getattr(self, name)
            if limit is not None:
                if type(limit) is not int:
                    raise TypeError(f"{name} must be an integer or None")
                if limit < 0:
                    raise ValueError(f"{name} must be nonnegative")


_AX25_ADDRESS = r"[A-Z0-9]{1,6}(?:-(?:[0-9]|1[0-5]))?"
_APRS_IS_SOURCE = r"(?=.{1,9}\Z)[A-Za-z0-9]{3,9}(?:-[A-Za-z0-9]{1,2})?"
_APRS_IS_ADDRESS = r"(?=.{1,9}\Z)[A-Za-z0-9]{1,9}(?:-[A-Za-z0-9]{1,2})?"

RF = EnvelopePolicy(
    source_pattern=_AX25_ADDRESS,
    destination_pattern=_AX25_ADDRESS,
    path_address_pattern=_AX25_ADDRESS,
    max_path_entries=8,
    max_information_bytes=256,
)

APRS_IS = EnvelopePolicy(
    source_pattern=_APRS_IS_SOURCE,
    destination_pattern=_APRS_IS_ADDRESS,
    path_address_pattern=_APRS_IS_ADDRESS,
    max_tnc2_line_bytes=512,
)
