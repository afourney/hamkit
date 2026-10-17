# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Wire text decoding.

APRS101/1.1 specify printable ASCII. The APRS 1.2 addendum
(aprs.org/aprs12/utf-8.txt) allows UTF-8 in message, bulletin, status and
comment text, so free text decodes as UTF-8. Bytes that are not valid UTF-8 fall
back to Latin-1, one character per byte, with a nonconforming diagnostic; the
exact bytes remain in original_wire. Protocol tokens stay printable ASCII.
"""
from __future__ import annotations

from ._errors import ModelError
from ._models import Diagnostic


def free_text(raw: bytes, path: str, diagnostics: list[Diagnostic]) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
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
