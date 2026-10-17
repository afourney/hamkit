# hamkit.aprs

Pure Python, MIT-licensed APRS packet models, parsing and composition, with no
runtime dependencies. Python 3.10+. This is an **alpha API**: the documented
payload families are represented, but many codecs are explicitly unimplemented.
See the [spec-to-model coverage matrix](docs/API_COVERAGE.md) for the full scope,
capabilities, ambiguities and source references.

```python
from hamkit.aprs import (
    Header, Packet, PathHop, Position, Message, Status,
    parse_packet, serialize_packet,
)

packet = Packet(
    Header("N0CALL", "APRS", (PathHop("WIDE1-1"),)),
    Position(latitude_deg=49.058333333333, longitude_deg=-72.029166666667),
)
wire = serialize_packet(packet, profile="rf")
assert wire == b"N0CALL>APRS,WIDE1-1:!4903.50N/07201.75W-"
assert isinstance(parse_packet(wire).payload, Position)

message = Packet(Header("N0CALL", "APRS"), Message("W1AW", b"Hello", "003"))
assert serialize_packet(message) == b"N0CALL>APRS::W1AW     :Hello{003"
assert parse_packet(b"N0CALL>APRS:>Ready").payload == Status(b"Ready")
```

Models are ordinary immutable dataclasses. Creating a value does not imply that
its grammar is valid or its codec exists:

```python
from hamkit.aprs import (
    CodecNotImplemented, Extensions, Location, Measurement, ObjectReport,
    Timestamp, Weather, capability_for, encode_payload,
)

weather = Weather(
    temperature=Measurement(32, "fahrenheit", raw=b"032"),
    wind_speed=Measurement(None, "mph", raw=b"..."),
)
report = ObjectReport(
    "AID #2",
    Location(49, -72, extensions=Extensions(weather=weather)),
    Timestamp("dhm_utc", hour=12, minute=30, day=17),
    alive=True,
)
assert capability_for(report).encode == "unimplemented"
try:
    encode_payload(report)
except CodecNotImplemented:
    pass  # Representable today; do not pretend that wire encoding succeeded.
else:
    raise AssertionError("ObjectReport codec is not implemented yet")
```

`None` on a weather field means absent. `Measurement(None, unit, raw)` means a
transmitted unavailable reading. A measured zero is a separate value. `Location` holds shared spatial content for Mic-E, objects and items;
`Position.location` exposes the same view of a station report. Models
also cover compressed/Mic-E positions, ambiguity cells, position extensions,
storms, telemetry/definitions, specialized messages/NTS, queries/responses,
NMEA, third-party packets and legacy/vendor families. No catch-all dictionary
is used in place of defined structured fields. All public names are exported
from `hamkit.aprs`; nested aliases such as `Payload`, `NTSRecord`, `NMEASentence`,
`TelemetryDefinitionData`, `Path`, and `QueryResponseData` support annotations.

## Public boundaries

- `parse_packet(wire, *, profile="monitor", options=DecodeOptions()) -> Packet`
  reads one **unframed** TNC2 byte sequence. `str` is a Latin-1 byte carrier.
- `serialize_packet(packet, *, profile="monitor", options=EncodeOptions()) -> bytes`
  constructs current fields. `validate_packet` checks the same encodability;
  missing codecs raise `CodecNotImplemented`, a `NotImplementedError` and
  `UnsupportedFormat` subclass. `validate_header` checks the envelope alone.
- `encode_packet_fields(packet, ...) -> EncodedPacketFields` returns the header
  **and** information field together. This is the joint boundary for Mic-E's
  destination-encoded fields; `EncodeOptions.destination` selects `derive` or
  `require_match`. Mic-E itself still raises explicitly.
- `decode_payload(info, *, header=None, options=...) -> Payload` accepts outer
  context. Mic-E requires `header`; packet parsing supplies it automatically.
  `encode_payload(payload, *, header=None, options=...) -> bytes` cannot silently
  discard a changed destination; use `encode_packet_fields` for joint encoding.
- `parse_tnc2_line` and `serialize_tnc2_line` handle LF/CRLF transport separately.
  Raw packet APIs preserve binary CR/LF; line helpers reject embedded delimiters.
- `get_capabilities()` and `capability_for(value_or_type)` distinguish working,
  partial, raw and unimplemented model codecs. Partial support is not a promise
  for every field combination.
- `hamkit.aprs.fields` provides independent coordinate/timestamp codecs. DHM/HMS
  work; MDHM is represented but explicitly unimplemented.

`models.py` holds packet families/context; `data.py` holds shared fields;
`nmea.py` holds sentence values; `codec.py`, `validation.py`, `transport.py` and
`fields/` keep interpretation, validation, framing and primitive codecs separate.
`py.typed` is included. There is no network/radio I/O or retained station state.

## Working codecs and recovery

Working: TNC2 headers, uncompressed/unambiguous positions, DHM/HMS timestamps,
basic status/messages/acks, bounded third-party nesting, user-defined binary
payloads and explicit invalid/test data. Reserved/opaque byte construction also
works. Other structured codecs raise; see the matrix for details.

`DecodeOptions(unsupported="opaque", malformed="raise")` is the default.
Unsupported data is retained with a diagnostic; malformed supported data raises.
Set `unsupported="raise"` to require a supported decoder, or `malformed="opaque"`
to recover an invalid information field. Invalid outer envelopes, missing context
and resource limits still raise. Recovery is not universal or conformance proof.
The default nesting limit is four third-party wrappers, configurable from 0–32.

`profile="monitor"` retains case, SSIDs and Internet path tokens; `"rf"` imposes
uppercase 1–6 alphanumeric addresses, SSIDs 0–15, eight hops, and 256 information
bytes. These are envelope rules, separate from `options.specification`, whose
historical/FAP values currently raise explicitly. No mode authorizes transmission.

## Semantic fields and exact wire

`Packet.original_wire` is archival evidence, excluded from equality. Replacing a
field does not update it; serialization always uses current fields. Coordinates
quantize to hundredths of minutes with half-up rounding. Timestamps do not invent
years/offsets. `Position.is_null_position` distinguishes the indeterminate-symbol
convention from an ordinary numeric `(0, 0)` fix.

`Position.tail` retains the unsliced suffix, which may include extensions/weather.
Structured authoring uses `extensions` and `comment` instead. Parsed basic
positions currently populate `tail`, not `comment`; constructing a comment then
parsing yields equivalent wire content, not identical dataclass field allocation.
`Status.text` likewise retains undecoded status extensions. Structured extensions
never get silently dropped: their codecs raise until implemented. Header-derived
annotations are metadata and do not override authoritative header tokens.

## Development and vectors

```console
python -m pip install -e packages/aprs
python -m unittest discover -s packages/aprs/tests -v
```

From `packages/aprs`, `hatch build` and `hatch run types:check` follow HamKit
conventions. Alternatively install `build`, `mypy`, `black` and `ruff`:

```console
python -m build packages/aprs
mypy --config-file packages/aprs/pyproject.toml packages/aprs/src/hamkit/aprs packages/aprs/tests
black --check packages/aprs/src packages/aprs/tests
ruff check packages/aprs/src packages/aprs/tests
```

The [vector document](docs/APRS_COMPLIANCE_VECTORS.md) remains authoritative for
its profiles. [Fixture guidance](tests/fixtures/README.md) describes the loader
and semantic adapter; comprehensive vector population is future work. Model
construction tests cover every payload/public dataclass, and regression tests
cover working codecs, explicit unimplemented errors, context, recovery and framing.
No GPL code or `aprslib` is used.

## Migration from the initial scaffold API

- Raw packet parsing now preserves CR/LF information bytes. Use the new line
  helpers if the input includes a transport terminator.
- Third-party, user-defined and invalid/test packets now return their typed models.
- Non-UTC timestamp-looking status text is preserved, correcting TIM-019/020.
- Empty information is a `FieldError`, recoverable only by explicit payload policy.
- Existing basic constructors and packet signatures remain usable; new context
  and policy options are keyword-only. The package version is `0.0.1a2`.

## License

`hamkit-aprs` is distributed under the terms of the [MIT](LICENSE) license.
