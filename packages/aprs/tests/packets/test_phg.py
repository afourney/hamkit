# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""PHG and PHGR use the public codec, including their comment boundaries."""

from dataclasses import replace

import pytest
from packets.test_corpus import check, public_phg_row, rows
from packets.test_roundtrip_corpus import without_evidence

from hamkit import aprs as a

PREFIX = b"!4903.50N/07201.75W#"
PHG_ROWS = [row for row in rows() if public_phg_row(row)]


@pytest.mark.parametrize("row", PHG_ROWS, ids=lambda row: row["id"])
def test_phg_vectors(row):
    check(row)


def test_related_phg_vectors_are_covered():
    assert {row["id"] for row in PHG_ROWS if row["id"].startswith("FAP-")} == {
        "FAP-001",
        "FAP-006",
        "FAP-028",
        "FAP-405",
        "FAP-415",
        "FAP-458",
        "FAP-459",
        "FAP-460",
        "FAP-461",
        "FAP-464",
        "FAP-466",
        "FAP-467",
        "FAP-468",
        "FAP-499",
        "FAP-501",
    }


@pytest.mark.parametrize("rate", range(36))
def test_phgr_rate_alphabet_and_required_separator(rate):
    code = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[rate : rate + 1]
    wire = PREFIX + b"PHG2130" + code + b"/Radio"
    value = a.parse_payload(wire)
    assert isinstance(value, a.Position)
    assert value.extensions.phg.rate_per_hour == rate
    assert value.comment == "Radio"
    assert a.serialize_payload(without_evidence(value)) == wire


@pytest.mark.parametrize(
    "comment", [b"6", b"6Radio", b"A", b"ZRadio", b"146.520MHz", b"a/hello"]
)
def test_rate_without_required_slash_is_comment(comment):
    value = a.parse_payload(PREFIX + b"PHG2130" + comment)
    assert isinstance(value, a.Position)
    assert value.extensions.phg.rate_per_hour is None
    assert value.comment == comment.decode()
    canonical = a.serialize_payload(without_evidence(value))
    assert canonical == PREFIX + b"PHG2130" + comment
    assert a.parse_payload(canonical) == value


@pytest.mark.parametrize("rate", [None, 6, 35])
@pytest.mark.parametrize(
    "comment",
    [
        "",
        "/hello",
        "//hello",
        "6/hello",
        "Z/hello",
        "hello/world",
        "A=001234",
        "A=-00123",
    ],
)
def test_composed_comments_preserve_slashes(rate, comment):
    value = a.Position(
        1,
        2,
        a.Symbol("/", "#"),
        comment=comment,
        extensions=a.Extensions(phg=a.PHG(4, 20, 3, rate_per_hour=rate)),
    )
    wire = a.serialize_payload(value)
    assert a.parse_payload(wire) == value


@pytest.mark.parametrize(
    "tail,rate,comment",
    [
        (b"PHG2130/hello", None, "hello"),
        (b"PHG2130//hello", None, "/hello"),
        (b"PHG21306//hello", 6, "/hello"),
        (b"PHG2130   hello  \t ", None, "hello"),
        (b"PHG21306/  hello  ", 6, "hello"),
        (b"PHG2130 /hello", None, "/hello"),
    ],
)
def test_phg_comment_delimiters(tail, rate, comment):
    raw = b"N0CALL>APRS:" + PREFIX + tail
    packet = a.parse_packet(raw)
    assert isinstance(packet, a.Packet)
    assert packet.original_wire == raw
    assert packet.payload.extensions.phg.rate_per_hour == rate
    assert packet.payload.comment == comment
    assert a.parse_packet(a.serialize_packet(without_evidence(packet))) == packet


@pytest.mark.parametrize("rate", [None, 6, 35])
def test_phg_rate_precedes_altitude_dao_and_telemetry(rate):
    value = a.Position(
        1,
        2,
        a.Symbol("/", "#"),
        comment="Radio",
        extensions=a.Extensions(
            phg=a.PHG(4, 20, 3, rate_per_hour=rate),
            altitude=a.Altitude(a.Measurement(1234, "feet"), encoding="feet_extension"),
            dao=a.DAO("W", precision="high"),
            telemetry=a.Telemetry((1, 2), sequence=3, encoding="base91_comment"),
        ),
    )
    wire = a.serialize_payload(value)
    rate_code = (
        b""
        if rate is None
        else b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[rate : rate + 1]
    )
    separator = b"" if rate is None else b"/"
    assert b"PHG2130" + rate_code + separator + b"/A=001234" in wire
    assert a.parse_payload(wire) == value


def test_phg_does_not_consume_altitude_as_comment_delimiter():
    value = a.parse_payload(PREFIX + b"PHG2130/A=001234Radio")
    assert isinstance(value, a.Position)
    assert value.extensions.phg.rate_per_hour is None
    assert value.extensions.altitude.measurement.value == 1234
    assert value.comment == "Radio"
    assert a.parse_payload(a.serialize_payload(without_evidence(value))) == value


@pytest.mark.parametrize(
    "payload,field,expected",
    [
        (b":DEST     :/Meet at A/B", "text", "/Meet at A/B"),
        (b":DEST     :PHG21306/hello", "text", "PHG21306/hello"),
        (b">/hello", "text", "/hello"),
        (PREFIX + b"/hello", "comment", "/hello"),
        (PREFIX + b" /hello ", "comment", " /hello "),
        (PREFIX + b"088/036/hello", "comment", "/hello"),
    ],
)
def test_other_text_does_not_lose_slashes(payload, field, expected):
    value = a.parse_payload(payload)
    assert getattr(value, field) == expected
    assert a.parse_payload(a.serialize_payload(without_evidence(value))) == value


@pytest.mark.parametrize("rate", [36, 100])
def test_unencodable_rate_is_reported_without_changing_public_model(rate):
    value = a.Position(
        1,
        2,
        a.Symbol("/", "#"),
        extensions=a.Extensions(phg=a.PHG(4, 20, 3, rate_per_hour=rate)),
    )
    with pytest.raises(a.ConformanceError, match="rate_per_hour"):
        a.serialize_payload(value)


def test_phg_comment_normalization_is_not_silent_on_transmit():
    value = a.parse_payload(PREFIX + b"PHG2130/Radio")
    with pytest.raises(a.ConformanceError, match="comment"):
        a.serialize_payload(replace(value, comment=" Radio "))
