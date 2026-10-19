# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Semantic codes from the post-semantic-API review (wire anchors are case vectors)."""

import pytest

from hamkit import aprs as a


def test_semantic_codes_stay_out_of_json():
    # The wire behaviour of these fields is covered by the EXT/MIC case vectors.
    area = a.Area("open_circle", "blue", 0.096, 0.096)
    bearing = a.Bearing(270, range_miles=16, accuracy_deg=1, hit_ratio=7 / 8)
    assert area.latitude_offset_code == area.longitude_offset_code == 12
    assert bearing.range_code == 4
    for value in (area, bearing):
        obj = a.to_json_dict(value)
        assert "range_code" not in obj and "latitude_offset_code" not in obj
        assert a.from_json_dict(obj) == value


@pytest.mark.parametrize("code", range(100))
def test_every_area_code_is_stable_from_semantic_degrees(code):
    area = a.Area("open_circle", "blue", code**2 / 1500, code**2 / 1500)
    assert area.latitude_offset_code == code
    assert area.longitude_offset_code == code


@pytest.mark.parametrize("code", range(10))
def test_every_df_range_code_is_stable_from_miles(code):
    assert a.Bearing(270, 2**code, 1, hit_ratio=7 / 8).range_code == code


@pytest.mark.parametrize(
    "model,values",
    [
        (
            a.Area,
            {
                "shape": "open_circle",
                "color": "blue",
                "latitude_offset_deg": -0.001,
                "longitude_offset_deg": 0,
            },
        ),
        (
            a.Area,
            {
                "shape": "open_circle",
                "color": "blue",
                "latitude_offset_deg": 6.535,
                "longitude_offset_deg": 0,
            },
        ),
        (
            a.Bearing,
            {
                "bearing_deg": 270,
                "hit_ratio": 0.875,
                "range_miles": 0,
                "accuracy_deg": 1,
            },
        ),
        (
            a.Bearing,
            {
                "bearing_deg": 270,
                "hit_ratio": 0.875,
                "range_miles": 513,
                "accuracy_deg": 1,
            },
        ),
    ],
)
def test_semantic_dimensions_reject_unrepresentable_bounds(model, values):
    with pytest.raises(a.ModelError):
        model(**values)
    with pytest.raises(a.JSONModelError):
        a.from_json_dict(values, expected_type=model)
