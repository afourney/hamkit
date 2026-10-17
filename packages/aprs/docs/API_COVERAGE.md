# APRS codec coverage

Packet dataclasses, payload unions and the packet JSON schema are unchanged.
Envelope entry points now accept `policy=EnvelopePolicy(...)` instead of a
profile string, with public `RF` and `APRS_IS` presets. `APRS_IS` is the default.
Decoding and encoding cover the families exercised by all 1,564 occurrences in
[the edition 1 corpus](APRS_COMPLIANCE_VECTORS.md). Unknown grammars still use
`Opaque`; raw wrappers preserve authoritative information bytes.

| Family            | Decoding and encoding                                                                                                                                                      |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Envelope          | TNC2, configurable address patterns and size limits, RF/APRS-IS presets, explicit repeated hops, AEA normalization, bounded third-party nesting                            |
| Positions         | All four DTIs, ambiguity, compressed coordinates/csT, Mic-E destination-dependent latitude/message/hemisphere                                                              |
| Extensions        | Motion, altitude, PHG/rate, range, DF signal/bearing, DAO, area/corridor, signpost, storm, weather, base91 and Mic-E telemetry                                             |
| Objects/items     | Names, ownership information, alive/killed markers, compressed/uncompressed positions and extensions                                                                       |
| Weather           | MDHM positionless and located reports, unavailable readings, rain/humidity/pressure, luminosity, snow, water height, APRS 1.2 radiation and battery volts, device suffixes |
| Telemetry         | Classic samples (short reports decode as nonconforming), PARM/UNIT/EQNS/BITS, comment base91, old Mic-E hex/binary                                                         |
| Messages          | Ordinary messages, ack/rej, reply-ack, automatic answers, bulletins/announcements/groups, NWS envelopes, NTS records                                                       |
| Queries/responses | General/directed queries, footprints, heard-station operands, direct lists, hourly counts, trace headers, capabilities                                                     |
| Status            | Text, DHM, grid/symbol and beam/ERP                                                                                                                                        |
| NMEA              | GGA, GLL, RMC, VTG and WPL, checksums, independent fix usability, destination/source symbol conventions                                                                    |
| Historical/raw    | Grid beacons, X1J embedded positions (opt-in), plain beacons, Agrelo, user-defined, invalid/test, reserved and external raw formats                                        |
| Vendor weather    | Ultimeter 2000 measurements plus original bytes; other vendor modes retain bytes without invented measurements                                                             |

`codec_support()` and `codec_support_for()` describe these boundaries at runtime.
Raw models do not promise interpretation of arbitrary vendor or external grammars.
AX.25 framing, KISS, FCS, radio/modem operation and arbitrary NMEA sentences remain
outside this package's packet codec.

## Receiver profiles without an API change

The source vectors deliberately describe different receivers. The same TNC2
bytes can have different expectations: embedded `!` is a modern beacon versus a
legacy X1J position (opt in with `legacy_positions=True`); FAP trims comments,
converts weather units, rounds some values, and accepts certain incomplete
historical reports.

Schema-only differences are resolved in the stored JSONL expectations, not by
rewriting actual public output during comparison. The offline source-to-schema
generator preserves values while translating names, nesting and equivalent units;
it never consults a parser or expected decoder output.

The public codec is deterministic and preserves the richer wire interpretation.
There is no receiver-emulation layer: every vector compares public
`parse_packet` output with its stored expectation. FAP's own extra fields
(display resolution, raw timestamps, warnings, indoor sensors) describe that
library's output rather than this schema, so they remain source provenance
without assertions. The pinned reference implementation was consulted; it is
not a runtime dependency.

Incomplete historical GLL reports and invalid timestamps remain `Malformed` when
required facts cannot be constructed; `Malformed.recovered` keeps the intact
fields of positions, objects and status reports. No missing time, coordinate or
calibration coefficient is fabricated.

The completed schema migration rewrites 35 expectations (33 FAP, two historical
positions). It stores weather measurements in the public decoder's equivalent
units, compressed weather wind in `extensions.weather`, legacy positions inside
`LegacyPosition`, vendor readings inside `RawWeather.weather`, and captured NMEA
coordinates/speed/course/altitude/symbol/checksum assertions in typed fields. Four
Mic-E comments now store their device marker separately in `device_code`,
preserving every character.
The runtime weather-unit conversion, wrapper flattening, and NMEA source-schema
comparison have been removed. Source snapshots and all raw packet bytes remain
unchanged; inverse-unit and source-value tests check that no information was lost.

Historical and FAP rows parse with `legacy_positions=True`. Fifty-two FAP
expectations record where FAP's interpretation differs from the
specification-following public decoder (`tests/fap_divergences.json`), each
with its reasons.

The 23 sequence occurrences run through a test application receiver using public
models. Ownership, deduplication, acknowledgment construction, calibration,
bulletin replacement, status fallback and station-specific weather association
are verified. The codec itself remains stateless.

## Composition and precision

Serialization builds bytes from semantic fields, never `original_wire`, lexical
NMEA fields, or extension `raw` evidence. Explicit raw models are the exception:
`information`/`data` are their authoritative semantic content.

- Uncompressed coordinates round to hundredths of minutes; ambiguity transmits
  the requested cell. Compressed coordinates round to their base91 grid. DAO
  precision is removed from the reported coordinate before encoding the base
  coordinate, preventing a second application of the offset.
- Compressed motion, range and altitude use their specified logarithmic codes.
  Field overflow is rejected. No saturation or text truncation is performed.
- Mic-E requires a destination consistent with latitude, ambiguity, message and
  longitude flags. A mismatch raises `FieldError`; packet headers are not silently
  changed. Payload-only Mic-E still requires header context. Longitude degrees
  use APRS101's table, so 100–109° are sent as `l`–`u`, never as control bytes.
- Mic-E status text follows the APRS 1.2 type codes
  (aprs.org/aprs12/mic-e-types.txt). `device_code` holds the type byte that
  begins the text plus any declared suffix that ends it, such as `` `_% ``
  (Yaesu FTM-400DR), `'|3` (Byonics TinyTrack3) or `]=` (Kenwood TM-D710).
  A leading `` ` `` or `'` is APRS101 hex telemetry only in its complete form
  without a declared suffix; otherwise it is a type byte, and no type byte or
  suffix makes a packet `Malformed`. Sending refuses an undeclared type code, a
  type code combined with hex or binary telemetry, and a comment that would be
  read back as a different type code.
- NMEA uses semantic numeric fields and recomputes a supplied checksum. Checksum
  characters can change when equivalent numeric spellings change. A sentence
  received with a bad checksum (`checksum_valid=False`) is a conformance finding:
  it is reported when parsed and refused when sending, so corrupt data is never
  re-signed implicitly. Repair it explicitly by clearing `checksum_valid` (a fresh
  checksum is computed) or by omitting the checksum.
- Weather encoders convert supported units to wire units, then round to field
  precision. Uncompressed located wind retains the corpus's explicit
  `disputed_knots_or_mph` unit on decode; composition of an explicitly metric or
  mph reading follows the FAP mph interpretation. No interpretation is assigned
  to a received disputed reading by the core decoder.
- Structured weather data is exempt from the 43-byte position-comment budget.
  Uncompressed wind (`ddd/sss`) still counts as the 7-byte data extension, leaving
  36 comment bytes; with wind in compressed csT all weather data is exempt.
  Envelope limits (information and line bytes) still count every byte.
- Weather software/unit codes end a report (APRS101 pp. 63–66 define no comment
  after them). They are decoded only when they end the report, so sending refuses
  codes followed by a comment, and a comment alone that would read back as codes
  (3–5 characters such as `home`).
- Message text is a query response only when it matches a response grammar
  completely; anything else remains an ordinary `Message`.
- Explicit altitude datum and DF interpretation annotations with no wire form
  remain unsendable rather than being silently discarded. Raw vendor weather
  annotations do not replace authoritative bytes.

Constructors enforce model validity. `check_packet` reports conformance findings;
`serialize_packet` rejects them and additionally checks representability. Received
warnings alone do not prevent encoding: Latin-1 input can become valid UTF-8.

## Verification

All 1,564 decode cases pass without skips or expected failures. Public JSON
projections and source assertions outside the projections are both checked,
including partial values recovered before a rejection.
All original packet bytes, semantic expectations, options and provenance have a
frozen integrity hash tied to PR #4's head commit.

Every vector also has an encoding test. With an explicit permissive envelope
policy (`EnvelopePolicy(".*", ".*", ".*")`), 1,305 occurrences encode and stabilize
through semantic decode/encode round trips with all raw evidence removed. The
other 259 have explicit refusal records: 176 malformed public packets and 83
violations of the existing transmit-conformance rules. Those refusal tests assert
the reason; they are not broad exception catches or skipped tests. Three NMEA
sentences with bad checksums are first refused, then encode after an explicit
repair; they are counted among the 1,305.

Of those 1,305, 15 have addresses rejected by the new default `APRS_IS` policy,
including two with SSID `-0`; the tests independently require those
default-policy refusals and validate the other 1,290 under the default policy. The permissive policy changes no decoded
fields, packet bytes or payload conformance checks. Dedicated policy tests cover
custom patterns, optional and zero limits, boundary sizes including CRLF,
repeated markers, and consistent outer-envelope handling of third-party packets.

PHG/PHGR vectors exercise the public API directly. The PHGR rate character and required slash, ordinary PHG separators,
and PHG comment whitespace are handled by the shared public decoder/encoder.
