# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""PHG/PHGR wire behaviour is in the EXT and FAP case vectors; this guards coverage."""

from case_tool import all_rows


def has_phg(row):
    payload = (row["decoded"] or {}).get("payload") or {}
    if payload.get("type") == "legacy_position":
        payload = payload["position"]
    return bool((payload.get("extensions") or {}).get("phg"))


def test_related_phg_vectors_are_covered():
    """The case vectors (tests/cases) keep exercising PHG/PHGR from FAP's suite."""
    rows = [row for row in all_rows() if row["tnc2"] and has_phg(row)]
    fap = {row["id"] for row in rows if row["id"].startswith("FAP-")}
    assert {i for i in fap if not i.endswith("-P")} == {
        "FAP-001",
        "FAP-002",
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
