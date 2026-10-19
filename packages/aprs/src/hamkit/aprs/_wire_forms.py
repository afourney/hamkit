# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Choose each container's wire form, so composing never selects an encoding.

Altitude and Telemetry record the form they were received in. When sending, a
received form is kept if the enclosing payload and policy can carry it;
otherwise, and for newly composed values, the library chooses. Checking and
encoding both use the resolved packet, so they always agree.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, TypeVar

from ._data import Altitude, Compression, Telemetry
from ._errors import APRSError
from ._models import Item, LegacyPosition, MicE, Object, Packet, Position, ThirdParty
from ._policy import EnvelopePolicy

T = TypeVar("T")


def resolve(value: T, policy: EnvelopePolicy) -> T:
    """Return value with every altitude and telemetry form chosen for sending."""
    if isinstance(value, Packet):
        return replace(value, payload=resolve(value.payload, policy))  # type: ignore[return-value]
    if isinstance(value, ThirdParty):
        return replace(value, packet=resolve(value.packet, policy))  # type: ignore[return-value]
    if isinstance(value, LegacyPosition):
        return replace(value, position=resolve(value.position, policy))  # type: ignore[return-value]
    if isinstance(value, Telemetry):
        return _with(value, encoding="classic")  # A telemetry report is classic.
    if not isinstance(value, (Position, Object, Item, MicE)):
        return value
    located: Any = value
    if not isinstance(located, MicE) and located.compression is not None:
        # The altitude form below depends on the chosen compression source.
        located = replace(located, compression=_compression(located))
    e = located.extensions
    altitude, telemetry = e.altitude, e.telemetry
    if altitude is not None:
        altitude = _with(altitude, encoding=_altitude_form(located, altitude))
    if telemetry is not None:
        telemetry = _with(
            telemetry, encoding=_telemetry_form(located, telemetry, policy)
        )
    if altitude is None and telemetry is None:
        return located  # type: ignore[no-any-return]
    return replace(  # type: ignore[no-any-return]
        located, extensions=replace(e, altitude=altitude, telemetry=telemetry)
    )


def _with(node: Any, **changes: Any) -> Any:
    """A copy with the chosen form, or the original if the model refuses it.

    Refusals (such as a Mic-E altitude with an ellipsoid reference) are then
    reported by the ordinary checks for the unchanged value.
    """
    try:
        return replace(node, **changes)
    except APRSError:
        return node


def _compression(container: Any) -> Compression:
    c = container.compression
    if c.ignored or None not in (c.fix, c.nmea_source, c.origin):
        return c
    e = container.extensions
    weather_wind = e.weather is not None and (
        e.weather.wind_direction is not None or e.weather.wind_speed is not None
    )
    motion = e.motion is not None and None not in (
        e.motion.course_deg,
        e.motion.speed_knots,
    )
    if not (motion or e.range is not None or weather_wind or c.nmea_source == "GGA"):
        return Compression(ignored=True)  # Nothing for csT to carry.
    return replace(
        c,
        fix=c.fix or "current",
        nmea_source=c.nmea_source or "other",
        origin=c.origin or "software",  # APRS101: DOS/Mac/Win/+SA software
    )


def _altitude_form(container: Any, altitude: Altitude) -> str:
    if isinstance(container, MicE):
        if altitude.reference == "ellipsoid":
            return "feet_extension"  # The model forbids it in the Mic-E field.
        if altitude.encoding in ("mic_e", "feet_extension"):
            return altitude.encoding
        # The compact Mic-E field holds whole meters; /A= holds whole feet.
        # Choosing by unit keeps the precision the caller gave.
        return "mic_e" if altitude.measurement.unit == "meters" else "feet_extension"
    csT = container.compression
    if csT is not None and not csT.ignored and csT.nmea_source == "GGA":
        return "compressed"  # APRS101: a GGA-sourced csT carries the altitude.
    return "feet_extension"


def _telemetry_form(container: Any, t: Telemetry, policy: EnvelopePolicy) -> str:
    if not isinstance(container, MicE):
        return "base91_comment"  # The only telemetry a position comment carries.
    hex_allowed = "mice_hex_as_device" not in policy.extensions
    # Hex and binary telemetry occupy the first status byte, like a type code.
    leading = container.device_code is None
    if t.encoding == "mic_e_hex" and hex_allowed and leading:
        return t.encoding
    if t.encoding in ("mic_e_binary",) and leading:
        return t.encoding
    if t.encoding == "base91_comment":
        return t.encoding
    present = [v for v in t.analog if v is not None]
    bytewise = (
        leading
        and t.sequence is None
        and not t.digital
        and not t.comment
        and all(float(v).is_integer() and 0 <= v <= 255 for v in present)
    )
    five = len(t.analog) == 5 and len(present) == 5
    two = len(present) == 2 and (
        len(t.analog) == 2
        or len(t.analog) == 5
        and all(t.analog[i] is None for i in (1, 3, 4))
    )
    if bytewise and hex_allowed and (five or two):
        return "mic_e_hex"
    if bytewise and five:
        return "mic_e_binary"
    return "base91_comment"
