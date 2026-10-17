# APRS representation and codec coverage

This is the scope contract for the alpha API. **Representation is not codec
implementation or compliance.** Every payload family within the baseline below
has a public construction model, including historical and optional families.
Known field layouts use named dataclasses and aliases, not untyped dictionaries.
Unimplemented vendor/extension grammars have explicitly named raw wrappers.
See [unresolved specification questions](UNRESOLVED_SPEC.md) for source gaps and profile decisions.

## Baseline and authority

The baseline is [APRS_COMPLIANCE_VECTORS.md](APRS_COMPLIANCE_VECTORS.md), edition 1:
APRS101 1.0.1; the APRS 1.1 addendum and corrections cited there; and the explicitly
identified compatibility extensions in its pinned FAP appendix. It is **not**
all future APRS 1.2 proposals, arbitrary NMEA sentences, or every vendor protocol.
No FAP or GPL implementation is incorporated.

This review cross-checked the document's family headings, expected-field schemas,
ambiguity decisions and selected cases against the [APRS101 reference](https://www.aprs.org/doc/APRS101.PDF),
[1.1 addendum](https://www.aprs.org/aprs11.html),
[weather notes](https://www.aprs.org/aprs11/spec-wx.txt),
[DF notes](https://www.aprs.org/APRS-docs/DF.TXT),
[area correction](https://www.aprs.org/aprs11/areaobjects.txt) and
[reply-ack notes](https://www.aprs.org/aprs11/replyacks.txt). Consulted 2026-10-17;
live links are not immutable revisions. Local vector references below are the
reproducible source for the scope decisions. Page numbers refer to printed pages.

## Coverage matrix

**Working** means the named subset has functional tests. **Modeled** means Python
values can be constructed but structured wire encoding raises
`CodecNotImplementedError`; decoding generally returns `Opaque` or raises that
error, as `parse_packet(..., unsupported=...)` selects. **Raw** means byte assembly/preservation,
not interpretation or semantic validation. Rows covering shared fields inherit
the capabilities of their enclosing payloads.

| Source / category                                                      | Public representation                                                                                                | Wire support and boundary                                                                                                                        |
| ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| HDR; APRS101 pp.12–16,83–85: TNC2 addresses/path                       | `Header`, `Hop`, `Path`, `Packet`                                                                                    | Working monitor/RF token validation; ordered explicit `*` only                                                                                   |
| HDR, NME-015–036, OTH-038: destination/source metadata                 | `Header`, `Symbol`, `Grid`                                                                                           | Header tokens retained exactly. Destination symbol/grid, source-SSID symbol, software ID and destination routing are not interpreted yet         |
| POS: all four position DTIs                                            | `Position`, `Symbol`                                                                                                 | Working uncompressed unambiguous position; messaging/timestamp options                                                                           |
| POS: ambiguity and unknown-position convention                         | `Position.ambiguity`, `ambiguity_extent`, `Extent`; `Position.is_null_position`                                      | Ambiguity digits modeled with a computed cell; null convention working; no guessed exact fix for an ambiguous area                               |
| TIM: DHM UTC/local, HMS UTC, MDHM UTC                                  | `Timestamp`, `TimestampKind`                                                                                         | DHM/HMS working; MDHM modeled; raw timestamp is evidence, not an encoding override. No inferred year/offset                                      |
| EXT: course/speed, altitude, range                                     | `Extensions`, `Motion`, `Altitude`, `Range`                                                                          | Working on uncompressed positions: CSE/SPD (including unknown and zero pairs), `/A=` feet and RNG. Compressed and Mic-E altitude modeled         |
| EXT: PHG and direction finding                                         | `PHG`, `Signal`, `Bearing`                                                                                           | Working on uncompressed positions: PHG, DFS and DF bearing/NRQ codes; derived radii and ranges are properties. Q-to-accuracy mapping not imposed |
| CMP: compressed positions, csT precedence                              | `Position(encoding="compressed")`, `Compression`, `Extensions`                                                       | Modeled: type/fix/NMEA source/origin, ignored csT, motion/range/altitude. Encoders must validate mutually exclusive interpretations              |
| MIC: current/old/beta Mic-E                                            | `MicE`, `MicEMessage`, `Extensions`                                                                                  | Modeled: position, message type, fix, ambiguity, device code, motion/altitude/telemetry. Header context required                                 |
| OBJ: objects/items, live/kill, compressed/moving/weather               | `Object`, `Item`, `Extensions`                                                                                       | Modeled: name, lifecycle, timestamp, position, compression and extension fields                                                                  |
| OBJ: areas/signposts                                                   | `Area`, `Signpost` in `Extensions`                                                                                   | Modeled: shape/color/offset codes, corrected anchor/offsets, corridor width, signpost label; rendering is outside scope                          |
| WX: positionless, located, compressed, object weather                  | `Weather`; `Extensions.weather` on `Position`, `Object`, `Item`                                                      | Modeled; located weather retains its enclosing position/object identity                                                                          |
| WX: missing/zero/raw sensor data and water gauges                      | `Weather`, `Measurement`, `WaterHeight`, `Unit`                                                                      | Modeled: wind/gust/temp/humidity/pressure, three rain windows, snow, luminosity, raw counter, software/device, height/datum                      |
| WX: hurricanes/tropical storms/depressions                             | `Storm` in `Extensions`                                                                                              | Modeled: predicted flag, sustained/gust wind, pressure and three radii                                                                           |
| TLM: classic, MIC, legacy Mic-E, base91 comment, relaxed compatibility | `Telemetry`, `TelemetryEncoding`, `AnalogChannels`, `DigitalChannels`                                                | Modeled: sequence/raw sequence, MIC comma variant, ordered missing channels, raw values. Calibration is not applied implicitly                   |
| TLM: PARM/UNIT/EQNS/BITS                                               | `TelemetryDefinition`, `TelemetryParameters`, `TelemetryUnits`, `TelemetryEquations`, `Calibration`, `TelemetryBits` | Modeled: target, partial/empty channels, coefficients, sense bits and project title                                                              |
| MSG: ordinary/group messages                                           | `Message`                                                                                                            | Working: UTF-8 text, message ID and reply-ack. Group addressees retained; delivery/ack policy not inferred                                       |
| MSG: ack/rej, reply-ack and automatic answers                          | `Acknowledgment`, `Message.reply_ack`, `AutoAnswer`                                                                  | ack/rej and reply-ack working; auto-answer modeled                                                                                               |
| MSG: bulletins, announcements, group bulletins, NWS                    | `Bulletin`, `NWSBulletin`                                                                                            | Modeled: identifier (announcement when a letter), group; NWS reference is separate from an ordinary message ID                                   |
| MSG: NTS records N#, NA, NP, N1–N6, NS, NR                             | `Radiogram`, `NTSRecord`, `NTSHeader`, `NTSAddress`, `NTSPhone`, `NTSText`, `NTSSignature`, `NTSRouting`             | Modeled named record fields; no radiogram assembly/state machine                                                                                 |
| QRY: general/directed/unknown queries and footprints                   | `Query`, `Footprint`                                                                                                 | Modeled open query name, recipient, heard station and additional argument bytes                                                                  |
| QRY: direct stations/heard history/path responses                      | `Response`, `ResponseValue`, `DirectStations`, `HeardStation`, `Trace`                                               | Modeled refinements. Generic response text still decodes as `Message`; it is not claimed as structured response decoding                         |
| QRY: capability announcements                                          | `Capabilities`, `Capability`                                                                                         | Modeled ordered tokens with optional values; unknown token names permitted                                                                       |
| STA: status/grid/beam                                                  | `Status`, `Grid`, `Beam`, `Symbol`                                                                                   | UTF-8 text and DHM UTC working; grid/beam modeled. Other timestamp-looking text stays text                                                       |
| NME: GGA/GLL/RMC/VTG/WPL                                               | `NMEA`, `NMEASentence`, `GGA`, `GLL`, `RMC`, `VTG`, `WPL`, `NMEAMetadata`                                            | Modeled explicit sentence fields, raw time/date, checksum and fix validity; no automatic trusted position or datum conversion                    |
| NET: third-party encapsulation                                         | `ThirdParty(Packet(...))`                                                                                            | Working bounded recursion, including binary and opaque inner packets; inner header supplied to decoding                                          |
| NET: APRS-IS path and no-gate/no-archive conventions                   | `Header.path`, raw payload bytes                                                                                     | Tokens retained, including q constructs. Routing/archive/authentication policy and station state are outside packet codecs                       |
| OTH: user-defined/experimental                                         | `UserDefined`                                                                                                        | Working one-byte ID/type plus arbitrary binary data; user payload semantics remain private                                                       |
| OTH: explicit invalid/test                                             | `Invalid`                                                                                                            | Working raw body; never interpreted as a position                                                                                                |
| OTH: raw vendor weather `!!`, `#`, `$ULTW`, `*`                        | `RawWeather`                                                                                                         | Named raw wrapper with optional externally interpreted `Weather`; vendor grammar not inferred; codec modeled only                                |
| APRS101 Appendix 1 p.103: Agrelo DFJr/MicroFinder `%`                  | `Agrelo`                                                                                                             | Bearing and quality-code representation modeled; no guessed quality meaning                                                                      |
| OTH: obsolete bracket Maidenhead beacon                                | `Maidenhead`, `Grid`                                                                                                 | Modeled historical wrapper                                                                                                                       |
| OTH: historical X1J, obsolete object/bulletin, non-APRS beacon         | `LegacyPosition`, `Beacon`                                                                                           | Modeled. Obsolete object/bulletin forms stay Opaque; the decoder does not search for embedded position DTIs                                      |
| OTH: reserved/unknown DTIs, future/undocumented data                   | `Reserved`, `Opaque`, `Diagnostic`                                                                                   | Raw reserved construction, opaque recovery. No invented grammar for reserved map/shelter slots                                                   |
| Addendum-linked polygon/line or other external vendor grammar          | `ExternalExtension`                                                                                                  | Named raw wrapper with specification URL; numerical interpretation remains unresolved pending an authoritative grammar                           |
| FAP-only extensions cited by corpus                                    | `DAO`, `PHG.rate_per_hour`, `Telemetry`, `RawWeather`, raw codes                                                     | Represented without asserting compatibility decoding                                                                                             |
| BAD: malformed supported payloads                                      | `Malformed`, `Diagnostic`                                                                                            | Working: undecodable fields yield Malformed with recovered data; out-of-spec but decodable input yields a Packet with nonconforming diagnostics  |
| SEQ: station state, ownership, retries, calibration history            | Packet models above                                                                                                  | Sequence inputs representable; state machines are outside this stateless module                                                                  |
| AEA, AX.25/KISS/FCS, modem/radio                                       | `Header` plus payload after adapter normalization                                                                    | Outside payload scope; AEA adapter not implemented. TNC2 LF/CRLF helpers are working                                                             |

`codec_support()` provides a per-payload machine-readable summary, and
`codec_support_for(value_or_type)` returns one entry. A `partial` entry is not a
promise that every combination of that model is encodable. The constructor
examples in `tests/model_examples.py` are checked against **every member of
`Payload` and every public dataclass**; extending the public surface requires
extending those examples and the codec registry.

## Validation tiers

- **Constructors** reject values that cannot exist on the wire or contradict
  another field: an out-of-range coordinate, an invalid timestamp, a `{` inside
  message text, a lowercase overlay on an uncompressed position. These raise
  `ModelError` from Python and `JSONModelError` from JSON. A Malformed parse
  result means a received field failed this tier.
- **Conformance** covers APRS limits a transmitter could still break: lengths,
  reserved characters, control characters, required weather slots, symbol
  requirements for storms, DF and areas, data-extension slot conflicts, telemetry
  layouts, and RF address/size limits with `profile="rf"`. Received packets
  keep these findings in `Packet.diagnostics`. `check_packet` lists them, and
  `serialize_packet` raises `ConformanceError` rather than send them.
- Values that follow from other fields are properties, so they cannot
  contradict: grid bounds and center, PHG ranges, bearing range and manual flag,
  area offsets and anchor, compression type byte, bulletin announcement flag
  and the ambiguity cell.

## Encoding and decoding contracts

- `serialize_packet` re-validates the whole model, raises
  `CodecNotImplementedError` for families without an encoder, then raises
  `ConformanceError` with every finding before any bytes are produced.
  `validate_packet` performs exactly the same checks. `original_wire` is never
  replayed.
- Mic-E's latitude and message bits belong in the destination address, so a
  future Mic-E encoder derives the destination inside `serialize_packet`.
  `serialize_payload` raises `ContextRequiredError` for Mic-E, as
  `parse_payload` does without `header=`; full packet parsing always supplies
  the header.
- `Position.comment` (and the comment on objects, items and Mic-E) is the free
  text after the data extensions. Course/speed, PHG, RNG, DFS, DF bearing and
  `/A=` altitude are decoded into `extensions` and encoded from them. Text shaped
  like an extension with invalid values (such as `361/010`) stays in `comment`
  with a nonconforming finding. Recognized syntax without a decoder yet (DAO,
  positioned weather, storms, areas, signposts, base91 telemetry) makes the
  payload `Opaque`, and encoding those extensions raises
  `CodecNotImplementedError`; nothing is silently discarded. Before sending,
  conformance re-reads the encoded extensions and comment and refuses a comment
  that would be read back differently, or extension values with no exact wire
  form. Measurements are rounded to whole units, like coordinates; code-table
  values (PHG power, height, gain, directivity) must be exact.
- `Position`, `Object`, `Item` and `MicE` carry latitude, longitude and symbol
  directly, and share the `coordinates` and `ambiguity_extent` properties.
  Compression is present exactly when `compression` is set.
- Raw evidence fields never override structured values and are ignored by
  equality. Future codecs must validate consistency rather than prefer evidence.

## Recovery, framing and limitations

`parse_packet` consumes an unframed byte sequence. It does not trim or reject
binary CR/LF inside information. `parse_tnc2_line` instead requires exactly one
LF/CRLF terminator and rejects embedded delimiters; its `original_wire` excludes
the terminator. `serialize_tnc2_line` emits CRLF and rejects non-line-safe data.
All 256 byte values are tested in `UserDefined.data` in monitor mode; RF size
limits still apply. Wire input is `bytes` only.

Free text decodes as UTF-8, following the APRS 1.2 proposed-draft guidance
adopted for compatibility; invalid UTF-8 falls back to Latin-1 with a
nonconforming diagnostic. Protocol tokens are printable
ASCII. See [unresolved specification questions](UNRESOLVED_SPEC.md#text-encoding-ascii-and-utf-8).

`parse_packet` returns a Packet unless a header or implemented payload field
cannot be decoded; then it returns one top-level Malformed. `parse_payload`
uses the same boundary for a standalone payload. Malformed contains
original_wire, diagnostics with field paths, recovered ordinary JSON in the
normal schema, and the typed `header` when it was intact. It never appears
inside Packet.payload. Missing or undecodable values are not invented.
Corrected recovered data goes through ordinary JSON construction to become a
Packet.

`unsupported` (`"opaque"` / `"raise"`) and `malformed` (`"return"` / `"raise"`)
are independent keyword options. Unknown or unimplemented formats are
unsupported, not malformed. Context and resource failures raise. A broken outer
header can still recover supported inner fields. Nested third-party failures
produce one outer Malformed with nested diagnostic paths.

`max_third_party_depth` counts third-party wrappers (default 4, configurable
0–32), in both directions. RF address rules apply to the transmitted header
only, not to Internet-origin inner envelopes; the outer RF information-size
limit still applies.

## Genuine ambiguities and scope gaps

- Wind units in uncompressed complete weather and zero-pair semantics remain
  disputed in the corpus. `Measurement.unit="disputed_knots_or_mph"` and raw
  evidence can represent an unresolved reading. No converter chooses silently.
- Peet vendor layouts have manufacturer documentation but no implemented codec.
  External polygon/line geometry and detailed Agrelo quality meanings still need
  verified authoritative definitions. Named raw
  models preserve these boundaries rather than fabricating fields.
- The area correction specifies numeric offsets/anchors, not a complete rendering
  algorithm. `Area` stores codes and corrected quantities; map rendering is out.
- Live symbol/TOCALL registries, later APRS 1.2 proposals (including new radiation
  formats), generic NMEA variants, and compatibility acceptance of malformed
  input are not exhaustively specified by this baseline.
- Historical and FAP compatibility profiles are not implemented; their
  behavioral rules and station-state sequences still need a design.

These are the limits of “everything represented.” All **defined payload families
in this baseline** have a model; undefined grammars have honest raw boundaries.
This is not a guarantee that future specifications require no additional fields
or classes. No comprehensive vector-compliance claim is made.

Weather and telemetry use the same semantic model as a full payload or nested
field. Conformance checks the slots and encoding variants each context requires;
neither has a wire codec yet.
See [the naming guide](NAMING.md) for model names and their meanings.
