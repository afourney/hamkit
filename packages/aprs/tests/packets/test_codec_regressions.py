# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Regressions that case vectors cannot express (tests/cases holds the rest)."""
from __future__ import annotations

import dataclasses
import random

import pytest

from case_tool import all_rows
from hamkit import aprs as a
from semantics import without_evidence


def packet(raw, policy=None):
    policy = a.APRS_IS() if policy is None else policy
    value = a.parse_packet(raw, policy=policy)
    assert isinstance(value, a.Packet)
    return value


def test_truncation_and_mutation_do_not_escape_recovery():
    rng = random.Random(4)
    # Captured traffic (TRF) is long and adds time more than variety here.
    rows = [r for r in all_rows() if r["tnc2"] and not r["id"].startswith("TRF-")]
    for raw in sorted({r["tnc2"].encode("latin1") for r in rows}):
        candidates = [raw[:i] for i in range(len(raw))]
        for _ in range(8):
            if raw:
                i = rng.randrange(len(raw))
                candidates.append(raw[:i] + bytes([rng.randrange(256)]) + raw[i + 1 :])
        for candidate in candidates:
            try:
                result = a.parse_packet(candidate)
            except (a.ContextRequiredError, a.ResourceLimitError):
                continue
            assert isinstance(result, (a.Packet, a.Malformed)), repr(candidate)
            assert result.original_wire == candidate


def test_mic_e_longitude_100_to_109_degrees_uses_specified_bytes():
    # APRS101 p.48 encodes 100-109 degrees as 'l'-'u'; bytes 28-37 decode to the
    # same values but include FS-US control characters.
    cases = [r for r in all_rows() if r["id"] in {f"MIC-{n}" for n in range(116, 126)}]
    assert len(cases) == 10
    for row in cases:
        raw = row["tnc2"].encode("latin-1")
        wire = a.serialize_packet(without_evidence(packet(raw)))
        assert wire == raw, row["id"]
        assert 108 <= wire[wire.index(b":") + 2] <= 117


def test_legacy_positions_keyword_matches_the_policy_switch():
    # The APRS101 p.18 search itself is covered by the OTH case vectors.
    raw = b"N0CALL>BEACON:X!4903.50N/07201.75W-"
    legacy = a.parse_packet(raw, policy=a.APRS_IS(legacy_positions=True))
    assert isinstance(legacy, a.Packet)
    assert a.parse_packet(raw, legacy_positions=True) == legacy
    framed = a.parse_tnc2_line(raw + b"\r\n", legacy_positions=True)
    assert framed.payload == legacy.payload
    payload = a.parse_payload(raw.partition(b":")[2], legacy_positions=True)
    assert payload == legacy.payload
    with pytest.raises(TypeError):
        a.parse_packet(raw, legacy_positions="yes")


def test_nmea_symbol_requires_header_context():
    # The NME case vectors cover the SSID symbols and header mismatches.
    p = packet(b"N0CALL-11>APRS:$GPGLL,4916.45,N,12311.12,W,225444,A")
    with pytest.raises(a.ContextRequiredError, match="NMEA symbol"):
        a.serialize_payload(p.payload)


def test_timestamp_from_datetime():
    import datetime as dt

    moment = dt.datetime(
        2026, 10, 17, 23, 45, 30, tzinfo=dt.timezone(dt.timedelta(hours=-4))
    )
    assert a.Timestamp.from_datetime(moment) == a.Timestamp.dhm(18, 3, 45)
    assert a.Timestamp.from_datetime(moment, "hms_utc") == a.Timestamp.hms(3, 45, 30)
    assert a.Timestamp.from_datetime(moment, "mdhm_utc") == a.Timestamp.mdhm(
        10, 18, 3, 45
    )
    local = a.Timestamp.from_datetime(moment, "dhm_local")
    assert local == a.Timestamp.dhm(17, 23, 45, local=True)
    with pytest.raises(ValueError):
        a.Timestamp.from_datetime(dt.datetime(2026, 1, 1))  # offset unknown


def test_altitude_encoding_is_keyword_only():
    with pytest.raises(TypeError):
        a.Altitude(a.Measurement(1, "feet"), "mic_e")  # type: ignore[misc]
    assert a.Altitude(a.Measurement(1, "feet"), encoding="mic_e").encoding == "mic_e"


def test_models_refuse_contradictory_values():
    # Sending refusals are case vectors; these fail when the model is built.
    with pytest.raises(a.ModelError):
        a.Bearing(270, 16, 1, hit_ratio=0.5, manual=True)
    received = packet(b"N0CALL>APRS:$GPGLL,4916.45,N,12311.12,W,225444,A").payload
    with pytest.raises(a.ModelError):
        a.Packet(a.Header("N0CALL", None), received)  # No symbol to derive from.
    unsigned = dataclasses.replace(
        received, metadata=a.NMEAMetadata("GP", checksum=False)
    )
    with pytest.raises(a.ModelError):
        dataclasses.replace(unsigned, comment="hello")
    header = a.NTSHeader(
        number="12",
        precedence="routine",
        originator="N0CALL",
        check="5",
        place="REDMOND WA",
        date="OCT 15",
    )
    with pytest.raises(a.ModelError):
        dataclasses.replace(header, precedence="R")


def test_compression_type_byte_takes_names():
    csT = a.Compression(fix="current", nmea_source="other", origin="kpc3")
    assert csT.type_value == 32 + 0 + 4  # current fix, other source, KPC3 origin
