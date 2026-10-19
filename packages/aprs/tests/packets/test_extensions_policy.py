# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Extension catalogue and policy construction (wire effects are case vectors)."""
from typing import Any, get_args

import pytest

from hamkit import aprs as a

BASELINE = a.APRS_IS(extensions=set())


@pytest.mark.parametrize("factory", [a.RF, a.APRS_IS])
def test_factory_defaults_and_explicit_empty(factory):
    default = factory()
    assert set(default.extensions) == set(a.SUPPORTED_EXTENSIONS) - {
        "mice_hex_as_device",
        "water_height_tenths",
        "w_symbol_motion",
    }
    assert factory(extensions=set()).extensions == ()
    explicit = factory(extensions={"mice_device_ids"}, max_information_bytes=0)
    assert explicit.extensions == ("mice_device_ids",)
    assert explicit.max_information_bytes == 0
    assert a.from_json(a.to_json(default)) == default


def test_direct_policy_construction_and_fully_resolved_json():
    policy = a.EnvelopePolicy(
        source_pattern="src_[0-9]+",
        destination_pattern="dst_[A-Z]+",
        path_address_pattern="via_[a-z]+",
        max_path_entries=1,
        max_information_bytes=12,
        max_tnc2_line_bytes=None,
        extensions={"utf8_text"},
        byte_fallback="reject",
        legacy_positions=False,
    )
    # HDR case vectors cover decoding and sending under this policy.
    data = a.to_json_dict(policy)
    assert data["extensions"] == ["utf8_text"]
    assert data["max_tnc2_line_bytes"] is None
    assert len(data) == 10  # tag plus every resolved policy field
    assert a.from_json_dict(data, expected_type=a.EnvelopePolicy) == policy
    data.pop("type")
    assert a.from_json_dict(data, expected_type=a.EnvelopePolicy) == policy
    data.pop("max_path_entries")
    with pytest.raises(a.JSONModelError):
        a.from_json_dict(data, expected_type=a.EnvelopePolicy)
    assert a.EnvelopePolicy(".*", ".*", ".*").extensions == ()


@pytest.mark.parametrize(
    "extensions", [("unknown",), ("high_speed",), ("dao", "dao"), "dao"]
)
def test_unknown_duplicate_or_invalid_extensions(extensions: Any):
    with pytest.raises((TypeError, ValueError)):
        a.RF(extensions=extensions)


def test_json_conflicting_tag_and_unknown_extension():
    data = a.to_json_dict(BASELINE)
    with pytest.raises(a.JSONModelError):
        a.from_json_dict(data, expected_type=a.Packet)
    data["extensions"] = ["unknown"]
    with pytest.raises(a.JSONModelError):
        a.from_json_dict(data)


CATALOG = [
    ("utf8_text", "additive", True),
    ("dao", "comment", True),
    ("base91_telemetry", "comment", True),
    ("mice_device_ids", "comment", True),
    ("mice_hex_as_device", "reinterpretive", False),
    ("expanded_telemetry", "additive", True),
    ("phg_rate", "comment", True),
    ("weather_extensions", "additive", True),
    ("water_height_tenths", "reinterpretive", False),
    ("w_symbol_motion", "reinterpretive", False),
]


def test_catalog_classification_is_exhaustive_and_immutable():
    assert (
        set(a.EXTENSION_KINDS)
        == set(a.SUPPORTED_EXTENSIONS)
        == set(get_args(a.Extension))
    )
    assert set(a.EXTENSION_KINDS) == {identifier for identifier, _, _ in CATALOG}
    with pytest.raises(TypeError):
        a.EXTENSION_KINDS["mice_device_ids"] = "additive"  # type: ignore[index]


@pytest.mark.parametrize("identifier,kind,enabled", CATALOG)
def test_catalog_default_rule(identifier, kind, enabled):
    assert a.EXTENSION_KINDS[identifier] == kind
    for factory in (a.RF, a.APRS_IS):
        assert (identifier in factory().extensions) is enabled
        assert identifier in factory(extensions={identifier}).extensions
        assert not factory(extensions=set()).extensions
        assert all(
            a.EXTENSION_KINDS[x] in {"additive", "comment"}
            for x in factory().extensions
        )
