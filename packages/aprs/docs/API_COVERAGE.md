# APRS codec coverage

Packet dataclasses and JSON use semantic fields; the alpha API changes described
below replace DAO codes and NMEA string/unit-specific fields.
Packet and payload entry points accept `policy=EnvelopePolicy(...)`.
`RF()` and `APRS_IS()` are factories with explicit extension defaults; direct
construction and fully specified JSON are supported. See
[packet policies](ENVELOPE_POLICIES.md) for the baseline, catalog and interpretation
conflicts. Wire support below is subject to the selected extension set.

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

Incomplete historical GLL layouts and undecodable timestamps remain `Malformed`.
Decodable partial NMEA times/dates remain structured with diagnostics; `Malformed.recovered` keeps the intact
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

Each JSONL row stores a complete serialized `EnvelopePolicy` under `policy`
(28 RF and 1,536 APRS-IS), including explicit extensions, byte fallback and legacy-position settings.
The separate `legacy_positions` field is provenance. Corpus,
individual-packet and round-trip runners reconstruct that policy directly. Source
`profile` and `options` remain provenance, not runtime envelope-policy hints.
The generator resolves the historical hints once; contract tests verify unchanged
effective parsing, including diagnostics, for every row.

The 23 packet occurrences from the archived application sequences are tested
independently. Hand-authored expectations in `tests/sequence_packet_expectations.json`
describe only transmitted headers and payload fields, using the documented packet
bytes and cited APRS layouts. No decoder output is used to generate expectations.
The original `source_expected` values remain non-executable application-state
provenance, explicitly labeled by `source_expected_scope`. There is no test
receiver, replay of earlier steps, or accumulated-state assertion. Ownership,
deduplication, acknowledgment scheduling, calibration application, bulletin
replacement, status precedence and weather-location inheritance belong to a
consuming application, outside this stateless codec.

## Composition and precision

Serialization builds bytes from semantic fields, never `original_wire`, lexical
NMEA fields, or extension `raw` evidence. Explicit raw models are the exception:
`information`/`data` are their authoritative semantic content.

- The library chooses each wire form; composing never selects an encoding.
  `Altitude.encoding` and `Telemetry.encoding` record how a value was
  received, are ignored by equality, and are kept on send only when the
  enclosing payload and policy can carry them. Otherwise a position's altitude
  uses `/A=`, or csT when the compression source is GGA. A Mic-E altitude in
  meters uses the compact field and one in feet uses `/A=`. Position telemetry
  uses base91. Mic-E telemetry uses APRS101 hex when it fits (no sequence or
  digital bits, whole values 0–255, two or five channels, no type code), the
  binary form when `mice_hex_as_device` rules out hex, and base91 otherwise.
  A telemetry report is always classic. `check_packet` checks the chosen form.
- Uncompressed coordinates round to hundredths of minutes; ambiguity transmits
  the requested cell, selected before decimal rounding. Derived `ambiguity_extent`
  bounds and encoding share the same cell selector, with no boundary epsilon.
  Both coordinates use the same ambiguity level. Exact pole/antimeridian coordinates whose cell would
  extend beyond the axis bounds are refused; requesting `ambiguity_extent` for
  such a cell raises `FieldError` rather than clamping to a neighboring cell.
  Compressed coordinates round to their base91 grid. DAO
  now stores `datum` and `encoding`, without latitude/longitude codes. The refined
  coordinate is rounded once, then split into hundredth-minute and DAO parts,
  including carry across minute/degree boundaries. Parsing applies supported
  offsets once; later edits recompute codes. Added precision with ambiguity or
  compressed coordinates is refused on send. On receive these unsupported
  combinations retain baseline coordinates and DAO evidence with diagnostics.
- Altitude accepts `Measurement` in feet or meters for `/A=`, compressed, Mic-E
  and GGA. Conversion precedes quantization and range checks. GGA uses
  `altitude_msl` and `geoid_separation`, replacing the `_m` scalar fields. Decoding
  retains each format's native unit; no vertical datum transformation is implied.
- `compression=Compression()` is enough to send a position compressed. The
  csT bytes carry motion, range or weather wind when present and are otherwise
  marked unused (`c` = space); missing type fields default to a current fix,
  the "other" NMEA source and software origin. A GGA source puts the altitude
  in csT; otherwise an altitude uses `/A=`. The type fields are kept when
  received and ignored by equality.
- Compressed motion, range and altitude use their specified logarithmic codes.
- Coded fields take names, and the library writes their codes: area
  `shape`/`color`/`intensity` (APRS101 pp60–61), compression `origin`
  (APRS101 p39, defaulting to `"software"`), storm `kind` (`"hurricane"`,
  `"tropical_storm"`, `"tropical_depression"`), NMEA `fix_status`
  (`"active"`/`"void"`), GGA `fix_quality` (`"invalid"` … `"simulation"`, the
  NMEA 0183 table), GGA `dgps_age_seconds` and `dgps_station` (0–1023, written
  as four digits) as numbers, and a signed `magnetic_variation_deg` (east
  positive). An NTS header takes `precedence` (`"routine"`, `"welfare"`,
  `"priority"`, `"emergency"`; written R, W, P, EMERGENCY) and `test=True` for a
  TEST message. NTS dates and times stay text, as written on the radiogram
  form, because APRS101 p75 defers them to the NTS handbook, which fixes no
  format. A void or invalid NMEA fix is not a diagnostic: `position_usable` is
  false. `Altitude.encoding` is keyword-only, like `Telemetry.encoding`. DAO
  `precision` is `"high"` (one more decimal digit of minutes, about 1.85 m) or
  `"highest"` (base-91, about 0.2 m). A DF `Bearing` takes `hit_ratio` or
  `manual`, `range_miles` and `accuracy_deg`, using APRS101's quality table
  (10° is sent as Q=5, "under 16°"). Agrelo quality remains a 0–9 vendor scale
  because its meaning is unverified (see [UNRESOLVED_SPEC.md](UNRESOLVED_SPEC.md)). `Timestamp.from_datetime`
  converts an aware `datetime` to any of the APRS time formats.
- Values between codes round to the nearest code, like coordinates: PHG and
  DF-signal power (n² watts), height (10 × 2ⁿ feet, on the logarithmic scale),
  gain (whole dB) and directivity (45° steps, so 10° is sent as north), and
  status beam heading (10°) and ERP (10 × n² watts). A value outside the code
  range after rounding is refused. No saturation or text truncation is
  performed.
- Course 0 means unknown in both uncompressed and Mic-E positions (APRS101
  pp. 27, 49), so `course_deg=None` is sent as 0 and a course that rounds to 0°
  is sent as north (360). Mic-E always carries a speed: `Motion(None, 0)` is a
  stationary report with unknown course. Likewise, a measured wind from 0° is
  sent as `360/sss`, because `000/000` reads back as an unavailable reading.
- Under a weather symbol (`_` or `W`), receivers read a course/speed pair,
  uncompressed or in compressed csT, as wind. `check_packet` therefore reports
  `Motion` on such a position at `$.extensions.motion`; send wind in
  `extensions.weather` instead. More generally, extensions that would read back
  as different kinds are refused.
  Numeric overlays use table IDs `a`–`j`; sending compressed positions with
  `0`–`9` table IDs is refused as nonconforming.
- Mic-E generates an omitted destination from latitude, ambiguity, message and
  longitude flags. `check_packet` reports mismatches at `$.header.destination`,
  and sending raises `ConformanceError`; packet headers are not silently changed.
  Explicit destinations are checked for consistency; omitted destinations remain
  automatic templates and are recomputed without mutation. Payload-only Mic-E
  decoding requires its received header; encoding derives the needed bits. Longitude degrees
  use APRS101's table, so 100–109° are sent as `l`–`u`, never as control bytes.
- Mic-E fixed-body motion does not occupy the comment data-extension slot. PHG
  can accompany it; PHGR still requires `phg_rate`. A DF bearing emits its
  required course/speed comment prefix and is retained on decode. Status checks
  also verify that extension presence survives serialization.
- Mic-E status interpretation is policy-selected. With `mice_device_ids` (on
  by default), an apostrophe/backtick not followed by complete APRS101 hex
  telemetry is a device type byte, and declared version suffixes become part of
  `device_code` for every type byte. Complete hex stays telemetry unless
  `mice_hex_as_device` (off by default) is enabled. With both off, those
  selectors introduce APRS101 hexadecimal telemetry. Incomplete hex (such as a
  Yaesu or TinyTrack type code read strictly) keeps the decoded position, leaves
  the status text as the comment and is reported nonconforming at
  `$.payload.comment`, so it is not re-sent; suffix text stays in the comment; original `>` and `]` device
  markers remain supported. There is no
  general APRS revision flag proving the sender's intent. Legacy grid/status
  text remains literal comment, separate from the encoded coordinates.
  Sending rejects models incompatible with the selected interpretation and
  comments that would read back as different fields. Extended high-speed
  reinterpretation is not implemented.
- NMEA uses `UTCTime(hour, minute, second)` and
  `NMEADate(day, month, year_mod_100)` in `RMC.date`, replacing formatted strings.
  Null means missing; unknown components stay null. A four-digit received clock
  or date retains its known components with a diagnostic, but sending requires
  seconds and a complete DDMMYY date when present. Void fixes may omit these
  observations; active fixes require time, and RMC also requires a date. No
  century, date or timezone is inferred. Year 00 permits February 29 because
  its unresolved century might be a leap century; leap seconds are accepted only
  at 23:59, without inventing a leap-second calendar. Fractional seconds use a
  numeric value; lexical trailing zeros are not preserved.
- NMEA checksums are a plain choice: `NMEAMetadata(checksum=True)` (the
  default) has the library compute one, and `checksum=False` omits it. A
  comment follows the checksum, so it requires `checksum=True`. The received
  checksum characters are hidden evidence (`checksum_supplied`), and
  `checksum_valid` records whether they matched; neither affects equality.
  Coordinates are written as `ddmm.mm` with at least two decimals. A sentence
  received with a bad checksum (`checksum_valid=False`) is a conformance finding:
  it is reported when parsed and refused when sending, so corrupt data is never
  re-signed implicitly. Repair it explicitly by clearing `checksum_valid` (a fresh
  checksum is computed) or by setting `checksum=False`.
  For an NMEA packet with a symbol, leave `header.destination` out: the library
  generates the `GPSxyz` destination from the published table
  (aprs.org/symbols/symbolsX.txt), including overlays. Received `GPSxyz`,
  `SPCxyz` and `SYMxyz` destinations decode through the same table. An
  explicit destination must carry the symbol; `check_packet` reports a
  conflict at `$.payload.symbol`. Payload-only encoding with an explicit symbol
  raises `ContextRequiredError`; use `serialize_packet` to supply the header.
- Weather encoders convert supported units to wire units, then round to field
  precision. Uncompressed located wind retains the corpus's explicit
  `disputed_knots_or_mph` unit on decode; composition of an explicitly metric or
  mph reading follows the FAP mph interpretation. No interpretation is assigned
  to a received disputed reading by the core decoder.
  Standalone `serialize_payload` applies the same positionless report requirements
  as packet serialization, including mandatory slots and the prohibition on snow.
- Structured weather data is exempt from the 43-byte position-comment budget.
  Uncompressed wind (`ddd/sss`) still counts as the 7-byte data extension, leaving
  36 comment bytes; with wind in compressed csT all weather data is exempt.
  Envelope limits (information and line bytes) still count every byte.
- Weather software/unit codes end a report (APRS101 pp. 63–66 define no comment
  after them). They are decoded only when they end the report, so sending refuses
  codes followed by a comment, and a comment alone that would read back as codes
  (3–5 characters such as `home`). Codes or a comment that begin like a broken
  field (a field letter followed by a number of the wrong width, such as
  software code `b` with unit `1234`) are refused too. On receive, only a
  number after a field letter is reported as a malformed field; other text is
  the comment.
- Message text is a query response only when it matches a response grammar
  completely; anything else remains an ordinary `Message`.
- Explicit altitude references, water-height datums and DF interpretation
  annotations have no wire field. They are reported as conformance findings at
  their own paths and remain unsendable rather than being silently discarded. Raw vendor weather
  annotations do not replace authoritative bytes.

Constructors enforce model validity. `check_packet` reports every finding
`serialize_packet` would refuse with, including values the encoder cannot
represent (a field too wide, a speed beyond the Mic-E range, an ERP with no
code), each at its own path. Only a missing codec or missing header context is
reported by sending alone. Received
warnings alone do not prevent encoding: Latin-1 input can become valid UTF-8.

## Verification

All 1,564 decode cases pass without skips or expected failures. Public JSON
projections and documented core packet/field assertions outside the projections are checked,
including partial values recovered before a rejection.
All original packet bytes, semantic expectations, options and provenance have a
frozen integrity hash tied to PR #4's head commit.

Every vector also has an encoding test. With an explicit permissive envelope
policy (the row policy with its envelope patterns and limits relaxed), 1,304 occurrences encode and stabilize
through semantic decode/encode round trips with all raw evidence removed. The
other 260 have explicit refusal records: 172 malformed public packets and 88
violations of the existing transmit-conformance rules. Those refusal tests assert
the reason; they are not broad exception catches or skipped tests. Three NMEA
sentences with bad checksums are first refused, then encode after an explicit
repair; they are counted among the 1,304.

Of those 1,304, 15 have addresses rejected by the `APRS_IS()` envelope constraints,
including two with SSID `-0`; the tests independently require those
envelope refusals and validate the other 1,289 with the row’s interpretation settings. The permissive policy changes no decoded
fields, packet bytes or payload conformance checks. Dedicated policy tests cover
custom patterns, optional and zero limits, boundary sizes including CRLF,
repeated markers, and consistent outer-envelope handling of third-party packets.

The round-trip runner also checks each row's stored policy separately: 25 of the
1,304 representable packets have envelope refusals under that policy, and 1,280
validate. The additional 10 refusals exercise RF address/path constraints.

PHG/PHGR vectors exercise the public API directly. The PHGR rate character and required slash, ordinary PHG separators,
and PHG comment whitespace are handled by the shared public decoder/encoder.

## Specification boundaries and migration

The [DAO proposal](https://www.aprs.org/datum.txt) defines decimal and base-91
refinements of hundredth-minute coordinates, and datum-only spaces. Its base-91
explanation uses an approximate 1.10 scale and contains a terminal-character
inconsistency. This codec retains the established corpus convention: integer
codes 0..90, ASCII 33..123, with an increment of 1/(91 × 6000) degrees. Rounding
uses Python's nearest/ties-to-even rule, as in the other coordinate encoders.
Local numeric datum identifiers lack a specified precision mode here and remain
uninterpreted comment text; no datum transformation or added precision on
compressed positions is claimed. FAP-035 now records the compressed-position
DAO limitation explicitly; its source assertion and packet remain unchanged.

The NMEA models follow the component layouts illustrated by the primary
[Trimble RMC documentation](https://receiverhelp.trimble.com/alloy-gnss/en-us/NMEA-0183messages_RMC.html)
and [GGA documentation](https://receiverhelp.trimble.com/alloy-gnss/en-us/NMEA-0183messages_GGA.html).
Partial four-digit clocks/dates are a permissive receive representation, not a
new valid wire layout. Arbitrary vendor partial-field conventions remain outside
this grammar. The four formerly malformed partial/missing NMEA corpus cases
(FAP-384, 386, 393 and 395) now retain structured data with send-conformance
findings. Other raw packet and source/provenance assertions are unchanged.

Alpha callers must replace `DAO.datum_byte` and precision codes with an uppercase
`datum` identifier plus `encoding`; replace NMEA time/date strings with the new
component objects; and wrap GGA heights in `Measurement`. JSON uses the same
fields, with standalone tags `utc_time` and `nmea_date`. Original DAO bytes and
NMEA `fields_raw` remain optional evidence, never a serialization source.

## Review corrections: geometry and bracketed grids

`Area.latitude_offset_deg` and `longitude_offset_deg` replace caller-supplied
wire codes. Offsets range from 0 through 6.534 degrees, and encode as
`round(sqrt(offset_deg * 1500))`; decoding uses `code**2 / 1500`, following the
[APRS 1.1 correction](https://www.aprs.org/aprs11/areaobjects.txt).
`Bearing.range_miles` replaces `range_code`, accepts 1 through 512 miles, and
encodes as `round(log2(range_miles))`. Its read-only `range_code` and the area
code properties expose the resulting codes without duplicating mutable facts.
Rounding ties go to even. Size/range edits recompute codes; finite values outside
the wire domain are rejected. Shape, color, hits and quality remain classification
codes; no disputed DF quality interpretation is added. Python and JSON use the
same semantic fields. This is an alpha API migration: the positional arguments
formerly carrying codes now carry degrees or miles.

The bracketed Maidenhead grammar is `[Grid Locator]Comment` (APRS101 p33).
Both brackets are required, and a supplied symbol is refused because this form
has no symbol slot. Symbol-bearing grid status reports remain separate. OTH-012
and OTH-013 now independently assert an empty comment and absent symbol, so the
closing bracket cannot again be mistaken for comment data. All source packet
bytes and provenance remain unchanged.

Mic-E PHG follows the [APRS 1.2 proposal](https://www.aprs.org/aprs12.html);
ordinary PHG has no extra interpretation flag, while its optional rate keeps the
existing `phg_rate` gate. Body motion and comment extension slots are validated
separately. No high-speed interpretation or other proposal is enabled here.
