# APRS codec coverage

Packet dataclasses, payload unions and the packet JSON schema are unchanged.
Envelope entry points now accept `policy=EnvelopePolicy(...)` instead of a
profile string, with public `RF` and `APRS_IS` presets. `APRS_IS` is the default.
Decoding and encoding cover the families exercised by all 1,561 occurrences in
[the edition 1 corpus](APRS_COMPLIANCE_VECTORS.md). Unknown grammars still use
`Opaque`; raw wrappers preserve authoritative information bytes.

| Family            | Decoding and encoding                                                                                                                           |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Envelope          | TNC2, configurable address patterns and size limits, RF/APRS-IS presets, explicit repeated hops, AEA normalization, bounded third-party nesting |
| Positions         | All four DTIs, ambiguity, compressed coordinates/csT, Mic-E destination-dependent latitude/message/hemisphere                                   |
| Extensions        | Motion, altitude, PHG/rate, range, DF signal/bearing, DAO, area/corridor, signpost, storm, weather, base91 and Mic-E telemetry                  |
| Objects/items     | Names, ownership information, alive/killed markers, compressed/uncompressed positions and extensions                                            |
| Weather           | MDHM positionless and located reports, unavailable readings, rain/humidity/pressure, luminosity, snow, water height, device suffixes            |
| Telemetry         | Classic samples, PARM/UNIT/EQNS/BITS, comment base91, old Mic-E hex/binary                                                                      |
| Messages          | Ordinary messages, ack/rej, reply-ack, automatic answers, bulletins/announcements/groups, NWS envelopes, NTS records                            |
| Queries/responses | General/directed queries, footprints, heard-station operands, direct lists, hourly counts, trace headers, capabilities                          |
| Status            | Text, DHM, grid/symbol and beam/ERP                                                                                                             |
| NMEA              | GGA, GLL, RMC, VTG and WPL, checksums, independent fix usability, destination/source symbol conventions                                         |
| Historical/raw    | Grid beacons, X1J embedded positions, plain beacons, Agrelo, user-defined, invalid/test, reserved and external raw formats                      |
| Vendor weather    | Ultimeter 2000 measurements plus original bytes; other vendor modes retain bytes without invented measurements                                  |

`codec_support()` and `codec_support_for()` describe these boundaries at runtime.
Raw models do not promise interpretation of arbitrary vendor or external grammars.
AX.25 framing, KISS, FCS, radio/modem operation and arbitrary NMEA sentences remain
outside this package's packet codec.

## Receiver profiles without an API change

The source vectors deliberately describe different receivers. The same TNC2
bytes can have different expectations: embedded `!` is a modern beacon versus a
legacy X1J position; FAP trims comments, converts weather units, rounds some
values, and accepts certain incomplete historical reports.

The public codec is deterministic and preserves the richer wire interpretation.
The private `_compatibility` adapter supplies the named historical views and
additional receiver facts without adding profile parameters or JSON fields to
the public API. It never reads fixtures or expected values. FAP compatibility is
an implementation of the captured receiver policy, not the core transmit policy.
The pinned reference implementation was consulted; it is not a runtime dependency.

Some facts cannot be stored as additional public fields: disputed DF quality
interpretations, network retention/routing policy, weather radiation/battery and
indoor sensor values, and historical receiver resolution/warnings. Tests verify
these separately from retained codes/bytes. Incomplete historical GLL reports
and invalid timestamps remain `Malformed` in the public model when required
facts cannot be constructed; the historical adapter exposes only available facts.
No missing time, coordinate or calibration coefficient is fabricated.

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
  changed. Payload-only Mic-E still requires header context.
- NMEA uses semantic numeric fields and recomputes a supplied checksum. Checksum
  characters can change when equivalent numeric spellings change. A deliberately
  bad input checksum is repaired and fix usability is reevaluated.
- Weather encoders convert supported units to wire units, then round to field
  precision. Uncompressed located wind retains the corpus's explicit
  `disputed_knots_or_mph` unit on decode; composition of an explicitly metric or
  mph reading follows the FAP mph interpretation. No interpretation is assigned
  to a received disputed reading by the core decoder.
- Explicit altitude datum and DF interpretation annotations with no wire form
  remain unsendable rather than being silently discarded. Raw vendor weather
  annotations do not replace authoritative bytes.

Constructors enforce model validity. `check_packet` reports conformance findings;
`serialize_packet` rejects them and additionally checks representability. Received
warnings alone do not prevent encoding: Latin-1 input can become valid UTF-8.

## Verification

All 1,561 decode cases pass without skips or expected failures. Public JSON
projections and source assertions outside the projections are both checked,
including partial values recovered before a rejection.
All original packet bytes, semantic expectations, options and provenance have a
frozen integrity hash tied to PR #4's head commit.

Every vector also has an encoding test. With an explicit permissive envelope
policy (`EnvelopePolicy(".*", ".*", ".*")`), 1,296 occurrences encode and stabilize
through semantic decode/encode round trips with all raw evidence removed. The
other 265 have explicit refusal records: 181 malformed public packets and 84
violations of the existing transmit-conformance rules. Those refusal tests assert
the reason; they are not broad exception catches or skipped tests. Three bad
NMEA checksums are repaired as part of the 1,296 successful encodings.

Of those 1,296, 13 have addresses rejected by the new default `APRS_IS` policy;
the tests independently require those default-policy refusals and validate the
other 1,283 under the default policy. The permissive policy changes no decoded
fields, packet bytes or payload conformance checks. Dedicated policy tests cover
custom patterns, optional and zero limits, boundary sizes including CRLF,
repeated markers, and consistent outer-envelope handling of third-party packets.

PHG/PHGR vectors exercise the public API directly, without compatibility
decoding. The PHGR rate character and required slash, ordinary PHG separators,
and PHG comment whitespace are handled by the shared public decoder/encoder.
