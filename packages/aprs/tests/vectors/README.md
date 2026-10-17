# Documented APRS vectors

These 18 JSONL files contain every numbered case from
[`APRS_COMPLIANCE_VECTORS.md`](../../docs/APRS_COMPLIANCE_VECTORS.md), edition 1:
**1,538 individual packets plus 23 packet occurrences from seven sequences**.
Sequence IDs have a `.step` suffix; all 1,545 original case IDs are represented.
No packet bytes were dropped, trimmed or replaced. Malformed envelopes (including
empty input) and the explicitly labeled AEA example remain malformed/AEA; adding
an envelope would destroy the test. All ordinary inputs already have full TNC2
envelopes. Existing synthetic envelopes in the source supplements are retained;
this conversion adds none.

## Run and regenerate

From the repository root, after installing the package and `pytest>=8,<10`:

```sh
PYTHONPATH=packages/aprs/src python -m pytest packages/aprs/tests -q
python packages/aprs/tests/generate_vectors.py
```

`hatch run test` also works from `packages/aprs`. The existing unittest suite
still works, but **pytest is required to collect the JSONL corpus**. The APRS
vector workflow runs the entire suite against source and a freshly installed
wheel. Tests and vectors are repository resources, not runtime package data.

## Row contract

- `id`, `title`, `profile`, `source`, and optional `note`, `scope_note` and
  `extension_tags` preserve provenance, copied verbatim from the source case.
- `packet` is a **Latin-1 byte carrier**, not text to UTF-8 encode. Use
  `packet.encode("latin-1")`. JSON escapes preserve every control/high-bit byte.
  The generator checks source byte lengths and any supplied hex before writing.
- `source_expected` retains the complete original semantic assertions. FAP's
  documented top-level defaults are expanded before overlaying each snapshot.
  FAP options remain separate; only `ax25` maps to the existing RF profile.
- `expected` is an independently translated **subset of the public
  `to_json_dict(..., include_defaults=True)` representation**. An absent key
  makes no assertion; an explicit null does. This matches the source contract,
  which permits additional correctly decoded fields. These are not snapshots of
  current parser output. The generator imports no APRS parser or models.
- Projections use the model's wire units and enums. Rain is projected from the
  source's hundredths of an inch as inches (its millimetre conversions stay
  unmapped), so unavailable rain readings remain explicit nulls. Storm kinds
  map to `HC`/`TS`/`TD`, and Mic-E altitude to `mic_e`; an unknown source value
  fails generation. DF bearing `usable`/`accuracy_less_than_deg` are not
  projected: they derive from a quality-code mapping the sources dispute (see
  `docs/UNRESOLVED_SPEC.md`). FAP rows keep FAP's own metric weather units.
- `unmapped` lists source paths not consumed by the public-JSON projection.
  Their values remain in `source_expected`; passing the projection does **not**
  claim those assertions pass. Examples include derived grid/range views,
  routing/state policies, source-only encoding evidence, FAP recovery flags,
  and flattened FAP NMEA properties without sentence-level counterparts.
- For rejection cases, `expected` asserts lossless original bytes and `rejection`
  requires either `Malformed` or a `Packet` with nonconforming diagnostics.
  Source error classes and partial results remain intact. We do not invent
  exception wording or equate an unsupported opaque packet with rejection.
- `gap` identifies an explicitly reviewed expected failure. Its allowed-current
  values are failure guards, **not desired decoded outputs**.

No decoder implementation is used to generate desired expectations. Field and
unit renames, conversions, and FAP compatibility mappings are explicit in
`generate_vectors.py`. The integrity tests verify exact regeneration, unique IDs,
section/row counts, and that projected keys and enum values belong to public
JSON models, even for codecs that cannot yet decode their packets. Coordinate
tolerance is 1e-8
degrees; other floating measurements use 1e-6 absolute / 1e-9 relative tolerance.

## Expected failures and unresolved assertions

`vector_gaps.json` is a reviewed manifest tied to individual IDs. It is **not
automatically refreshed from test failures**. Every JSONL file and every line
gets a separate pytest case labeled `filename:line:vector-id`.

Only `KnownGap` can xfail. A missing codec must still return the specific recorded
unsupported diagnostic, preserve opaque bytes, and preserve the expected header.
A field gap must match the listed field paths and current values; a different
field mismatch or a parser exception fails normally. Passing a marked case is a
strict XPASS failure, prompting removal/review of that annotation. Harness tests
exercise both regression detection and completed-gap behavior.

The 23 sequence occurrences are explicitly unresolved (`expected: null`): their
source expectations are station state transitions, not packet model outputs.
They are collected and byte-preservation checked, then reported as expected
failures with the state-model reason. They need an independently reviewed packet
expectation/state adapter before they can become semantic passes; they are not
invented passing placeholders. No other packet entries are omitted from the
behavioral projections. Existing planned codec gaps, source compatibility
choices, and adapter/state work are distinct from parser regressions.

Currently the 1,561 corpus cases yield **642 passes and 919
expected failures**, including the 23 unresolved state occurrences. These are
projection results, not a claim of complete compliance with every source field.
The complete suite includes the pre-existing tests and harness checks.

| File      | Rows | Pass | Expected failure |
| --------- | ---: | ---: | ---------------: |
| hdr.jsonl |   51 |   51 |                0 |
| pos.jsonl |   68 |   56 |               12 |
| tim.jsonl |   20 |   17 |                3 |
| ext.jsonl |   50 |   50 |                0 |
| cmp.jsonl |  122 |    0 |              122 |
| mic.jsonl |  265 |    0 |              265 |
| obj.jsonl |   53 |    0 |               53 |
| wx.jsonl  |   66 |    0 |               66 |
| tlm.jsonl |   18 |    0 |               18 |
| msg.jsonl |   45 |   25 |               20 |
| qry.jsonl |   20 |    3 |               17 |
| sta.jsonl |   29 |    8 |               21 |
| nme.jsonl |   36 |    1 |               35 |
| net.jsonl |   15 |   14 |                1 |
| oth.jsonl |   38 |   24 |               14 |
| bad.jsonl |  125 |   66 |               59 |
| seq.jsonl |   23 |    0 |               23 |
| fap.jsonl |  517 |  327 |              190 |

FAP fixtures preserve the pinned upstream provenance and licensing attribution
in the source document's final section. No FAP implementation is imported.
