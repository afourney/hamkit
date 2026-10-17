# APRS representation and codec coverage

This is the scope contract for the alpha API. **Representation is not codec
implementation or compliance.** Every payload family within the baseline below
has a public construction model, including historical and optional families.
Known field layouts use named dataclasses and aliases, not untyped dictionaries.
Unspecified vendor/extension grammars have explicitly named raw wrappers.

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
`CodecNotImplemented`; decoding generally returns `Opaque` or raises that error
according to `DecodeOptions.unsupported`. **Raw** means byte assembly/preservation,
not interpretation or semantic validation. Rows covering shared fields inherit
the capabilities of their enclosing payloads.

| Source / category                                                      | Public representation                                                                     | Wire support and boundary                                                                                                                                 |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| HDR; APRS101 pp.12–16,83–85: TNC2 addresses/path                       | `Header`, `Hop`, `Path`, `Packet`                                                         | Working monitor/RF token validation; ordered explicit `*` only                                                                                            |
| HDR, NME-015–036, OTH-038: destination/source metadata                 | `HeaderSemantics`, `Symbol`, `Grid`                                                       | Modeled interpretation of destination symbol/grid, source-SSID symbol, software ID and historical destination routing. Header tokens remain authoritative |
| POS: all four position DTIs                                            | `Position`, `Symbol`                                                                      | Working uncompressed unambiguous position; messaging/timestamp options                                                                                    |
| POS: ambiguity and unknown-position convention                         | `Ambiguity`, `Extent`; `Position.is_null_position`                                        | Ambiguity modeled; null convention working; no guessed exact fix for an ambiguous area                                                                    |
| TIM: DHM UTC/local, HMS UTC, MDHM UTC                                  | `Timestamp`, `TimestampKind`                                                              | DHM/HMS working; MDHM and raw-timestamp consistency checks modeled. No inferred year/offset                                                               |
| EXT: course/speed, altitude, range                                     | `Extensions`, `Motion`, `Altitude`, `Range`                                               | Modeled, with explicit units/encoding/reference and raw codes                                                                                             |
| EXT: PHG and direction finding                                         | `PHG`, `Signal`, `Bearing`                                                                | Modeled: power/height/gain/directivity, signal and NRQ codes, validity and derived quantities                                                             |
| CMP: compressed positions, csT precedence                              | `Position(encoding="compressed")`, `Compression`, `Extensions`                            | Modeled: type/fix/NMEA source/origin, ignored csT, motion/range/altitude. Encoders must validate mutually exclusive interpretations                       |
| MIC: current/old/beta Mic-E                                            | `MicE`, nested `Location`, `Extensions`                                                   | Modeled: DTI, comment bits/set, fix, type marker, destination evidence, longitude offset, grid/symbol, altitude/telemetry. Header context required        |
| OBJ: objects/items, live/kill, compressed/moving/weather               | `Object`, `Item`, nested `Location`                                                       | Modeled: identity plus exact padded name, lifecycle, timestamp and reusable location/extension fields                                                     |
| OBJ: areas/signposts                                                   | `Area`, `Signpost` in `Extensions`                                                        | Modeled: shape/color/offset codes, corrected anchor/offsets, corridor width, signpost label; rendering is outside scope                                   |
| WX: positionless, located, compressed, object weather                  | `Weather`; `Extensions.weather` on `Position` / `Location`                                | Modeled; located weather retains its enclosing position/object identity                                                                                   |
| WX: missing/zero/raw sensor data and water gauges                      | `Weather`, `Measurement`, `WaterHeight`, `Unit`                                           | Modeled: wind/gust/temp/humidity/pressure, three rain windows, snow, luminosity, raw counter, software/device, height/datum                               |
| WX: hurricanes/tropical storms/depressions                             | `Storm` in `Extensions`                                                                   | Modeled: predicted flag, sustained/gust wind, pressure and three radii                                                                                    |
| TLM: classic, MIC, legacy Mic-E, base91 comment, relaxed compatibility | `Telemetry`, `TelemetryEncoding`, `AnalogChannels`, `DigitalChannels`                     | Modeled: sequence/raw sequence, MIC comma variant, ordered missing channels, raw values. Calibration is not applied implicitly                            |
| TLM: PARM/UNIT/EQNS/BITS                                               | `Definition`, `Parameters`, `Units`, `Equations`, `Calibration`, `Bits`                   | Modeled: target, partial/empty channels, coefficients, sense bits, project title and raw fields                                                           |
| MSG: ordinary/group messages                                           | `Message`                                                                                 | Working basic printable text/ID. Group addressees retained; delivery/ack policy not inferred                                                              |
| MSG: ack/rej, reply-ack and automatic answers                          | `Acknowledgment`, `ReplyAck`, `AutoAnswer`                                                | Basic ack/rej working; reply-ack/auto-answer modeled. New ID and previous ack are separate                                                                |
| MSG: bulletins, announcements, group bulletins, NWS                    | `Bulletin`, `NWSBulletin`                                                                 | Modeled: ID/group/announcement/legacy flag; NWS reference is separate from ordinary message ID                                                            |
| MSG: NTS records N#, NA, NP, N1–N6, NS, NR                             | `Radiogram`, `NTSRecord`, `NTSHeader`, `Address`, `Phone`, `Text`, `Signature`, `Routing` | Modeled named record fields; no radiogram assembly/state machine                                                                                          |
| QRY: general/directed/unknown queries and footprints                   | `Query`, `Footprint`                                                                      | Modeled open query name, recipient, heard station and additional argument bytes                                                                           |
| QRY: direct stations/heard history/path responses                      | `Response`, `ResponseValue`, `DirectStations`, `HeardStation`, `Trace`                    | Modeled refinements. Generic response text still decodes as `Message`; it is not claimed as structured response decoding                                  |
| QRY: capability announcements                                          | `Capabilities`, `Capability`                                                              | Modeled ordered tokens with optional values; unknown token names permitted                                                                                |
| STA: status/grid/beam                                                  | `Status`, `Grid`, `Beam`, `Symbol`                                                        | Text and DHM UTC working; grid/beam modeled. Other timestamp-looking text stays text                                                                      |
| NME: GGA/GLL/RMC/VTG/WPL                                               | `NMEA`, `NMEASentence`, `GGA`, `GLL`, `RMC`, `VTG`, `WPL`, `NMEAMetadata`                 | Modeled explicit sentence fields, raw time/date, checksum and fix validity; no automatic trusted position or datum conversion                             |
| NET: third-party encapsulation                                         | `ThirdParty(Packet(...))`                                                                 | Working bounded recursion, including binary and opaque inner packets; inner header supplied to decoding                                                   |
| NET: APRS-IS path and no-gate/no-archive conventions                   | `Header.path`, `HeaderSemantics.q_construct`, raw payload bytes                           | Tokens retained; annotation slot modeled. Routing/archive/authentication policy and station state are outside packet codecs                               |
| OTH: user-defined/experimental                                         | `UserDefined`                                                                             | Working one-byte ID/type plus arbitrary binary data; user payload semantics remain private                                                                |
| OTH: explicit invalid/test                                             | `Invalid`                                                                                 | Working raw body; never interpreted as a position                                                                                                         |
| OTH: raw vendor weather `!!`, `#`, `$ULTW`, `*`                        | `RawWeather`                                                                              | Named raw wrapper with optional externally interpreted `Weather`; vendor grammar not inferred; codec modeled only                                         |
| APRS101 Appendix 1 p.103: Agrelo DFJr/MicroFinder `%`                  | `Agrelo`                                                                                  | Bearing and quality-code representation modeled; no guessed quality meaning                                                                               |
| OTH: obsolete bracket Maidenhead beacon                                | `Maidenhead`, `Grid`                                                                      | Modeled historical wrapper                                                                                                                                |
| OTH: historical X1J, obsolete object/bulletin, non-APRS beacon         | `LegacyPosition`, `Object.legacy`, `Bulletin.legacy`, `Beacon`                            | Modeled. Historical profile currently raises explicitly; modern decoder does not search for embedded position DTIs                                        |
| OTH: reserved/unknown DTIs, future/undocumented data                   | `Reserved`, `Opaque`, `Diagnostic`                                                        | Raw reserved construction, opaque recovery. No invented grammar for reserved map/shelter slots                                                            |
| Addendum-linked polygon/line or other external vendor grammar          | `ExternalExtension`                                                                       | Named raw wrapper with specification URL; numerical interpretation remains unresolved pending an authoritative grammar                                    |
| FAP-only extensions cited by corpus                                    | `DAO`, `PHG.rate_per_hour`, `Telemetry`, `RawWeather`, raw codes                          | Represented without asserting compatibility decoding. `compatibility-fap` is an explicitly unavailable codec profile                                      |
| BAD: malformed supported payloads                                      | `DecodeOptions`, `Opaque`, `Diagnostic`                                                   | Working strict error or explicit raw recovery; no trusted partial fix manufactured                                                                        |
| SEQ: station state, ownership, retries, calibration history            | Packet models above                                                                       | Sequence inputs representable; state machines are outside this stateless module                                                                           |
| AEA, AX.25/KISS/FCS, modem/radio                                       | `Header` plus payload after adapter normalization                                         | Outside payload scope; AEA adapter not implemented. TNC2 LF/CRLF helpers are working                                                                      |

`get_capabilities()` provides a per-payload-machine-readable summary, and
`capability_for(value_or_type)` returns one entry. A `partial` entry is not a
promise that every combination of that model is encodable. The constructor
examples in `tests/model_examples.py` are checked against **every member of
`Payload` and every public dataclass**; extending the public surface requires
extending those examples and the capability registry.

## Encoding and decoding contracts

- `encode_packet_fields(Packet(...)) -> EncodedPacketFields` is the authoritative
  joint header/information boundary. `serialize_packet` uses the returned header.
  Mic-E's latitude/comment bits belong in the destination, so this layer will
  coordinate both halves. `EncodeOptions.destination="derive"` permits deriving
  that destination from semantic fields; `"require_match"` requires agreement
  with the template. The Mic-E codec is not yet implemented: both modes raise,
  rather than returning an inconsistent pair.
- `decode_payload(info, header=...)` supplies the outer address context. Mic-E
  without a header raises `ContextRequired`, even under opaque recovery; full
  packet parsing always supplies the header. Other header-derived annotations
  can use the same boundary later.
- `encode_payload(payload, header=...)` is a convenience for information-only
  output. If joint encoding changes the header, it raises `ContextRequired`;
  callers must use the joint result instead of losing the new destination.
- `Position.tail` is an unsliced, uninterpreted suffix. Structured extensions
  use `Position.extensions` plus `comment`. These are alternative authoring
  sources; supplying both tail and comment raises. Structured extensions
  currently raise `CodecNotImplemented`, never get silently discarded.
- `Location` is shared spatial content for Mic-E, objects and items, without
  station-report timestamp/messaging flags. `Position.location` exposes that
  view of a station report. Object/item encoding and compression choices live
  on their wrappers; Mic-E has its own encoding metadata. Unsupported encoders
  do not yet validate all field combinations. Models are construction values,
  **not proofs of validity**. `validate_packet` means wire encodability and also
  raises when no codec exists.
- Raw evidence fields never grant permission to override conflicting semantic
  values silently. Future codecs must validate consistency. `HeaderSemantics`
  is interpretation-only metadata, excluded from equality, and does not override
  `Header`. `original_wire` remains an archival copy, not a serialization cache.

## Recovery, framing and limitations

`parse_packet` consumes an unframed byte sequence. It does not trim or reject
binary CR/LF inside information. `parse_tnc2_line` instead requires exactly one
LF/CRLF terminator and rejects embedded delimiters; its `original_wire` excludes
the terminator. `serialize_tnc2_line` emits CRLF and rejects non-line-safe data.
All 256 byte values are tested in `UserDefined.data` in monitor mode; RF size
limits still apply. Text input is only a reversible Latin-1 byte carrier.

`DecodeOptions` separates unsupported (`opaque` default / `raise`) from malformed
supported fields (`raise` default / `opaque`). Recovered payloads include a typed
diagnostic. Unknown input is not claimed to have a valid known representation.
Invalid outer envelopes, wrong Python types, missing context and depth limits
still raise. Empty information can be retained by malformed recovery, but its
opaque model is not serializable as a valid APRS packet; retain `original_wire`
for exact evidence. Known message validation can reject high-bit text; explicit
malformed recovery retains it without endorsing it. This is **not universal
lossless recovery or a complete conformance validator**.

`max_depth` counts third-party wrappers (default 4, configurable 0–32). The same
bound is enforced in both directions. The outer validation profile does not
force RF address rules on Internet-origin inner envelopes; nested monitor
validation and the outer RF information-size limit still apply.

## Genuine ambiguities and scope gaps

- Wind units in uncompressed complete weather and zero-pair semantics remain
  disputed in the corpus. `Measurement.unit="disputed_knots_or_mph"` and raw
  evidence can represent an unresolved reading. No converter chooses silently.
- Raw vendor weather layouts, external polygon/line geometry, and detailed
  Agrelo quality meanings need additional authoritative definitions. Named raw
  models preserve these boundaries rather than fabricating fields.
- The area correction specifies numeric offsets/anchors, not a complete rendering
  algorithm. `Area` stores codes and corrected quantities; map rendering is out.
- Live symbol/TOCALL registries, later APRS 1.2 proposals (including new radiation
  formats), generic NMEA variants, and compatibility acceptance of malformed
  input are not exhaustively specified by this baseline.
- Historical/FAP profiles are modeled option values, but explicitly unavailable;
  their behavioral rules and station-state sequences still need implementation.

These are the limits of “everything represented.” All **defined payload families
in this baseline** have a model; undefined grammars have honest raw boundaries.
This is not a guarantee that future specifications require no additional fields
or classes. No comprehensive vector-compliance claim is made.

Weather and telemetry use the same semantic model as a full payload or nested
field. Metadata is retained in both contexts; neither has a wire codec yet.
See [the naming audit](NAMING.md) for the public-name changes.
