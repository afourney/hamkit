# hamkit.aprs

Pure Python, MIT-licensed APRS parsing **and composition**, with no runtime
dependencies. This is an alpha public API foundation, not a complete APRS
implementation. Python 3.10+ is supported.

```python
from hamkit.aprs import (
    Header, Message, Packet, PathHop, Position, Status,
    parse_packet, serialize_packet,
)

packet = Packet(
    Header("N0CALL", "APRS", (PathHop("WIDE1-1"),)),
    Position(latitude_deg=49.058333333333, longitude_deg=-72.029166666667),
)
wire = serialize_packet(packet, profile="rf")
assert wire == b"N0CALL>APRS,WIDE1-1:!4903.50N/07201.75W-"
received = parse_packet(wire)
assert isinstance(received.payload, Position)

message = Packet(Header("N0CALL", "APRS"), Message("W1AW", b"Hello", "003"))
assert serialize_packet(message) == b"N0CALL>APRS::W1AW     :Hello{003"
assert parse_packet(b"N0CALL>APRS:>Ready").payload == Status(b"Ready")
```

## Public API and organization

- `parse_packet(bytes | str, *, profile="monitor") -> Packet` reads one TNC2
  monitor packet. Strings are Latin-1 byte carriers, as specified by the vector
  document; arbitrary Unicode and implicit UTF-8 conversion are not supported.
- `serialize_packet(Packet, *, profile="monitor") -> bytes` constructs wire
  data from fields. `validate_packet` performs the same checks without returning
  bytes. `validate_header` checks only the envelope.
- `decode_payload(bytes) -> Payload` and `encode_payload(Payload) -> bytes`
  operate on information fields including their data type identifier.
- Immutable dataclasses: `Packet`, `Header`, `PathHop`, `Position`, `Symbol`,
  `Timestamp`, `Status`, `Message`, `Acknowledgment`, `Opaque`. Construct these
  directly; validation happens at codec boundaries, not dataclass initialization.
- Named annotation aliases: `Payload`, `Path`, `WireInput`, `ValidationProfile`,
  `TimestampKind`, `CoordinateAxis`. The distribution includes `py.typed`.
- `hamkit.aprs.fields` exports `encode_coordinate`, `decode_coordinate`,
  `encode_timestamp`, `decode_timestamp`. These units are independent of packet
  framing and ready for focused encoding/decoding vectors.
- `APRSError` is the `ValueError` base for `EnvelopeError`, `FieldError`, and
  `UnsupportedFormat`. Wrong Python input types may raise `TypeError`.

`models.py`, `validation.py`, `codec.py`, and `fields/` separate values,
validation, packet dispatch/composition, and primitive codecs. No network, radio,
station-state, routing, retransmission, or delivery-policy layer is included.

## Supported scope

| Area           | Implemented                                                                                 | Deferred / retained without interpretation                                                                   |
| -------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Envelope       | TNC2 source, destination, ordered path and explicit trailing `*`                            | AX.25/KISS/AEA framing, destination dispatch policies, APRS-IS server rules                                  |
| Positions      | `!`, `=`, `/`, `@`; uncompressed, unambiguous WGS-84 coordinates; symbol table/code/overlay | Ambiguous and compressed positions become `Opaque`; Mic-E, objects/items, DAO and extensions are not decoded |
| Timestamps     | DHM UTC (`z`), DHM local (`/`), HMS UTC (`h`); transmitted components only                  | Weather MDHM, clock/date resolution                                                                          |
| Status         | Text and optional DHM UTC timestamp, 62-byte body limit                                     | Grid and beam/ERP extensions remain in text                                                                  |
| Messages       | Nine-byte padded addressee, basic text, 1–5 alphanumeric ID, exact basic `ack`/`rej`        | Reply-ack, bulletins, NWS, definitions, directed queries, automatic answers and NTS become `Opaque`          |
| Other families | Byte-preserving `Opaque`                                                                    | Weather, telemetry, queries, NMEA, third-party nesting, vendor/historical formats                            |

`Position.tail` is bytes after the symbol, **not** a parsed comment: it may
contain weather, motion, altitude, DAO or other extensions. `Status.text` likewise
does not claim to extract status extensions. Basic `Message` is a container and
does not infer ack requests or group-delivery rules. Use `Opaque(information)`
to construct formats not yet supported, explicitly taking responsibility for
those payload bytes; only envelope/framing checks apply to opaque content.

Parsing unsupported families returns `Opaque` with the entire information field
and a reason. Malformed supported fields raise `FieldError`; the parser does not
silently turn these failures into valid values. Ambiguous/unsupported position
representations are retained without validating their unimplemented grammar.
This parser is not a general APRS conformance validator.

`monitor` validation preserves address case, explicit SSIDs and Internet path
tokens such as `qAR`; it checks token syntax but does not assert RF validity.
`rf` additionally enforces uppercase 1–6 alphanumeric addresses, SSIDs 0–15,
at most eight hops and at most 256 information bytes. Neither mode authorizes
transmission. CR/LF transport delimiters are rejected, never stripped. Payload
bytes and whitespace are retained; message text has its narrower printable-byte
and 67-byte constraints. Input must contain a nonempty information field.

## Round trips and original bytes

`Packet.original_wire` retains the exact bytes passed to `parse_packet` and is
excluded from semantic equality. It is archival evidence: replacing a dataclass
field does not update this attribute. `serialize_packet` always encodes the
current fields, never the stored wire. Access `original_wire` explicitly when
exact received bytes are needed.

Coordinates encode to hundredths of minutes with half-up rounding and degree
carry; the decoded quantized value can differ from the input float. Compare
semantic round trips against that quantized value, not arbitrary encoder input.
Signed zero is retained where practical, but compares equal numerically.
`Position.is_null_position` identifies the zero-coordinate indeterminate-symbol
convention; an ordinary numeric (0, 0) is not automatically a missing fix.
Timestamps never invent missing month/year or local UTC offsets. Bytes in tails,
status and opaque payloads avoid lossy text decoding. `Message.addressee_raw`
provides its nine-character padded form; leading spaces and case are preserved.

## Development and vectors

```console
python -m pip install -e packages/aprs
python -m unittest discover -s packages/aprs/tests -v
```

From `packages/aprs`, `hatch build` and `hatch run types:check` use the existing
HamKit build/type conventions. Alternatively install `build`, `mypy`, `black`
and `ruff`, then run:

```console
python -m build packages/aprs
mypy --config-file packages/aprs/pyproject.toml packages/aprs/src/hamkit/aprs packages/aprs/tests
black --check packages/aprs/src packages/aprs/tests
ruff check packages/aprs/src packages/aprs/tests
```

The local [compliance vector document](docs/APRS_COMPLIANCE_VECTORS.md) is the
implementation reference: APRS101 plus its documented APRS 1.1 corrections,
with FAP compatibility treated separately. Its profile/outcome and Latin-1
contracts guide this foundation; the full corpus has not been transcribed or
claimed as passing. No GPL code or `aprslib` is used.

See [fixture guidance](tests/fixtures/README.md) for the profile-aware loader,
semantic adapter, field/packet test structure and future vector integration.
Focused tests cover construction, decoding, quantization, malformed fields,
framing, opaque preservation and semantic versus wire round trips.

## License

`hamkit-aprs` is distributed under the terms of the [MIT](LICENSE) license.
