# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Public errors shared by models, codecs and JSON conversion."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._models import Diagnostic


class APRSError(ValueError):
    """Base class for invalid APRS wire data or structured values."""


class EnvelopeError(APRSError):
    """Invalid TNC2 envelope or transport framing."""


class FieldError(APRSError):
    """Invalid field in a supported representation."""


class ModelError(FieldError):
    """A model value that cannot exist on the wire or contradicts itself."""

    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


class Unrepresentable(FieldError):
    """A value with no exact wire form; path is relative to the encoded payload."""

    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


class ConformanceError(FieldError):
    """A packet is representable but breaks APRS rules; it must not be sent."""

    def __init__(self, diagnostics: tuple[Diagnostic, ...]):
        self.diagnostics = diagnostics
        super().__init__("; ".join(f"{d.path}: {d.message}" for d in diagnostics))


class CodecNotImplementedError(APRSError, NotImplementedError):
    """A modeled feature has no codec yet. Never substitute empty/opaque output."""


class ContextRequiredError(APRSError):
    """A header-dependent codec needs the outer packet header."""


class ResourceLimitError(APRSError):
    """The explicit third-party nesting limit was reached."""
