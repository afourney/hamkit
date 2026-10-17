# Documented APRS vectors

These 18 JSONL files retain all 1,541 individual packets and 23 sequence
occurrences from [edition 1](../../docs/APRS_COMPLIANCE_VECTORS.md): 1,564 rows and
1,548 case IDs. Every raw TNC2 byte, source expectation, receiver option and
provenance field of the original 1,561 rows is unchanged from PR #4. A frozen
integrity test protects that requirement, independently of regeneration; the
three cases added by the corpus amendment (WX-067–WX-069) are frozen separately.

Run from the repository root:

```sh
python -m pytest packages/aprs/tests -q
python packages/aprs/tests/generate_vectors.py
```

The generator translates source assertions, never parser output. The translated
expectations are stored in these JSONL files; comparisons do not convert them
back to the source schema. Schema changes include units/enums, explicit absence,
telemetry channel padding, structured query responses and typed NMEA sentences.
`packet` is a Latin-1 byte carrier:
use `packet.encode("latin-1")`, including for control/high-bit bytes.

## Runner configuration

Every row has a complete `policy` object with all nine `EnvelopePolicy` fields,
including explicit `null` for unlimited constraints. For example, an RF row has:

```json
{
  "policy": {
    "source_pattern": "[A-Z0-9]{1,6}(?:-(?:[0-9]|1[0-5]))?",
    "destination_pattern": "[A-Z0-9]{1,6}(?:-(?:[0-9]|1[0-5]))?",
    "path_address_pattern": "[A-Z0-9]{1,6}(?:-(?:[0-9]|1[0-5]))?",
    "max_path_entries": 8,
    "max_information_bytes": 256,
    "max_tnc2_line_bytes": null,
    "extensions": [],
    "legacy_positions": false,
    "byte_fallback": "latin-1"
  },
  "legacy_positions": false
}
```

The generator writes fully resolved policy data. Runners load it with
`aprs.from_json_dict(row["policy"], expected_type=aprs.EnvelopePolicy)`.
Zero limits remain zero and `null` remains unlimited. Every extension set is
explicit; changing factory defaults cannot change vector interpretation.

The stored envelope constraints retain **28 RF** and **1,536 APRS-IS** rows.
Source profiles/options and the separate `legacy_positions` field are retained
as provenance, not runtime selectors. The policy itself contains the legacy
setting. Extension selection is derived from source expectations and relevant
wire syntax without calling a decoder. Legacy Mic-E hex expectations exclude
`mice_device_ids`; modern device-code expectations select it. Expanded telemetry
is not silently enabled for source cases that require the original 0–255 limit.

The migration changes policy configuration only: packet bytes, expected public
fields, rejection categories, source assertions and provenance remain intact.
The original source integrity guard remains independent of regeneration.
Corpus and round-trip runners use each row's policy; focused tests cover direct
construction, custom limits, baseline/extension differences and factory defaults.

## Expectations and provenance

`expected` is a subset of the public JSON representation. Missing keys make no
assertion; explicit nulls do. `source_expected` preserves the original assertions.
`unmapped` lists source paths outside the JSON projection. For core rows,
`source_details.py` checks every such path using models, evidence or derived
properties, and core rejection cases also check retained headers and partial
observations. For FAP rows, unmapped paths are FAP's own output fields and are
kept as provenance only (PHG rows still check theirs from public models). Error
wording is represented by the public diagnostic scheme rather than copied
verbatim.

Every row compares `parse_packet` output with `expected` directly; there is
no receiver-emulation layer. FAP's own extra fields stay in `source_expected` as
provenance and are not asserted.

Where FAP's interpretation differs from the public decoder's, and the public
one follows the specification, `tests/fap_divergences.json` replaces the
FAP-derived expectation. Each override names its reasons: comment whitespace
kept as transmitted, callsign case, compressed course 0, disputed wind units,
NMEA default symbols and precision, packets FAP refuses but the specification
allows, Mic-E type codes, a corrupted Mic-E packet that FAP repairs, invalid
timestamps and incomplete GLL or telemetry that FAP accepts, short telemetry
FAP pads, and an `O` token FAP skips in weather reports. The
generator applies the overrides, copies the reasons into the row's
`divergence` field and leaves `outcome` and `source_expected` as FAP captured
them. Legacy position searches follow the explicit row setting described above.

The schema migration rewrote 35 stored expectations (33 FAP and two historical
position cases): equivalent weather units, compressed weather wind nesting,
`LegacyPosition`/`RawWeather` wrappers, four flattened NMEA observations, and four Mic-E device markers split from comments.
Offline conversion tests reverse unit changes back to the captured measurements
and verify stored fields against source values. The original `source_expected`
snapshots remain immutable provenance. Mapped packet facts and the documented
core supplemental assertions are executed; FAP-only output fields and
application-state facts are not codec assertions.

All 29 PHG/PHGR projections (including 15 FAP vectors) exercise the public
API directly. Their comment separators, whitespace, and numeric/alphabetic rates are
handled by the public codec. FAP's legacy-position wrapper and omitted trailing
telemetry channels are expressed using the existing JSON schema; original source
values remain unchanged and are also checked.

The 23 sequence packet occurrences are ordinary stateless tests, with substantive
`expected.header` and `expected.payload` assertions. The hand-authored
`../sequence_packet_expectations.json` derives them from the documented packet
bytes and cited APRS layouts, not parser snapshots. It checks names and alive
markers, coordinates/timestamps, message ID/reply-ack fields, raw telemetry and
definitions, bulletin text, beacon/status text, and positionless weather fields.
The generator guards each assertion with its exact input packet.

`sequence`, `profile: stateful`, `outcome: stateful`, titles and notes retain the
original source context. For these rows, `source_expected_scope` explicitly marks
`source_expected` as application-state provenance only; it is not executed.
There is no `state_expected`, test receiver, sequence replay, or assertion of
ownership, visibility, deduplication, pending acknowledgments, applied calibration,
bulletin replacement, status precedence or inherited weather coordinates.
Every sequence packet still participates in parsing, serialization and JSON
round trips independently of the preceding packets.

## Round trips

All 1,564 rows pass without xfails. Every row also participates in encoding tests:
1,305 semantic round trips under an explicit permissive envelope policy
(the row policy with envelope constraints relaxed), and 259 explicit malformed/conformance
refusals. Three intentionally bad NMEA checksums are refused until explicitly
repaired, then round-trip. The reviewed
`../roundtrip_exceptions.json` records exact reasons. Adding a new unexpected
refusal or silently fixing a recorded one fails the test; this file is not
regenerated by `generate_vectors.py`.

The `APRS_IS()` envelope constraints additionally refuse serialization for 15 of
those round-trippable packets because of their address formats (including SSID
`-0`). The tests assert those refusals separately and validate the other 1,290
under those envelope constraints with each row’s interpretation settings.
This preserves the source vectors while exercising both representation and
transport constraints through the public API.

Round-trip decoding and a separate serialization check use each row's stored
policy. Of the 1,305 representational round trips, 25 are refused by their stored
envelope policy (the 15 APRS-IS refusals above plus 10 RF-only refusals); the other
1,280 pass that policy. The permissive representation policy remains an explicit
test override, not a replacement for the row's policy. It allows invalid-address
vectors to test semantic encoding while their transport refusals are checked.

Round-trip tests remove all evidence fields before serialization, check semantic
fields at wire precision, and require canonical bytes to stabilize. Raw wrappers
retain `information` because it is their semantic content. JSON round trips are
also checked for every input, including `Malformed` results.

Tests and fixtures are repository resources, not runtime package data. The CI
workflow tests source and a freshly installed wheel. Pinned FAP provenance and
licensing attribution remain in the unchanged source document.
