# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Derived bounds and the transmitted cell agree at adjacent float boundaries."""
import math
from fractions import Fraction

import pytest

from hamkit import aprs as a

POLICIES = [a.RF(), a.RF(extensions=()), a.APRS_IS(), a.APRS_IS(extensions=())]
KINDS = [a.Position, a.MicE, a.Object, a.Item]


def located(kind, latitude, longitude, ambiguity):
    options = {"ambiguity": ambiguity}
    if kind is a.MicE:
        options.update(
            message="off_duty", extensions=a.Extensions(motion=a.Motion(90, 10))
        )
    if kind is a.Object:
        options["timestamp"] = a.Timestamp.dhm(18, 0, 0)
    args = ("Test",) if kind in (a.Object, a.Item) else ()
    return kind(*args, latitude, longitude, a.Symbol("/", ">"), **options)


def check_extent(payload, expected, policy):
    # JSON is reconstructed separately before encoding, not just compared with
    # the same potentially incorrect Python property's output.
    for value in (payload, a.from_json(a.to_json(payload))):
        assert value.ambiguity_extent == expected
        destination = None if isinstance(value, a.MicE) else "APRS"
        packet = a.Packet(a.Header("N0CALL", destination), value)
        assert not a.check_packet(packet, policy=policy)
        a.validate_packet(packet, policy=policy)
        wire = a.serialize_packet(packet, policy=policy)
        decoded = a.parse_packet(wire, policy=policy)
        assert isinstance(decoded, a.Packet)
        assert decoded.payload.ambiguity_extent == expected
        assert decoded.payload.ambiguity_extent == value.ambiguity_extent
        assert a.serialize_packet(decoded, policy=policy) == wire


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("digits", [1, 2, 3, 4])
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("neighbor", ["below", "exact", "above"])
def test_original_and_decoded_extents_match_at_boundaries(
    policy, kind, digits, sign, neighbor
):
    lat_edge, lon_edge = (50.0, 73.0) if digits == 4 else (49.5, 72.5)

    def coordinate(edge):
        if neighbor == "below":
            return sign * math.nextafter(edge, 0)
        if neighbor == "above":
            return sign * math.nextafter(edge, math.inf)
        return sign * edge

    # Independent exact rational bounds, not computed by any codec helper.
    width = (Fraction(1, 600), Fraction(1, 60), Fraction(1, 6), Fraction(1))[digits - 1]

    def bounds(edge):
        low = Fraction(edge) - width if neighbor == "below" else Fraction(edge)
        high = low + width
        return (float(low), float(high)) if sign > 0 else (-float(high), -float(low))

    value = located(kind, coordinate(lat_edge), coordinate(lon_edge), digits)
    check_extent(value, a.Extent(bounds(lat_edge), bounds(lon_edge)), policy)


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("digits", [1, 2, 3, 4])
@pytest.mark.parametrize("sign", [-1, 1])
def test_zero_and_last_representable_cells(policy, kind, digits, sign):
    width = (Fraction(1, 600), Fraction(1, 60), Fraction(1, 6), Fraction(1))[digits - 1]
    for latitude, longitude, lat_low, lon_low in (
        (0.0, 0.0, Fraction(0), Fraction(0)),
        (math.nextafter(90, 0), math.nextafter(180, 0), 90 - width, 180 - width),
    ):

        def bounds(low):
            return (
                (float(low), float(low + width))
                if sign > 0
                else (-float(low + width), -float(low))
            )

        value = located(
            kind, math.copysign(latitude, sign), math.copysign(longitude, sign), digits
        )
        check_extent(value, a.Extent(bounds(lat_low), bounds(lon_low)), policy)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("digits", [1, 2, 3, 4])
@pytest.mark.parametrize("sign", [-1, 1])
def test_unrepresentable_boundary_has_no_neighboring_extent(kind, digits, sign):
    for latitude, longitude in ((sign * 90, 0.0), (0.0, sign * 180)):
        value = located(kind, latitude, longitude, digits)
        for variant in (value, a.from_json(a.to_json(value))):
            with pytest.raises(a.FieldError, match="ambiguity cell exceeds"):
                _ = variant.ambiguity_extent
