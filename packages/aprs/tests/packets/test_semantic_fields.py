# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Component constraints (the wire anchors for semantic fields are case vectors)."""

import pytest

from hamkit import aprs as a


@pytest.mark.parametrize(
    "model,values",
    [
        (a.UTCTime, {"hour": 24, "minute": 0}),
        (a.UTCTime, {"hour": 12, "minute": 0, "second": 60}),
        (a.UTCTime, {"hour": 23, "minute": 59, "second": 61}),
        (a.NMEADate, {"day": 29, "month": 2, "year_mod_100": 23}),
        (a.NMEADate, {"day": 31, "month": 4}),
        (a.NMEADate, {"year_mod_100": 2026}),
    ],
)
def test_component_constraints_match_python_and_json(model, values):
    with pytest.raises(a.ModelError):
        model(**values)
    with pytest.raises(a.JSONModelError):
        a.from_json_dict(values, expected_type=model)
