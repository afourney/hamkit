# Case vectors

Packet behaviour is tested here. Each `.jsonl` file holds one family of cases
(`pos`, `mic`, `nme`, `wx`, `msg`, `hdr`, `bad`, `fap`, ...), one JSON object per
line, with exactly these fields in this order:

| Field            | Checked | Meaning                                                                                                                       |
| ---------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `id`             | unique  | Stable identifier (`EXT-001`). Docs and comments refer to rows by id; never renumber.                                         |
| `comment`        | no      | Provenance, what the case tests, and any decision that explains the expected output.                                          |
| `tnc2`           | yes     | The packet as a Latin-1 byte carrier (one character per byte; use `tnc2.encode("latin-1")`), or `null` for an encode-only row. |
| `policy`         | yes     | The complete `EnvelopePolicy`, exactly as `to_json_dict(policy, include_defaults=True)` writes it.                             |
| `decoded`        | yes     | With `tnc2`: the exact `to_json_dict(parse_packet(...), include_defaults=True)`. Without: the input, in the same full form.     |
| `reencoded`      | yes     | What `serialize_packet` sends (Latin-1 carrier), or `null` when sending fails.                                                |
| `encoding_error` | yes     | The expected error, or `null`. Exactly one of `reencoded` and `encoding_error` is `null`.                                     |
| `fap`            | no      | FAP's output for the same packet, for auditing; `implementation` names which FAP produced it.                                 |

`encoding_error` mirrors how the library reports the failure:

- `{"type": "ConformanceError", "diagnostics": [...]}`, with each finding in the
  same form as `decoded` diagnostics. `check_packet` must return exactly these.
- `{"type": "<ErrorClass>", "message": "..."}` otherwise, for example
  `TypeError` for a `Malformed` decode (it cannot be sent), `FieldError`, or
  `JSONModelError` when an encode-only row's `decoded` is not a valid model.

Every row with `tnc2` has a `fap` snapshot from
[go-aprs-fap](https://github.com/hessu/go-aprs-fap) at commit
`94c7118ca94d251990382b9210112ddd5b260efa` (the Go port of Ham::APRS::FAP),
recorded by `tests/fap_snapshot`:
`header`, every exported `Packet` field under `fields`, and `error` when FAP
rejects the packet. Strings use the same Latin-1 carrier as `tnc2`; byte fields
are one character, or `null` when zero. `Timestamp` is kept only for NMEA, where
FAP computes it from the sentence's own date; elsewhere FAP completes it from
the wall clock, so it is left out. `options` records the FAP options used; rows
not taken from FAP's own tests use `ax25` exactly when their `policy` is RF.
Encode-only rows have `fap: null`.

Ids with a suffix derive from another row: `X-P` is packet `X` under a
permissive envelope policy (any address, no limits), so its payload is still
decoded and sent although `X`'s policy refuses the header; `X-R` is `X` after an
explicit repair (a known-bad NMEA checksum cleared).

`traffic_sample.jsonl` (`TRF-` ids) is a curated sample of live APRS-IS traffic
(a several-hour capture from the Pacific Northwest), under `APRS_IS()`: the
first two packets of each shape and software family. A row's shape is its
payload type, the diagnostics it gets (indices and quoted text removed), and
whether FAP rejects it; its software family is the first four characters of the
destination (`case_tool.shape` and `case_tool.software`). Its ids are line
numbers into the original distinct-line list, so they have gaps.

## Sweeping captured traffic

Raw captures stay outside the repository. To check one:

```sh
(cd tests/fap_snapshot && go build -o fapsnapshot .)   # Go 1.26 or later
python tests/case_tool.py sweep capture.tnc2 --fap tests/fap_snapshot/fapsnapshot
```

`sweep` runs every distinct line through the parser, FAP and the runner's
checks, and reports runner failures (bugs), how our accept/reject compares with
FAP's, and shapes not yet in any case file. `--add tests/cases/traffic_sample.jsonl`
then appends up to `--per` (default 2) rows for each new shape and software
family, with FAP's output; review them like any other change. Use
`--policy rf` for an RF capture. `python tests/case_tool.py fap BINARY [FILE...]`
fills in missing `fap` snapshots for rows added by hand.

## What the runner checks

`tests/test_cases.py` checks every row every way it can. JSON comparisons are
exact: `-0.0` differs from `0.0`, and `1` from `1.0`.

With `tnc2`:

1. `parse_packet` under `policy` gives exactly `decoded`, and so does
   `parse_tnc2_line` on the line ended by CRLF or LF.
2. `from_json_dict(decoded)` rebuilds the parsed value exactly.
3. The encoding checks below, for both the parsed and the rebuilt value. The
   value with received evidence removed must also be refused the same way, or
   read back with the same meaning.

Without `tnc2`:

1. `from_json_dict(decoded)` either fails exactly as `encoding_error` says, or
   writes back exactly `decoded` (inputs are in full form).
2. The encoding checks below.

Encoding checks: `serialize_packet` gives `reencoded` or fails as
`encoding_error`; `validate_packet` agrees; `check_packet` returns exactly the
`ConformanceError` findings (none otherwise); `serialize_tnc2_line` gives
`reencoded` plus CRLF; `serialize_payload` gives its information field, unless
the payload needs header context. Whatever is sent parses back as a `Packet`
with no diagnostics, re-encodes to the same bytes (also without evidence), and
survives a JSON round trip.

The runner also requires the exact field list, a nonempty `comment`, unique
ids across all files, and a policy in canonical form.

## Changing expectations

Expectations are reviewed, never regenerated blindly:

```sh
python tests/case_tool.py propose            # print rows that no longer match
python tests/case_tool.py propose --write    # apply them, then review the diff
```

Every changed expectation needs a `comment` that explains why the new output is
right. `decoded` comes from the library, so the review, the comment and `fap`
are what keep a bug from becoming the expected answer.

To add a case, append a row with `tnc2` (or `decoded` for an encode-only case),
`policy`, `comment` and `fap`, set the three expectation fields to `null`, and
run `propose --write`; then check the result against the specification.

What does not fit a row stays in Python: model construction and validation
errors, the JSON API, computed properties, parser options such as
`malformed="raise"`, and properties checked over many generated inputs.
