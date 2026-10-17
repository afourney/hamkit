# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Stored expectations preserve source information without runtime reshaping."""

import copy

import pytest
from generate_vectors import records
from packets.test_corpus import check, rows

from hamkit import aprs as a

ROWS = rows()
FAP_ACCEPTED = [
    row
    for row in ROWS
    if row["profile"] == "compatibility-fap" and row["outcome"] == "accept"
]
WEATHER = [
    row
    for row in FAP_ACCEPTED
    if row["source_expected"]["fap_fields"]["Wx"] is not None
    # FAP-465 diverges: its weather symbol carries no weather fields.
    and row["id"] != "FAP-465"
]
NMEA = [
    row
    for row in FAP_ACCEPTED
    if row["source_expected"]["fap_fields"]["Format"] == "nmea"
    # FAP-362 diverges: an incomplete GLL sentence is Malformed.
    and row["expected"].get("type") != "malformed"
]
LEGACY = [
    row
    for row in ROWS
    if row["expected"].get("payload", {}).get("type") == "legacy_position"
]


def test_regeneration_does_not_consult_decoders(monkeypatch):
    from hamkit.aprs import _codec

    def forbidden(*args, **kwargs):
        raise AssertionError("Expectations must come from source assertions")

    for module in (a, _codec):
        for name in ("parse_packet", "parse_payload"):
            monkeypatch.setattr(module, name, forbidden)
    assert sorted(records(), key=lambda row: row["id"]) == sorted(
        ROWS, key=lambda row: row["id"]
    )


@pytest.mark.parametrize("row", WEATHER, ids=lambda row: row["id"])
def test_weather_expectations_preserve_physical_measurements(row):
    """Convert stored measurements BACK to the captured source units."""
    fields = row["source_expected"]["fap_fields"]
    expected = row["expected"]["payload"]
    if expected["type"] == "raw_weather":
        assert expected["information"] == row["packet"].partition(":")[2]
        assert expected["format"] == "ultimeter_2000"
        weather = expected["weather"]
    elif expected["type"] == "weather":
        weather = expected
    else:
        weather = expected["extensions"]["weather"]
    for source, target in (
        ("WindDirection", "wind_direction"),
        ("WindSpeed", "wind_speed"),
        ("WindGust", "gust"),
        ("Temp", "temperature"),
        ("Humidity", "humidity"),
        ("Pressure", "pressure"),
        ("Rain1h", "rain_1h"),
        ("Rain24h", "rain_24h"),
        ("RainMidnight", "rain_since_midnight"),
        ("Snow24h", "snow_24h"),
        ("Luminosity", "luminosity"),
        ("Radiation", "radiation"),
        ("BatteryVoltage", "battery_voltage"),
    ):
        original = fields["Wx"][source]
        if original is None:
            continue
        if target not in weather and "divergence" in row:
            continue  # A reviewed divergence reads this field differently.
        reading = weather[target]
        value, unit = reading["value"], reading["unit"]
        if source in ("WindSpeed", "WindGust"):
            # Only a reviewed divergence may keep the disputed unit.
            if unit == "disputed_knots_or_mph" and "divergence" in row:
                unit = "mph"
            assert unit in ("mph", "m/s")
            value = value * 0.44704 if unit == "mph" else value
        elif source == "Temp":
            assert unit in ("fahrenheit", "celsius")
            value = (value - 32) / 1.8 if unit == "fahrenheit" else value
        elif source.startswith("Rain") or source == "Snow24h":
            assert unit in ("inches", "mm")
            value = value * 25.4 if unit == "inches" else value
        else:
            assert (
                unit
                == {
                    "WindDirection": "degrees",
                    "Humidity": "percent",
                    "Pressure": "hPa",
                    "Luminosity": "W/m2",
                    "Radiation": "nSv/h",
                    "BatteryVoltage": "volts",
                }[source]
            )
        assert value == pytest.approx(original, abs=1e-12, rel=1e-12)
    if fields["Format"] == "compressed":
        assert "motion" not in expected["extensions"]
        assert weather["wind_direction"] == {
            "value": fields["Course"],
            "unit": "degrees",
        }
        assert weather["wind_speed"]["unit"] == "knots"
        assert weather["wind_speed"]["value"] * 1.852 == pytest.approx(
            fields["Speed"], abs=1e-12
        )
    if fields["Wx"]["WaterLevel"] is not None:
        height = weather["water_height"]["measurement"]
        assert height["unit"] == "feet"
        assert height["value"] * 0.3048 == pytest.approx(fields["Wx"]["WaterLevel"])
    # Indoor readings have no model field and remain source provenance.
    for field in ("TempIn", "HumidityIn"):
        assert f"$.fap_fields.Wx.{field}" in row["unmapped"]


@pytest.mark.parametrize("row", NMEA, ids=lambda row: row["id"])
def test_nmea_observations_are_stored_in_typed_fields(row):
    source = row["source_expected"]["fap_fields"]
    payload = row["expected"]["payload"]
    sentence = payload["sentence"]
    assert sentence["coordinates"] == {
        "latitude_deg": source["Latitude"],
        "longitude_deg": source["Longitude"],
    }
    if source["Speed"] is not None:
        assert sentence["speed_knots"] * 1.852 == pytest.approx(
            source["Speed"], abs=1e-12
        )
    diverged = "divergence" in row  # Course precision and default symbol.
    if source["Course"] is not None:
        assert sentence["course_deg"] == pytest.approx(
            source["Course"], abs=0.5 if diverged else 0
        )
    if source["Altitude"] is not None:
        assert sentence["altitude_msl"] == {
            "value": source["Altitude"],
            "unit": "meters",
        }
    assert diverged or payload["symbol"] is None
    assert source["SymbolTable"] is None and source["SymbolCode"] is None
    assert payload["metadata"]["checksum_valid"] == source["ChecksumOK"]
    # The source did not assert these sentence fields. Never invent them to make
    # an incomplete historical GLL report into a constructible public model.
    assert "time_utc" not in sentence and "fix_status" not in sentence


@pytest.mark.parametrize("row", LEGACY, ids=lambda row: row["id"])
def test_legacy_wrappers_preserve_position_values_and_comment(row):
    expected = row["expected"]["payload"]
    assert (
        expected["prefix"] + "!"
        == row["packet"].partition(":")[2].partition("!")[0] + "!"
    )
    position = expected["position"]
    source = row["source_expected"]
    if row["profile"] == "compatibility-fap":
        fields = source["fap_fields"]
        assert position["latitude_deg"] == fields["Latitude"]
        assert position["longitude_deg"] == fields["Longitude"]
        assert position["comment"] == fields["Comment"]
    else:
        assert position["latitude_deg"] == source["position"]["latitude_deg"]
        assert position["longitude_deg"] == source["position"]["longitude_deg"]
        assert position["comment"] == source["comment"]


@pytest.mark.parametrize("identifier", ["FAP-032", "FAP-357", "FAP-406", "FAP-491"])
def test_migrated_values_are_asserted_not_only_archived(identifier):
    row = copy.deepcopy(next(r for r in ROWS if r["id"] == identifier))
    payload = row["expected"]["payload"]
    if identifier == "FAP-032":
        payload["extensions"]["weather"]["wind_direction"]["value"] += 1
    elif identifier == "FAP-357":
        assert payload["sentence"]["course_deg"] == 27.9  # FAP reports 28.
        payload["sentence"]["course_deg"] = 28
    elif identifier == "FAP-406":
        payload["position"]["latitude_deg"] += 1
    else:
        payload["weather"]["temperature"]["value"] += 1
    with pytest.raises(AssertionError):
        check(row)


def test_conflicting_modern_beacon_interpretation_is_not_rewritten():
    for identifier in ("OTH-033", "OTH-035"):
        row = next(r for r in ROWS if r["id"] == identifier)
        assert row["expected"]["payload"] == {
            "type": "beacon",
            "text": row["source_expected"]["raw_text"],
        }


@pytest.mark.parametrize("identifier", ["FAP-005", "FAP-036", "FAP-345", "FAP-346"])
def test_mic_e_device_field_preserves_captured_comment(identifier):
    row = next(r for r in ROWS if r["id"] == identifier)
    payload = row["expected"]["payload"]
    # The type byte begins the status text and any version suffix ends it.
    head, suffix = payload["device_code"][0], payload["device_code"][1:]
    assert head == row["packet"].partition(":")[2][9]
    assert (
        head + payload["comment"] + suffix
        == row["source_expected"]["fap_fields"]["Comment"]
    )


def test_corrupted_mic_e_is_not_repaired():
    row = next(r for r in ROWS if r["id"] == "FAP-349")
    assert row["options"]["accept_broken_mice"]
    assert row["expected"] == {"original_wire": row["packet"], "type": "malformed"}
    assert row["divergence"]
