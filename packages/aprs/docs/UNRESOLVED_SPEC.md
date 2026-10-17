# Unresolved specification questions

This module validates the modeled baseline without claiming complete APRS or
NMEA conformance. Validation has two tiers: constructors reject values that cannot
exist on the wire or contradict another field, and conformance rules report APRS
limits that a transmitter could still break. Received packets keep conformance
findings as diagnostics; `serialize_packet` refuses to send them. The questions below are deliberately not resolved by guessing
values, inventing sensor observations, or treating interoperability examples as
normative specifications. Wire codecs remain unavailable for these families
unless [API_COVERAGE.md](API_COVERAGE.md) states otherwise.

APRS101 page numbers below are printed page numbers. PDF viewer pages are ten
higher. The [APRS 1.1 addendum](https://www.aprs.org/aprs11.html) evolves over time;
later proposals linked from it are not automatically settled baseline rules.

## Text encoding: ASCII and UTF-8

**Authority:** [APRS101](https://www.aprs.org/doc/APRS101.PDF) and the 1.1
addendum specify printable 7-bit ASCII for all text. The 1.1 page states that
"all new updates and additions to APRS since 2004 are found on the APRS 1.2
proposed draft addendum", whose
[UTF-8 International Alphabets note](https://www.aprs.org/aprs12/utf-8.txt)
(WB4APR, 17 December 2009) allows UTF-8 in message, bulletin and announcement
text, in status text after the optional timestamp, in position/object free text
after the fixed extension fields, and in Mic-E status text. It still recommends
ASCII for global communication. APRS-IS services such as aprs.fi decode UTF-8 in
these fields.

**Current behavior:** free-text fields decode as UTF-8; invalid UTF-8 falls back
to Latin-1, one character per byte, with a nonconforming diagnostic, and the exact
bytes remain in `original_wire`. Free text is sent as UTF-8 and length limits
count encoded bytes. Control characters are nonconforming. Protocol tokens
(callsigns, addressees, message IDs, object and item names, query names, NTS
fields, telemetry labels, NMEA fields) remain printable ASCII.

**What resolves it:** a ratified APRS revision that settles character sets, or an
explicit decision to reject non-ASCII text when transmitting on RF.

## NMEA versions, missing fix fields and receiver profiles

**Authority:** [APRS101 chapter 6, p25](https://www.aprs.org/doc/APRS101.PDF#page=35)
references NMEA 0183 version 2.0 but does not reproduce its sentence tables. The
[NMEA standard](https://www.nmea.org/nmea-0183.html) is licensed; its complete 2.0
tables were unavailable for this implementation. The 1.1 addendum tentatively
corrects the printed WPT name to WPL.

**Current behavior:** GGA/GLL/RMC coordinates accept explicit `None` for invalid
fixes, but their keys remain required. Time, and the RMC date, remain required
even for a void fix. No zero position, clock, date, talker ID or usable-fix flag
is invented. GGA quality remains 0..8; newer mode fields are not represented.
This is a limited model contract, not proof that absent times are prohibited by
every NMEA version. No NMEA wire codec exists. Unsupported sentences stay opaque.

**What resolves it:** consult the versioned normative sentence tables and select
the intended core and receiver extensions before changing omission semantics,
sentence lengths, modes, quality codes, waypoint limits or checksum requirements.
[Trimble's GGA table](https://receiverhelp.trimble.com/alloy-gnss/en-us/nmea0183-messages-gga.html),
[GLL table](https://receiverhelp.trimble.com/alloy-gnss/en-us/nmea0183-messages-gll.html),
[Garmin GPS18x §4.2](https://static.garmin.com/pumac/GPS_18x_Tech_Specs.pdf), and
[NovAtel GGA](https://docs.novatel.com/OEM7/Content/Logs/GPGGA.htm) document receiver
profiles; for example, NovAtel includes quality 9. They do not establish universal
NMEA 2.0 rules.

## NMEA reported precision and evidence

**Authority:** [Trimble VTG](https://receiverhelp.trimble.com/alloy-gnss/en-us/nmea0183-messages-vtg.html)
reports one speed in knots and km/h. [NovAtel RMC](https://docs.novatel.com/OEM7/Content/Logs/GPRMC.htm)
describes date and variation, but a two-digit year does not identify a century.

**Current behavior:** `VTG.speed_knots` and `speed_kmh_reported` remain separately
reported observations; agreement is not enforced because numeric fields do not
retain the precision needed to compare rounded wire readings. They are not two
independent authoring sources for a future encoder. Calendar validation rejects
impossible dates, allowing February 29 in YY=00 without assigning a century.
`checksum_valid` requires a supplied checksum, but is evidence about original
input, not certification of an edited sentence. No checksum is invented or
recomputed by the model.

**What resolves it:** define which speed is authoritative for composition and
retain each received field's precision, or define an explicitly selected rounding
policy. Supply a century context only if an application needs an absolute date.

## Base91 comment telemetry's channel minimum

**Authority:** the author's [specification §3.7](https://github.com/hessu/aprs-specs/blob/master/aprs-base91-comment-telemetry.txt)
requires at least one channel; the same author's [README](https://github.com/hessu/aprs-specs#readme)
allows sequence-only telemetry. The extension describes itself as experimental.

**Current behavior:** conformance for `base91_comment` follows §3.7: a sequence
in 0..8280 and at least one analog value are required. Digital data follows all five analog fields.
Sequence-only data is unsupported by this model contract, not declared universally
malformed on receipt; there is no wire decoder for it. `compatibility` is an
explicitly unverified representation, not a named normative encoding.

**What resolves it:** choose a versioned extension profile or obtain an author
clarification reconciling the documents. Do not silently expand the baseline by
filling missing channels with zero.

## Weather proposals, unavailable readings and water gauges

**Authority:** [APRS101 pp63–66](https://www.aprs.org/doc/APRS101.PDF#page=73),
[1.1 weather clarification](https://www.aprs.org/aprs11/spec-wx.txt), and
[1.2 weather proposals](https://www.aprs.org/aprs12/weather-new.txt).

**Current behavior:** conformance requires direction, speed, gust and
temperature slots in a complete report. Positionless reports require MDHM; located
reports use the enclosing position time. Explicit unavailable readings satisfy
slot presence. There is no extra requirement for a numeric observation. A
`Weather` model may be incomplete; only sending an incomplete report is refused.

The later minimum flood example omits gust; proposed water units and examples
disagree across the documents. `WaterHeight` consequently remains a signed
measurement with explicit feet/meters and optional external datum metadata; no
water-wire encoding is inferred. `disputed_knots_or_mph` explicitly records
unresolved velocity units and must not be converted without a selected profile.

**What resolves it:** a chosen, cited water/flood profile and clarification of
units, unavailable markers, field widths and mandatory slots. The blanket baseline
must not be replaced by an inconsistent proposal. An application may reject
reports with no numeric observations, but that is separate from protocol validity.

## Telemetry equations and empty definition slots

**Authority:** [APRS101 pp69–70](https://www.aprs.org/doc/APRS101.PDF#page=79)
allows the coefficient list to stop at any field; its relationship to complete
triples, interior empty fields and default coefficients is not fully explicit.

**Current behavior:** `Calibration` requires all three coefficients.
`TelemetryEquations` can omit trailing channels or preserve a `None` channel, but cannot claim an
incomplete trailing triple is an evaluable polynomial. PARM/UNIT channel lengths
and delimiters are checked; `None` and empty labels are retained without invented
labels. No parser or encoder silently inserts calibration coefficients. The
BITS project segment is limited to 23 characters; exact future comma framing
must be checked against the diagram when implementing its codec.

**What resolves it:** agree whether to model transmitted coefficient lists or
complete evaluable calibrations separately; verify empty/interior-field semantics
and delimiter accounting before implementing a wire codec.

## Direction-finding mappings and PHG extensions

**Authority:** [APRS101 pp28–30](https://www.aprs.org/doc/APRS101.PDF#page=38),
[original protocol notes](https://www.aprs.org/APRS-docs/PROTOCOL.TXT),
[DF notes](https://www.aprs.org/APRS-docs/DF.TXT), and
[PHG display guidance](https://www.aprs.org/symbols/PHGmobile.txt).

**Current behavior:** code ranges and positive accuracy bounds are checked. The
manual flag, bearing range and PHG radii are computed properties, so they cannot
disagree with the codes. A single Q-to-accuracy
or usability mapping is not imposed: the original notes omit Q=6 and differ from
APRS101 at low Q values. `Bearing.usable` and accuracy remain reported
interpretations, not certified derivations. PHG rate-per-hour has no verified
extension authority here. Display half-radius is a documented display choice,
not an independently transmitted observation.

**What resolves it:** identify a versioned DF mapping and a primary specification
for PHG rate. Do not silently combine conflicting tables or treat UI guidance as
another on-air field.

## NWS, historical beacons and vendor weather

**Authority:** [APRS101 pp25,62,74,89,103](https://www.aprs.org/doc/APRS101.PDF),
the [1.1 WXSVR links](https://www.aprs.org/aprs11.html), and
[Peet Bros serial specification](https://www.peetbros.com/shop/custom.aspx?recid=29).

**Current behavior:** NWS transport addressee/ID/text constraints are checked,
but a full WXSVR alert grammar is not claimed. Maidenhead bracket-beacon symbol
and comment suffixes lack verified historical placement. Agrelo's three-digit
bearing/one-digit quality layout is known, but exact reference and quality
semantics remain unverified. RawWeather checks its declared prefix only; hardware
and mode aliases are documented, and decoded observations are external evidence.
Detailed Peet layouts exist; absence of a codec is an implementation boundary,
not absence of an authoritative vendor grammar.

**What resolves it:** retrieve the specific WXSVR/historical/Agrelo grammar, and
select Peet device/mode/rain-gauge profiles before interpretation. Raw bytes remain
the content of explicit raw models. Editing annotations does not edit those bytes.

## Names, lifecycles, reply-ack and authoring policy

**Authority:** [APRS101 pp57–61](https://www.aprs.org/doc/APRS101.PDF#page=67),
[object clarification](https://www.aprs.org/aprs11/Objects.txt),
[names and spaces](https://www.aprs.org/aprs11/aprs-names-and-spaces.txt), and
[reply-ack format](https://www.aprs.org/aprs11/replyacks.txt).

**Current behavior:** standard killed Objects still require location and timestamp;
Items still require location. Detailed object grammar takes precedence over the
contradictory overview's optional-timestamp wording. Semantic names exclude outer
padding but do not impose every waypoint-friendly punctuation recommendation.
Reply-ack is one `reply_ack` suffix on the message or acknowledgment ID, so the
two cannot disagree; conformance checks that the combined field fits five
characters, and exact two-character halves are not forced. Obsolete object and
bulletin forms are not modeled as flags; they remain Opaque until a historical
profile defines them.

**What resolves it:** a documented compatibility profile for truncated kills,
obsolete reports, stricter name conventions or shorter reply-ack halves. These
choices must not weaken strict modern construction silently.

## Quantization and unimplemented codecs

Physical measurements and some derived fields can have more precision or a
larger magnitude than a selected wire format can express. Current semantic
validation is not universal representability validation. Future encoders must
choose and document exact conversion, rounding, saturation-versus-rejection and
field-budget rules. They must not round implicitly in constructors, truncate text,
reuse stale raw evidence, or invent unavailable data. The original APRS101 widths
and the exact selected extension's rules remain authoritative for that encoder.

Mandatory symbol facts, ordinary status/message text, and NMEA talker metadata
are explicit constructor inputs. Empty text is valid when supplied; missing text
in recovered data is not an empty observation. Ordinary JSON import requires the
same facts as Python construction, so incomplete repair data remains incomplete.
