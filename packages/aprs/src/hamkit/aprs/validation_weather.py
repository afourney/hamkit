# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Weather/report context and encoding-specific telemetry invariants.

APRS101 chapters 12–13 define the baseline report shapes. A shared Weather
component may be empty; attaching it to a report imposes the required slots.
Unavailable measurements are present slots, not fabricated numeric readings.
"""
from __future__ import annotations

from typing import Any

from .model_validation import ModelError


def validate_weather_report(weather: Any, path: str, positioned: bool = False) -> None:
    """Validate a complete baseline weather report without encoding its fields."""
    if positioned:
        if weather.timestamp is not None:
            raise ModelError(
                f"{path}.timestamp", "positioned weather uses the enclosing timestamp"
            )
    elif weather.timestamp is None or weather.timestamp.kind != "mdhm_utc":
        raise ModelError(f"{path}.timestamp", "positionless weather requires MDHM UTC")
    for field in ("wind_direction", "wind_speed", "gust", "temperature"):
        if getattr(weather, field) is None:
            raise ModelError(
                f"{path}.{field}",
                "required weather slot; use Measurement(None, unit) when unavailable",
            )
    if not positioned and weather.snow_24h is not None:
        raise ModelError(
            f"{path}.snow_24h", "snow cannot use the positionless wind-speed identifier"
        )


def _telemetry(v: Any, path: str) -> None:
    def fail(field: str, message: str) -> None:
        raise ModelError(f"{path}.{field}", message)

    def analog(low: int, high: int) -> None:
        for i, value in enumerate(v.analog):
            if (
                value is None
                or not float(value).is_integer()
                or not low <= value <= high
            ):
                fail(f"analog[{i}]", f"requires an integer in {low}..{high}")

    if not 0 <= len(v.analog) <= 5:
        fail("analog", "at most five analog channels")
    if not 0 <= len(v.digital) <= 8:
        fail("digital", "at most eight digital channels")
    if v.encoding == "classic":
        if len(v.analog) != 5:
            fail("analog", "classic telemetry requires five analog channels")
        if len(v.digital) != 8 or any(x is None for x in v.digital):
            fail("digital", "classic telemetry requires eight binary channels")
        analog(0, 255)
        if v.sequence != "MIC" and not (
            type(v.sequence) is int and 0 <= v.sequence <= 999
        ):
            fail("sequence", "classic telemetry requires 0..999 or MIC")
        if v.sequence != "MIC" and not v.mic_comma:
            fail("mic_comma", "comma omission applies only to the MIC sequence")
    elif v.encoding in ("mic_e_hex", "mic_e_binary"):
        counts = (2, 5) if v.encoding == "mic_e_hex" else (5,)
        if len(v.analog) not in counts:
            fail("analog", f"{v.encoding} requires channel counts {counts}")
        analog(0, 255)
        if v.digital:
            fail("digital", "Mic-E telemetry has no separate digital field")
        if v.sequence is not None:
            fail("sequence", "Mic-E telemetry has no sequence field")
        if v.comment:
            fail("comment", "Mic-E telemetry and status text are alternative fields")
        if not v.mic_comma:
            fail("mic_comma", "only meaningful for a classic MIC sequence")
    elif v.encoding == "base91_comment":
        if not (type(v.sequence) is int and 0 <= v.sequence <= 8280):
            fail("sequence", "base91 telemetry requires an integer in 0..8280")
        if not v.analog:
            fail("analog", "base91 telemetry requires at least one analog channel")
        analog(0, 8280)
        if v.digital and (
            len(v.analog) != 5
            or len(v.digital) != 8
            or any(x is None for x in v.digital)
        ):
            fail("digital", "eight binary channels must follow five analog channels")
        if v.comment:
            fail("comment", "base91 telemetry uses the enclosing position comment")
        if not v.mic_comma:
            fail("mic_comma", "only meaningful for a classic MIC sequence")
    elif not v.analog and not v.digital:
        fail("analog", "at least one channel is required")


def validate_weather(v: Any, path: str) -> None:
    """Additional semantic checks after generic model/type validation."""
    name = type(v).__name__
    if name == "Packet" and type(v.payload).__name__ == "Weather":
        validate_weather_report(v.payload, f"{path}.payload")
    elif name == "Packet" and type(v.payload).__name__ == "Telemetry":
        if v.payload.encoding not in ("classic", "compatibility"):
            raise ModelError(
                f"{path}.payload.encoding",
                "comment/Mic-E telemetry requires its enclosing report",
            )
    elif name in ("Position", "Location") and v.extensions.weather is not None:
        validate_weather_report(
            v.extensions.weather, f"{path}.extensions.weather", positioned=True
        )
    elif name == "Weather":
        if v.software_code is not None and len(v.software_code) != 1:
            raise ModelError(f"{path}.software_code", "requires one character")
        if v.device_code is not None and not 2 <= len(v.device_code) <= 4:
            raise ModelError(f"{path}.device_code", "requires two to four characters")
    elif name == "Telemetry":
        _telemetry(v, path)
    elif name in ("Parameters", "Units"):
        limits = (7, 6, 5, 5, 4, 5, 4, 3, 3, 3, 2, 2, 2)
        if not 1 <= len(v.channels) <= len(limits):
            raise ModelError(f"{path}.channels", "requires one to thirteen channels")
        for i, (channel, limit) in enumerate(zip(v.channels, limits)):
            if channel is not None and (
                len(channel) > limit or any(c in ",|~{" for c in channel)
            ):
                raise ModelError(
                    f"{path}.channels[{i}]",
                    f"requires at most {limit} characters without message/CSV delimiters",
                )
    elif name == "Bits":
        if len(v.sense) != 8 or any(type(bit) is not bool for bit in v.sense):
            raise ModelError(f"{path}.sense", "requires eight non-null binary values")
        if len(v.project_title) > 23 or any(c in "|~{" for c in v.project_title):
            raise ModelError(
                f"{path}.project_title", "requires at most 23 message-safe characters"
            )
