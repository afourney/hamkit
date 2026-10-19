# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Resolved envelope constraints and selected APRS payload interpretation."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Literal, TypeAlias, TypedDict, Unpack

Extension: TypeAlias = Literal[
    "utf8_text",
    "dao",
    "base91_telemetry",
    "mice_device_ids",
    "mice_hex_as_device",
    "expanded_telemetry",
    "phg_rate",
    "weather_extensions",
    "water_height_tenths",
    "w_symbol_motion",
]
ExtensionKind: TypeAlias = Literal["additive", "comment", "reinterpretive"]
# Explicit classification is required for each implemented identifier. Defaults
# select only approved categories, never "everything except known exceptions".
EXTENSION_KINDS: Mapping[Extension, ExtensionKind] = MappingProxyType(
    {
        "utf8_text": "additive",
        "dao": "comment",
        "base91_telemetry": "comment",
        "mice_device_ids": "comment",
        "mice_hex_as_device": "reinterpretive",
        "expanded_telemetry": "additive",
        "phg_rate": "comment",
        "weather_extensions": "additive",
        "water_height_tenths": "reinterpretive",
        "w_symbol_motion": "reinterpretive",
    }
)
SUPPORTED_EXTENSIONS: tuple[Extension, ...] = tuple(EXTENSION_KINDS)
ByteFallback: TypeAlias = Literal["latin-1", "reject"]


@dataclass(frozen=True, slots=True)
class EnvelopePolicy:
    """Address fullmatch patterns and optional, nonnegative envelope limits.

    Path addresses exclude their trailing repeated marker (``*``). Information
    length includes third-party encapsulation. TNC2 line length includes a
    canonical CRLF, even for unframed input. None means no limit.

    Envelope constraints exclude encapsulated headers. Extension interpretation
    and text rules apply throughout the packet tree. Direct construction defaults
    to the implemented APRS 1.1 baseline (no extensions). Iterable extension input
    is stored as an immutable tuple in catalog order. See ENVELOPE_POLICIES.md.
    """

    source_pattern: str
    destination_pattern: str
    path_address_pattern: str
    max_path_entries: int | None = None
    max_information_bytes: int | None = None
    max_tnc2_line_bytes: int | None = None

    extensions: Iterable[Extension] = ()
    legacy_positions: bool = False
    byte_fallback: ByteFallback = "latin-1"

    def __post_init__(self) -> None:
        if isinstance(self.extensions, (str, bytes)):
            raise TypeError("extensions must be a collection of identifiers")
        supplied = tuple(self.extensions)
        if any(
            not isinstance(x, str) or x not in SUPPORTED_EXTENSIONS for x in supplied
        ):
            raise ValueError("unknown extension identifier")
        if len(set(supplied)) != len(supplied):
            raise ValueError("duplicate extension identifiers")
        object.__setattr__(
            self, "extensions", tuple(x for x in SUPPORTED_EXTENSIONS if x in supplied)
        )
        if type(self.legacy_positions) is not bool:
            raise TypeError("legacy_positions must be a bool")
        if self.byte_fallback not in ("latin-1", "reject"):
            raise ValueError("byte_fallback must be 'latin-1' or 'reject'")
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
# APRS-IS drops SSID -0 because it conflicts with an absent SSID.
_APRS_IS_SSID = r"(?:-(?!0\Z)[A-Za-z0-9]{1,2})?"
_APRS_IS_SOURCE = r"(?=.{1,9}\Z)[A-Za-z0-9]{3,9}" + _APRS_IS_SSID
_APRS_IS_ADDRESS = r"(?=.{1,9}\Z)[A-Za-z0-9]{1,9}" + _APRS_IS_SSID

_RF = EnvelopePolicy(
    source_pattern=_AX25_ADDRESS,
    destination_pattern=_AX25_ADDRESS,
    path_address_pattern=_AX25_ADDRESS,
    max_path_entries=8,
    max_information_bytes=256,
)

_APRS_IS = EnvelopePolicy(
    source_pattern=_APRS_IS_SOURCE,
    destination_pattern=_APRS_IS_ADDRESS,
    path_address_pattern=_APRS_IS_ADDRESS,
    max_tnc2_line_bytes=512,
)


DEFAULT_EXTENSIONS: tuple[Extension, ...] = tuple(
    x for x, kind in EXTENSION_KINDS.items() if kind in ("additive", "comment")
)


class PolicyOverrides(TypedDict, total=False):
    """Individual RF/APRS_IS factory overrides; extensions are a separate argument."""

    source_pattern: str
    destination_pattern: str
    path_address_pattern: str
    max_path_entries: int | None
    max_information_bytes: int | None
    max_tnc2_line_bytes: int | None
    legacy_positions: bool
    byte_fallback: ByteFallback


def RF(
    *,
    extensions: Iterable[Extension] | None = None,
    **overrides: Unpack[PolicyOverrides],
) -> EnvelopePolicy:
    """AX.25 envelope limits and compatible extension defaults; explicit empty selects baseline."""
    return replace(
        _RF,
        extensions=DEFAULT_EXTENSIONS if extensions is None else extensions,
        **overrides,
    )


def APRS_IS(
    *,
    extensions: Iterable[Extension] | None = None,
    **overrides: Unpack[PolicyOverrides],
) -> EnvelopePolicy:
    """APRS-IS envelope limits and compatible extension defaults; explicit empty selects baseline."""
    return replace(
        _APRS_IS,
        extensions=DEFAULT_EXTENSIONS if extensions is None else extensions,
        **overrides,
    )


_DEFAULT_POLICY = APRS_IS()
