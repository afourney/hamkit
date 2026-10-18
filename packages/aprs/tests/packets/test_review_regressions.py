# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Independent wire anchors for the six post-semantic-API review findings."""
import math
from dataclasses import replace

import pytest

from hamkit import aprs as a

POLICIES = [a.RF(), a.RF(extensions=()), a.APRS_IS(), a.APRS_IS(extensions=())]
SYMBOL = a.Symbol("/", ">")


def checked(payload, policy, destination="APRS"):
    packet = a.Packet(a.Header("N0CALL", destination), payload)
    assert not a.check_packet(packet, policy=policy)
    a.validate_packet(packet, policy=policy)
    wire = a.serialize_packet(packet, policy=policy)
    assert wire == a.serialize_packet(a.from_json(a.to_json(packet)), policy=policy)
    assert wire.partition(b":")[2] == a.serialize_payload(payload, policy=policy)
    parsed = a.parse_packet(wire, policy=policy)
    assert isinstance(parsed, a.Packet)
    return wire, parsed


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("comment", ["", "hello", "*99,tail", " spaced "])
@pytest.mark.parametrize(
    "sentence",
    [
        a.GLL(a.Coordinates(49, -72), a.UTCTime(12, 0, 0), "A"),
        a.GGA(a.UTCTime(12, 0, 0), a.Coordinates(49, -72), 1),
        a.RMC(a.UTCTime(12, 0, 0), a.NMEADate(1, 1, 26), "A", a.Coordinates(49, -72)),
        a.WPL(a.Coordinates(49, -72), "HOME"),
        a.VTG(course_true_deg=90, speed_knots=10),
    ],
)
def test_nmea_comment_has_an_unambiguous_checksum_boundary(policy, comment, sentence):
    payload = a.NMEA(sentence, a.NMEAMetadata("GP"), comment=comment)
    wire, parsed = checked(payload, policy)
    assert parsed.payload.sentence == sentence
    assert parsed.payload.comment == comment
    assert parsed.payload.metadata.checksum_valid is (True if comment else None)
    assert payload.metadata.checksum_supplied is None  # automatic, without mutation
    assert b"*" in wire if comment else b"*" not in wire
    changed = replace(parsed.payload, comment="edited")
    assert checked(changed, policy)[1].payload.comment == "edited"


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize(
    "ambiguity,center_minutes", [(1, 59.95), (2, 59.5), (3, 55), (4, 30)]
)
@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("edge", [49.999999, math.nextafter(50, 0)])
def test_ambiguity_selects_the_cell_before_rounding(
    policy, ambiguity, center_minutes, sign, edge
):
    p = a.Position(sign * edge, -sign * edge, SYMBOL, ambiguity=ambiguity)
    _, parsed = checked(p, policy)
    expected = 49 + center_minutes / 60
    assert parsed.payload.latitude_deg == pytest.approx(sign * expected, abs=1e-12)
    assert parsed.payload.longitude_deg == pytest.approx(-sign * expected, abs=1e-12)
    assert checked(parsed.payload, policy)[1].payload == parsed.payload


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("ambiguity", [1, 2, 3, 4])
@pytest.mark.parametrize("sign", [-1, 1])
def test_ambiguity_at_zero_poles_and_antimeridian(policy, ambiguity, sign):
    near = a.Position(
        sign * math.nextafter(90, 0),
        sign * math.nextafter(180, 0),
        SYMBOL,
        ambiguity=ambiguity,
    )
    _, parsed = checked(near, policy)
    assert 89 <= abs(parsed.payload.latitude_deg) < 90
    assert 179 <= abs(parsed.payload.longitude_deg) < 180
    zero = replace(
        near, latitude_deg=math.copysign(0, sign), longitude_deg=math.copysign(0, sign)
    )
    decoded = checked(zero, policy)[1].payload
    assert math.copysign(1, decoded.latitude_deg) == sign
    for v in (
        replace(near, latitude_deg=sign * 90),
        replace(near, longitude_deg=sign * 180),
    ):
        packet = a.Packet(a.Header("N0CALL", "APRS"), v)
        assert a.check_packet(packet, policy=policy)
        for operation in (a.validate_packet, a.serialize_packet):
            with pytest.raises(a.ConformanceError):
                operation(packet, policy=policy)
        with pytest.raises(a.ConformanceError):
            a.serialize_payload(v, policy=policy)


@pytest.mark.parametrize("policy", POLICIES)
def test_mice_df_bearing_survives_parse_encode_and_edit(policy):
    wire = b"N0CALL>TYPP0P:`dX\x1c\x1d\x1cv\\/090/010/270/729"
    parsed = a.parse_packet(wire, policy=policy)
    assert isinstance(parsed, a.Packet)
    assert parsed.payload.extensions.bearing == a.Bearing(270, 7, 4, 9)
    assert not a.check_packet(parsed, policy=policy)
    assert a.serialize_packet(parsed, policy=policy) == wire
    edited = replace(
        parsed.payload,
        extensions=replace(
            parsed.payload.extensions,
            bearing=a.Bearing(180, hits_code=7, range_miles=16, quality_code=9),
        ),
    )
    encoded, back = checked(edited, policy, destination=None)
    assert encoded.endswith(b"090/010/180/749")
    assert back.payload.extensions.bearing.range_miles == 16
    assert back.payload.extensions.bearing.bearing_deg == 180


@pytest.mark.parametrize("policy", POLICIES)
def test_mice_phg_has_a_comment_slot_independent_of_body_motion(policy):
    p = a.MicE(
        49,
        -72,
        SYMBOL,
        message="off_duty",
        extensions=a.Extensions(motion=a.Motion(90, 10), phg=a.PHG(25, 20, 3)),
    )
    wire, parsed = checked(p, policy, destination=None)
    assert wire.endswith(b"PHG5130")
    assert parsed.payload.extensions.phg == p.extensions.phg
    assert parsed.payload.extensions.motion.course_deg == 90
    assert parsed.payload.extensions.motion.speed_knots == 10
    assert not a.check_packet(parsed, policy=policy)
    edited = replace(
        parsed.payload,
        extensions=replace(parsed.payload.extensions, phg=a.PHG(36, 40, 4)),
    )
    assert checked(edited, policy, destination=None)[0].endswith(b"PHG6240")
    with_rate = replace(
        p,
        extensions=replace(
            p.extensions, phg=replace(p.extensions.phg, rate_per_hour=1)
        ),
    )
    if "phg_rate" in policy.extensions:
        assert checked(with_rate, policy, destination=None)[0].endswith(b"PHG51301/")
    else:
        with pytest.raises(a.ConformanceError):
            a.serialize_packet(a.Packet(a.Header("N0CALL"), with_rate), policy=policy)


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("grid", ["IO91", "IO91SX"])
@pytest.mark.parametrize(
    "comment", ["", " 35 miles NNW of London", "]literal", "/>literal"]
)
def test_maidenhead_bracket_and_comment_are_distinct(policy, grid, comment):
    wire, parsed = checked(a.Maidenhead(a.Grid(grid), comment=comment), policy)
    assert wire == ("N0CALL>APRS:[" + grid + "]" + comment).encode()
    assert parsed.payload.comment == comment
    assert parsed.payload.symbol is None
    assert a.serialize_packet(parsed, policy=policy) == wire
    assert isinstance(
        a.parse_payload(("[" + grid).encode(), policy=policy), a.Malformed
    )
    unsupported = a.Packet(
        a.Header("N0CALL", "APRS"), a.Maidenhead(a.Grid(grid), symbol=SYMBOL)
    )
    assert a.check_packet(unsupported, policy=policy)
    with pytest.raises(a.ConformanceError):
        a.serialize_packet(unsupported, policy=policy)


@pytest.mark.parametrize("policy", POLICIES)
def test_semantic_area_offsets_and_df_range_python_json(policy):
    area = a.Area(0, 1, latitude_offset_deg=0.096, longitude_offset_deg=0.096)
    wire, back = checked(
        a.Position(49, -72, a.Symbol("\\", "l"), extensions=a.Extensions(area=area)),
        policy,
    )
    assert wire.endswith(b"l012/112")
    assert back.payload.extensions.area == area
    assert area.latitude_offset_code == area.longitude_offset_code == 12
    edited = replace(
        back.payload,
        extensions=a.Extensions(area=replace(area, latitude_offset_deg=0.15)),
    )
    assert checked(edited, policy)[0].endswith(b"l015/112")
    bearing = a.Bearing(270, hits_code=7, range_miles=16, quality_code=9)
    wire, back = checked(
        a.Position(
            49,
            -72,
            a.Symbol("/", "\\"),
            extensions=a.Extensions(motion=a.Motion(90, 10), bearing=bearing),
        ),
        policy,
    )
    assert wire.endswith(b"090/010/270/749")
    assert back.payload.extensions.bearing == bearing
    assert bearing.range_code == 4
    for value in (area, bearing):
        obj = a.to_json_dict(value)
        assert "range_code" not in obj and "latitude_offset_code" not in obj
        assert a.from_json_dict(obj) == value


@pytest.mark.parametrize("code", range(100))
def test_every_area_code_is_stable_from_semantic_degrees(code):
    area = a.Area(0, 1, code**2 / 1500, code**2 / 1500)
    assert area.latitude_offset_code == code
    assert area.longitude_offset_code == code


@pytest.mark.parametrize("code", range(10))
def test_every_df_range_code_is_stable_from_miles(code):
    assert a.Bearing(270, 7, 2**code, 9).range_code == code


@pytest.mark.parametrize(
    "model,values",
    [
        (
            a.Area,
            {
                "shape_code": 0,
                "color_code": 1,
                "latitude_offset_deg": -0.001,
                "longitude_offset_deg": 0,
            },
        ),
        (
            a.Area,
            {
                "shape_code": 0,
                "color_code": 1,
                "latitude_offset_deg": 6.535,
                "longitude_offset_deg": 0,
            },
        ),
        (
            a.Bearing,
            {"bearing_deg": 270, "hits_code": 7, "range_miles": 0, "quality_code": 9},
        ),
        (
            a.Bearing,
            {"bearing_deg": 270, "hits_code": 7, "range_miles": 513, "quality_code": 9},
        ),
    ],
)
def test_semantic_dimensions_reject_unrepresentable_bounds(model, values):
    with pytest.raises(a.ModelError):
        model(**values)
    with pytest.raises(a.JSONModelError):
        a.from_json_dict(values, expected_type=model)


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("kind", [a.Item, a.Object])
def test_object_and_item_ambiguity_uses_same_cell_selection(policy, kind):
    options = {"timestamp": a.Timestamp.dhm(18, 0, 0)} if kind is a.Object else {}
    value = kind("Test", 49.999999, -72.999999, SYMBOL, ambiguity=4, **options)
    decoded = checked(value, policy)[1].payload
    assert decoded.latitude_deg == 49.5
    assert decoded.longitude_deg == -72.5


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize(
    "ambiguity,center_minutes", [(1, 59.95), (2, 59.5), (3, 55), (4, 30)]
)
@pytest.mark.parametrize("sign", [-1, 1])
def test_mice_ambiguity_uses_same_cell_selection(
    policy, ambiguity, center_minutes, sign
):
    p = a.MicE(
        sign * math.nextafter(50, 0),
        -sign * math.nextafter(73, 0),
        SYMBOL,
        message="off_duty",
        ambiguity=ambiguity,
        extensions=a.Extensions(motion=a.Motion(90, 10)),
    )
    decoded = checked(p, policy, destination=None)[1].payload
    assert decoded.latitude_deg == pytest.approx(
        sign * (49 + center_minutes / 60), abs=1e-12
    )
    assert decoded.longitude_deg == pytest.approx(
        -sign * (72 + center_minutes / 60), abs=1e-12
    )


@pytest.mark.parametrize("policy", POLICIES)
def test_size_and_range_quantize_without_stale_codes(policy):
    p = a.Position(
        49,
        -72,
        a.Symbol("\\", "l"),
        extensions=a.Extensions(area=a.Area(0, 1, 0.1, 0.1)),
    )
    wire, parsed = checked(p, policy)
    assert wire.endswith(b"l012/112")
    assert parsed.payload.extensions.area.latitude_offset_deg == 0.096
    df = a.Position(
        49,
        -72,
        a.Symbol("/", "\\"),
        extensions=a.Extensions(
            motion=a.Motion(90, 10), bearing=a.Bearing(270, 7, 20, 9)
        ),
    )
    wire, parsed = checked(df, policy)
    assert wire.endswith(b"/270/749")
    assert parsed.payload.extensions.bearing.range_miles == 16


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("sign,address", [(1, "YPZZLZ"), (-1, "YPZLLZ")])
def test_explicit_mice_header_cannot_bypass_pole_cell_validation(policy, sign, address):
    value = a.MicE(
        sign * 90,
        -72,
        SYMBOL,
        message="off_duty",
        ambiguity=4,
        extensions=a.Extensions(motion=a.Motion(90, 10)),
    )
    for destination in (None, address):
        packet = a.Packet(a.Header("N0CALL", destination), value)
        assert a.check_packet(packet, policy=policy)
        for operation in (a.validate_packet, a.serialize_packet):
            with pytest.raises(a.ConformanceError):
                operation(packet, policy=policy)
    with pytest.raises(a.ConformanceError):
        a.serialize_payload(value, policy=policy)
