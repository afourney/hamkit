# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Wire text decoding.

APRS101/1.1 specify printable ASCII. Receive decoding preserves intelligible
UTF-8 for diagnostics even when the selected policy does not permit sending it.
Conformance permits non-ASCII only in designated free-text fields with utf8_text.
Invalid UTF-8 either falls back to Latin-1 with a diagnostic or raises, according
to byte_fallback. Original bytes remain evidence, never a serialization source.
Protocol tokens stay printable ASCII.
"""
from __future__ import annotations

from ._errors import ModelError
from ._models import Diagnostic
from ._policy import _DEFAULT_POLICY, EnvelopePolicy


def free_text(
    raw: bytes,
    path: str,
    diagnostics: list[Diagnostic],
    policy: EnvelopePolicy = _DEFAULT_POLICY,
) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        if policy.byte_fallback == "reject":
            raise ModelError(
                path, "text is not valid UTF-8 and byte fallback is disabled"
            ) from exc
        diagnostics.append(
            Diagnostic(
                "nonconforming", "text is not valid UTF-8; decoded as Latin-1", path
            )
        )
        return raw.decode("latin-1")


def token(raw: bytes, path: str) -> str:
    if any(not 32 <= c <= 126 for c in raw):
        raise ModelError(path, "protocol token must be printable ASCII")
    return raw.decode("ascii")
