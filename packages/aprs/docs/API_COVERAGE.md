# APRS codec coverage

Packet dataclasses and JSON use semantic fields: plain values in stated units
or named choices, never wire codes.
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

Each case vector stores the public decoder's exact output (`decoded`) beside
the captured FAP output (`fap`), which is provenance and never asserted; the
`comment` of each row explains where and why the two differ.

The public codec is deterministic and preserves the richer wire interpretation.
There is no receiver-emulation layer: every case vector compares public
`parse_packet` output with its stored expectation exactly. FAP's own extra fields
(display resolution, raw timestamps, warnings, indoor sensors) describe that
library's output rather than this schema, so they remain source provenance
without assertions. The pinned reference implementation was consulted; it is
not a runtime dependency.

Incomplete historical GLL layouts remain `Malformed`. A position whose timestamp
cannot be decoded (often a time of day sent with `z`) keeps its other fields:
the timestamp is left out, with a nonconforming diagnostic quoting it, so sending
the decoded fields drops it. Objects require a timestamp and remain `Malformed`.
Out-of-spec values that the model can hold (non-ASCII capability values,
telemetry bits that are not eight binary digits, a non-base-91 Mic-E altitude
kept as comment text) decode with nonconforming diagnostics and are refused when
sent.
Decodable partial NMEA times/dates remain structured with diagnostics; `Malformed.recovered` keeps the intact
fields of positions, objects and status reports. No missing time, coordinate or
calibration coefficient is fabricated.

Historical and FAP rows parse with `legacy_positions=True`. Fifty-five FAP rows
record in their `comment` where FAP's interpretation differs from the
specification-following public decoder, with the reason.

Each case vector stores the complete serialized `EnvelopePolicy` under `policy`,
including explicit extensions, byte fallback and the legacy-position setting;
the runner uses nothing else to choose an interpretation.

The 23 packet occurrences from the archived application sequences (SEQ) are
tested independently, one packet per row. Their original accumulated-state
assertions are kept in each row's `comment` as provenance only. There is no test
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
  stores `datum` and `precision`, without latitude/longitude codes. The refined
  coordinate is rounded once, then split into hundredth-minute and DAO parts,
  including carry across minute/degree boundaries. Parsing applies supported
  offsets once; later edits recompute codes. Added precision with ambiguity or
  compressed coordinates is refused on send. On receive these unsupported
  combinations retain baseline coordinates and DAO evidence with diagnostics.
- Altitude accepts `Measurement` in feet or meters for `/A=`, compressed, Mic-E
  and GGA. Conversion precedes quantization and range checks. GGA uses
  `altitude_msl` and `geoid_separation` measurements. Decoding
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
- Under the weather symbol `_` (APRS101 pp. 62-65), receivers read a course/speed
  pair, uncompressed or in compressed csT, as wind. `/W` and `\W` are accepted as
  alternate weather symbols ([spec-wx](https://www.aprs.org/aprs11/spec-wx.txt))
  only when weather fields follow, since moving stations also use them; a bare
  course/speed pair under `W` is motion. `check_packet` therefore reports
  `Motion` on a position read as weather at `$.extensions.motion`; send wind in
  `extensions.weather` instead. More generally, extensions that would read back
  as different kinds are refused.
- Numeric overlays use table IDs `a`–`j`; sending compressed positions with
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
  the status text (including any suffix) as the comment, and is reported
  nonconforming at `$.payload.comment`, so it is not re-sent. Original `>` and
  `]` device markers remain supported. There is no
  general APRS revision flag proving the sender's intent. Legacy grid/status
  text remains literal comment, separate from the encoded coordinates.
  Sending rejects models incompatible with the selected interpretation and
  comments that would read back as different fields. Extended high-speed
  reinterpretation is not implemented.
- NMEA uses `UTCTime(hour, minute, second)` and
  `NMEADate(day, month, year_mod_100)` in `RMC.date`.
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
- Explicit altitude references and water-height datums have no wire field. They are reported as conformance findings at
  their own paths and remain unsendable rather than being silently discarded. Raw vendor weather
  annotations do not replace authoritative bytes.

Constructors enforce model validity. `check_packet` reports every finding
`serialize_packet` would refuse with, including values the encoder cannot
represent (a field too wide, a speed beyond the Mic-E range, an ERP with no
code), each at its own path. Only a missing codec or missing header context is
reported by sending alone. Received
warnings alone do not prevent encoding: Latin-1 input can become valid UTF-8.

## Verification

Packet behaviour is tested by 5,269 case vectors in `tests/cases` (see its
README), with no skips or expected failures. 3,899 rows start from received
bytes, 1,947 of them a curated sample of live APRS-IS traffic: their exact
decoded JSON is asserted, including diagnostics and the partial values a
`Malformed` result recovers (220 rows). 1,370 rows start from a composed model
and assert what is sent or exactly why it is refused. Every row with received
bytes also records go-aprs-fap's output for comparison.

For every row the runner also checks that every sending path agrees
(`serialize_packet`, `validate_packet`, `serialize_tnc2_line`, `check_packet`,
and `serialize_payload` where no header context is needed); that whatever is sent
parses back cleanly and re-encodes to the same bytes; and that the value with
all received evidence removed is refused the same way or reads back with the
same meaning. Received packets the library will not resend as they are (386) or
cannot represent (the 220 `Malformed`) record the exact refusal. The 25 rows
with a `-P` suffix repeat a packet whose stored policy refuses its addresses
under a permissive envelope policy, so its payload still round-trips; the three
`-R` rows send NMEA reports with known-bad checksums after an explicit repair.

The suite passes unchanged on CPython 3.11 to 3.15 and PyPy, with exact JSON
comparison (so `-0.0` differs from `0.0`, and `1` from `1.0`).

PHG/PHGR vectors exercise the public API directly. The PHGR rate character and required slash, ordinary PHG separators,
and PHG comment whitespace are handled by the shared public decoder/encoder.

## Specification boundaries

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

DAO uses an uppercase `datum` identifier and a named `precision`; NMEA times and
dates are component objects; GGA heights are `Measurement`s. JSON uses the same
fields, with standalone tags `utc_time` and `nmea_date`. Original DAO bytes and
NMEA `fields_raw` remain optional evidence, never a serialization source.

## Geometry and bracketed grids

`Area.latitude_offset_deg` and `longitude_offset_deg` are in degrees. Offsets range from 0 through 6.534 degrees, and encode as
`round(sqrt(offset_deg * 1500))`; decoding uses `code**2 / 1500`, following the
[APRS 1.1 correction](https://www.aprs.org/aprs11/areaobjects.txt).
`Bearing.range_miles` accepts 1 through 512 miles and encodes as
`round(log2(range_miles))`. Read-only properties (`Bearing.range_code`,
`hits_code`, `quality_code`, `Area.shape_code`, `color_code` and the offset
codes) expose the resulting codes without duplicating mutable facts. Rounding
ties go to even. Edits recompute codes; finite values outside the wire domain
are rejected. Area shape, color and intensity, and DF hit ratio and accuracy,
are named or plain values (see Composition and precision). Python and JSON use
the same semantic fields.

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
