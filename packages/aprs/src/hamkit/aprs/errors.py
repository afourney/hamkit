# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Public errors shared by packet and field codecs."""


class APRSError(ValueError):
    """Base class for invalid APRS wire data or structured values."""


class EnvelopeError(APRSError):
    """Invalid TNC2 envelope or transport framing."""


class FieldError(APRSError):
    """Invalid field in a supported representation."""


class UnsupportedFormat(APRSError):
    """A field codec cannot represent this otherwise potentially valid format."""


class CodecNotImplemented(UnsupportedFormat, NotImplementedError):
    """A modeled feature has no codec yet. Never substitute empty/opaque output."""


class ContextRequired(APRSError):
    """A header-dependent codec needs the outer header or joint encoder."""


class ResourceLimitError(APRSError):
    """The explicit third-party nesting limit was reached."""
