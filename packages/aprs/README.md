# hamkit.aprs

Pure Python, MIT-licensed APRS packet models, parsing and composition, with no
runtime dependencies. Python 3.10+. This is an **alpha API**: every family in the
[coverage matrix](docs/API_COVERAGE.md) has a model, but many wire codecs remain
unimplemented. Constructing a model is different from serializing it.

This cookbook constructs every member of `Payload` and decodes representative
input for each family. Run the Python blocks **in order**, after installing with
`python -m pip install -e packages/aprs`. Output blocks are captured from the
current implementation and checked by the documentation tests.

- [JSON conversion](#json-conversion)
- [Setup and printable packets](#setup-and-printable-packets)
- [Positions and encodings](#positions-and-encodings)
- [Position extensions](#position-extensions)
- [Objects, items, areas and signposts](#objects-items-areas-and-signposts)
- [Weather and storms](#weather-and-storms)
- [Telemetry and definitions](#telemetry-and-definitions)
- [Messages, acknowledgments and bulletins](#messages-acknowledgments-and-bulletins)
- [NTS radiograms](#nts-radiograms)
- [Queries, responses and capabilities](#queries-responses-and-capabilities)
- [Status, grid and beam reports](#status-grid-and-beam-reports)
- [NMEA sentences](#nmea-sentences)
- [Third-party, user-defined and raw packets](#third-party-user-defined-and-raw-packets)
- [Vendor, historical and external formats](#vendor-historical-and-external-formats)
- [Strict decoding, recovery and line framing](#strict-decoding-recovery-and-line-framing)

Names such as `POS-001` identify exact input bytes in the local
[vector document](docs/APRS_COMPLIANCE_VECTORS.md). The construction values are
illustrative; only working encoders produce wire bytes. No equivalence to a
reference packet is asserted for an unimplemented encoder. FAP-labeled inputs
are compatibility examples, not normative expectations; their attribution and
BSD license are retained in the [vector document](docs/APRS_COMPLIANCE_VECTORS.md#license).

## Setup and printable packets

`Packet` and every payload already have readable dataclass `repr`/`str` output:
`print(packet)` includes the header and payload, and `print(packet.payload)` shows
just the payload. `original_wire` is deliberately omitted from the packet repr;
inspect it explicitly for exact received bytes.

The helper below prints the **actual** encoding/decoding result and saves both
packets for further inspection. It catches only `CodecNotImplemented`, so a real
validation error is not disguised as missing support. `show` never transmits.

```python
import hamkit.aprs as a
from dataclasses import replace

header = a.Header("N0CALL", "APRS")
constructed: dict[str, a.Packet] = {}
received: dict[str, a.Packet] = {}


def show(
    name: str, payload: a.Payload, wire: bytes, *, header: a.Header = header
) -> None:
    constructed[name] = a.Packet(header, payload)
    try:
        encoded = a.serialize_packet(constructed[name])
        encoding = repr(encoded)
    except a.CodecNotImplemented:
        encoding = "CodecNotImplemented"
    received[name] = a.parse_packet(wire)
    decoded = received[name].payload
    print(f"{name}: construct {type(payload).__name__}; encode {encoding}")
    print(f"  decode {type(decoded).__name__}", end="")
    if isinstance(decoded, a.Opaque):
        print(f"; preserved={decoded.information!r}")
    elif isinstance(decoded, a.Position):
        print(
            f"; lat={decoded.latitude_deg:.6f}, lon={decoded.longitude_deg:.6f}; tail={decoded.tail!r}"
        )
    elif isinstance(decoded, a.Status):
        print(f"; text={decoded.text!r}; timestamp={decoded.timestamp!r}")
    elif isinstance(decoded, a.Message):
        print(
            f"; to={decoded.addressee!r}; text={decoded.text!r}; id={decoded.message_id!r}"
        )
    else:
        print(f"; {decoded!r}")


packet = a.parse_packet(b"N0CALL>APRS:>Ready")
print(packet)
print(packet.payload)
print(packet.original_wire)
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Status(text=b'Ready', timestamp=None, grid=None, symbol=None, beam=None), header_semantics=None)
Status(text=b'Ready', timestamp=None, grid=None, symbol=None, beam=None)
b'N0CALL>APRS:>Ready'
```

For any later example, use `print(constructed["POS-001"].payload)` or
`print(received["POS-001"].payload)` for the full repr. These are ordinary typed
objects, not dictionaries or display-only summaries.

## Positions and encodings

**Working:** uncompressed, unambiguous positions with `!`, `=`, `/`, or `@`.
**Model-only:** compressed positions, ambiguity cells and Mic-E. Decoding those
currently preserves `Opaque`; it does not return a fabricated location.

```python
latitude = 49 + 3.5 / 60
longitude = -(72 + 1.75 / 60)
position = a.Position(latitude, longitude, tail=b"Test")
location = a.Location(latitude, longitude, a.Symbol("/", ">"))
time = a.Timestamp("dhm_utc", hour=23, minute=45, day=9)
show("POS-001", position, b"N0CALL>APRS:!4903.50N/07201.75W-Test")
show(
    "POS-002",
    replace(position, messaging=True),
    b"N0CALL>APRS:=4903.50N/07201.75W-Test",
)
show(
    "POS-003",
    replace(position, timestamp=time),
    b"N0CALL>APRS:/092345z4903.50N/07201.75W-Test",
)
show(
    "POS-004",
    replace(
        position, messaging=True, timestamp=a.Timestamp("hms_utc", 23, 45, second=17)
    ),
    b"N0CALL>APRS:@234517h4903.50N/07201.75W-Test",
)
show(
    "POS-014",
    a.Position(latitude, longitude, ambiguity=a.Ambiguity(1)),
    b"N0CALL>APRS:!4903.5 N/07201.7 W-",
)
show(
    "CMP-001",
    a.Position(
        latitude,
        longitude,
        a.Symbol("/", ">"),
        encoding="compressed",
        compression=a.Compression(58, "current", "RMC", 2),
    ),
    b"N0CALL>APRS:!/5L!!<*e7>7P[",
)
show(
    "MIC-001",
    a.MicE(
        a.Location(33.427333333333, -112.129, a.Symbol("/", "j")), (False, False, False)
    ),
    b"N0CALL>332UVT:`(_f\x1e\x1eOj/",
    header=a.Header("N0CALL", "332UVT"),
)
```

Output:

```text
POS-001: construct Position; encode b'N0CALL>APRS:!4903.50N/07201.75W-Test'
  decode Position; lat=49.058333, lon=-72.029167; tail=b'Test'
POS-002: construct Position; encode b'N0CALL>APRS:=4903.50N/07201.75W-Test'
  decode Position; lat=49.058333, lon=-72.029167; tail=b'Test'
POS-003: construct Position; encode b'N0CALL>APRS:/092345z4903.50N/07201.75W-Test'
  decode Position; lat=49.058333, lon=-72.029167; tail=b'Test'
POS-004: construct Position; encode b'N0CALL>APRS:@234517h4903.50N/07201.75W-Test'
  decode Position; lat=49.058333, lon=-72.029167; tail=b'Test'
POS-014: construct Position; encode CodecNotImplemented
  decode Opaque; preserved=b'!4903.5 N/07201.7 W-'
CMP-001: construct Position; encode CodecNotImplemented
  decode Opaque; preserved=b'!/5L!!<*e7>7P['
MIC-001: construct MicE; encode CodecNotImplemented
  decode Opaque; preserved=b'`(_f\x1e\x1eOj/'
```

`Position.location` gives reusable spatial data without station-report flags.
An `Ambiguity` may also carry `CellBounds`; its center is not an exact fix.
Mic-E needs the destination as well as information bytes: use full packet parsing
or `decode_payload(info, header=...)`. For future encoding, use
`encode_packet_fields(packet)` to receive **both** derived header and information;
its Mic-E codec still raises today. Coordinates may quantize during working
encoding; compare decoded quantized values rather than arbitrary input floats.

## Position extensions

**Model-only fields, working outer position decoder.** Motion, altitude, PHG,
range, direction finding, DAO and comment telemetry have typed representations.
The current position decoder leaves their bytes in `tail`; a returned `Position`
does **not** mean these extensions were interpreted. Structured construction
raises rather than dropping them.

```python
show(
    "EXT-001",
    a.Position(
        latitude,
        longitude,
        extensions=a.Extensions(motion=a.Motion(course_deg=1, speed_knots=1)),
    ),
    b"N0CALL>APRS:!4903.50N/07201.75W>001/001",
)
show(
    "EXT-011",
    a.Position(
        latitude,
        longitude,
        extensions=a.Extensions(
            altitude=a.Altitude(a.Measurement(1234, "feet"), "feet_extension")
        ),
    ),
    b"N0CALL>APRS:!4903.50N/07201.75W-/A=001234 tail",
)
show(
    "EXT-018",
    a.Position(
        latitude,
        longitude,
        extensions=a.Extensions(phg=a.PHG(25, 20, 3, directivity_deg=90)),
    ),
    b"N0CALL>APRS:!4903.50N/07201.75W#PHG5132Radio",
)
show(
    "EXT-033",
    a.Position(
        latitude, longitude, extensions=a.Extensions(radio_range=a.RadioRange(50))
    ),
    b"N0CALL>APRS:!4903.50N/07201.75W#RNG0050Range",
)
show(
    "EXT-035",
    a.Position(
        latitude, longitude, extensions=a.Extensions(df_signal=a.DFSignal(2, 80, 6))
    ),
    b"N0CALL>APRS:!4903.50N/07201.75W\\DFS2360",
)
show(
    "EXT-045",
    a.Position(
        latitude,
        longitude,
        extensions=a.Extensions(
            df_bearing=a.DFBearing(270, hits_code=7, range_code=2, quality_code=7)
        ),
    ),
    b"N0CALL>APRS:=4903.50N/07201.75W\\088/036/270/727",
)
show(
    "FAP-034",
    a.Position(
        latitude, longitude, extensions=a.Extensions(dao=a.DAO("W", 3, 3, "decimal"))
    ),
    b"K0ELR-15>APOT02,WIDE1-1,WIDE2-1,qAo,K0ELR:/102033h4133.03NX09029.49Wv204/000!W33! 12.3V 21C/A=000665",
)
print(received["EXT-001"].payload.tail)
```

Output:

```text
EXT-001: construct Position; encode CodecNotImplemented
  decode Position; lat=49.058333, lon=-72.029167; tail=b'001/001'
EXT-011: construct Position; encode CodecNotImplemented
  decode Position; lat=49.058333, lon=-72.029167; tail=b'/A=001234 tail'
EXT-018: construct Position; encode CodecNotImplemented
  decode Position; lat=49.058333, lon=-72.029167; tail=b'PHG5132Radio'
EXT-033: construct Position; encode CodecNotImplemented
  decode Position; lat=49.058333, lon=-72.029167; tail=b'RNG0050Range'
EXT-035: construct Position; encode CodecNotImplemented
  decode Position; lat=49.058333, lon=-72.029167; tail=b'DFS2360'
EXT-045: construct Position; encode CodecNotImplemented
  decode Position; lat=49.058333, lon=-72.029167; tail=b'088/036/270/727'
FAP-034: construct Position; encode CodecNotImplemented
  decode Position; lat=41.550500, lon=-90.491500; tail=b'204/000!W33! 12.3V 21C/A=000665'
b'001/001'
```

## Objects, items, areas and signposts

**Model-only codecs.** Object identity, exact padding, lifecycle and timestamp
are separate from location. Items omit the object timestamp. Area and signpost
fields belong to the location's extensions. `alive=False` constructs a kill
report; it is not an invalid position.

```python
show(
    "OBJ-001",
    a.ObjectReport("LEADER", location, time, name_raw=b"LEADER   "),
    b"N0CALL>APRS:;LEADER   *092345z4903.50N/07201.75W>",
)
show(
    "OBJ-002",
    a.ObjectReport("LEADER", location, time, alive=False, name_raw=b"LEADER   "),
    b"N0CALL>APRS:;LEADER   _092345z4903.50N/07201.75W>",
)
show(
    "OBJ-013",
    a.ItemReport("AID #2", location),
    b"N0CALL>APRS:)AID #2!4903.50N/07201.75W>",
)
show(
    "OBJ-023",
    a.ObjectReport(
        "AREA",
        replace(
            location,
            symbol=a.Symbol("\\", "l"),
            extensions=a.Extensions(
                area=a.Area(0, 3, 10, 10, transmitted_anchor="circle_center")
            ),
        ),
        time,
    ),
    b"N0CALL>APRS:;AREA     *092345z4903.50N\\07201.75Wl010/310",
)
show(
    "OBJ-049",
    a.ItemReport(
        "SIGN",
        replace(
            location,
            symbol=a.Symbol("\\", "m"),
            extensions=a.Extensions(signpost=a.Signpost(b"5")),
        ),
    ),
    b"N0CALL>APRS:)SIGN!4903.50N\\07201.75Wm{5}",
)
```

Output:

```text
OBJ-001: construct ObjectReport; encode CodecNotImplemented
  decode Opaque; preserved=b';LEADER   *092345z4903.50N/07201.75W>'
OBJ-002: construct ObjectReport; encode CodecNotImplemented
  decode Opaque; preserved=b';LEADER   _092345z4903.50N/07201.75W>'
OBJ-013: construct ItemReport; encode CodecNotImplemented
  decode Opaque; preserved=b')AID #2!4903.50N/07201.75W>'
OBJ-023: construct ObjectReport; encode CodecNotImplemented
  decode Opaque; preserved=b';AREA     *092345z4903.50N\\07201.75Wl010/310'
OBJ-049: construct ItemReport; encode CodecNotImplemented
  decode Opaque; preserved=b')SIGN!4903.50N\\07201.75Wm{5}'
```

For a compressed object/item, set its wrapper's `encoding="compressed"` and
`compression=Compression(...)`. The shape is available, but its encoder is not.

## Weather and storms

**Model-only codecs.** `WeatherReport` is positionless; located weather uses
`Extensions.weather` on a `Position` or an object's `Location`. Storm metadata is
another extension. `None` means absent; `Measurement(None, ...)` means transmitted
but unavailable; numeric zero is a measured value. Units and rain windows are
explicit. Uncompressed complete-weather wind has a documented unit dispute;
choose a named interpretation or retain `disputed_knots_or_mph`, never silently
convert it.

```python
weather = a.Weather(
    wind_direction=a.Measurement(220, "degrees"),
    wind_speed=a.Measurement(4, "mph"),
    gust=a.Measurement(5, "mph"),
    temperature=a.Measurement(77, "fahrenheit"),
    rain_1h=a.Measurement(0.01, "inches"),
    rain_24h=a.Measurement(0.25, "inches"),
    rain_since_midnight=a.Measurement(0.12, "inches"),
    humidity=a.Measurement(50, "percent"),
    pressure=a.Measurement(990, "hPa"),
    software_code=b"W",
    device_code=b"RSW",
)
complete_weather = replace(
    weather, wind_speed=a.Measurement(4, "disputed_knots_or_mph")
)
show(
    "WX-001",
    a.WeatherReport(weather, a.Timestamp("mdhm_utc", 5, 56, day=9, month=10)),
    b"N0CALL>APRS:_10090556c220s004g005t077r001p025P012h50b09900WRSW",
)
show(
    "WX-052",
    a.ObjectReport(
        "WX-SITE",
        replace(
            location,
            symbol=a.Symbol("/", "_"),
            extensions=a.Extensions(weather=complete_weather),
        ),
        time,
    ),
    b"N0CALL>APRS:;WX-SITE  *092345z4903.50N/07201.75W_220/004g005t077r001p025P012h50b09900",
)
show(
    "WX-053",
    a.ObjectReport(
        "STORM",
        replace(
            location,
            symbol=a.Symbol("\\", "@"),
            extensions=a.Extensions(
                motion=a.Motion(88, 36),
                storm=a.Storm("HC", False, 150, 200, 980, 90, 30, 40),
            ),
        ),
        time,
    ),
    b"N0CALL>APRS:;STORM    *092345z4903.50N\\07201.75W@088/036/HC/150^200/0980>090&030%040",
)
unavailable = a.Measurement(None, "mph", raw=b"...")
gauge = a.WaterHeight(a.Measurement(20.1, "feet"), reference_datum=None)
print(unavailable)
print(gauge)
```

Output:

```text
WX-001: construct WeatherReport; encode CodecNotImplemented
  decode Opaque; preserved=b'_10090556c220s004g005t077r001p025P012h50b09900WRSW'
WX-052: construct ObjectReport; encode CodecNotImplemented
  decode Opaque; preserved=b';WX-SITE  *092345z4903.50N/07201.75W_220/004g005t077r001p025P012h50b09900'
WX-053: construct ObjectReport; encode CodecNotImplemented
  decode Opaque; preserved=b';STORM    *092345z4903.50N\\07201.75W@088/036/HC/150^200/0980>090&030%040'
Measurement(value=None, unit='mph', raw=b'...')
WaterHeight(measurement=Measurement(value=20.1, unit='feet', raw=None), reference_datum=None)
```

## Telemetry and definitions

**Model-only codecs.** Channel order is preserved, missing samples are `None`,
and calibration is separate. `TelemetryDefinition` carries PARM, UNIT, EQNS or
BITS addressed to the station being described. Classic telemetry, the special
`MIC` sequence, Mic-E telemetry, and base-91 comment telemetry share
`TelemetryData` with an explicit `encoding`.

```python
show(
    "TLM-001",
    a.Telemetry(
        a.TelemetryData(
            (199, 0, 255, 73, 123),
            (False, True, True, False, True, False, False, True),
            sequence=0,
        )
    ),
    b"N0CALL>APRS:T#000,199,000,255,073,123,01101001",
)
show(
    "TLM-010",
    a.TelemetryDefinition(
        "N0CALL-11",
        a.TelemetryParameters(
            (
                "Battery",
                "Btemp",
                "ATemp",
                "Pres",
                "Alt",
                "Camra",
                "Chut",
                "Sun",
                "10m",
                "ATV",
            )
        ),
    ),
    b"N0CALL>APRS::N0CALL-11:PARM.Battery,Btemp,ATemp,Pres,Alt,Camra,Chut,Sun,10m,ATV",
)
show(
    "TLM-011",
    a.TelemetryDefinition(
        "N0CALL-11",
        a.TelemetryUnits(
            (
                "v/100",
                "deg.F",
                "deg.F",
                "Mbar",
                "Kft",
                "Click",
                "OPEN",
                "on",
                "on",
                "hi",
            )
        ),
    ),
    b"N0CALL>APRS::N0CALL-11:UNIT.v/100,deg.F,deg.F,Mbar,Kft,Click,OPEN,on,on,hi",
)
show(
    "TLM-012",
    a.TelemetryDefinition(
        "N0CALL-11",
        a.TelemetryEquations(
            (
                a.Calibration(0, 5.2, 0),
                a.Calibration(0, 0.53, -32),
                a.Calibration(3, 4.39, 49),
                a.Calibration(-32, 3, 18),
                a.Calibration(1, 2, 3),
            )
        ),
    ),
    b"N0CALL>APRS::N0CALL-11:EQNS.0,5.2,0,0,.53,-32,3,4.39,49,-32,3,18,1,2,3",
)
show(
    "TLM-013",
    a.TelemetryDefinition(
        "N0CALL-11",
        a.TelemetryBits(
            (True, False, True, True, False, False, False, False), b"Balloon project"
        ),
    ),
    b"N0CALL>APRS::N0CALL-11:BITS.10110000,Balloon project",
)
show(
    "FAP-418",
    a.Position(
        latitude,
        longitude,
        extensions=a.Extensions(
            telemetry=a.TelemetryData(
                (0, 0, 0, 0, 0), (False,) * 8, sequence=0, encoding="base91_comment"
            )
        ),
    ),
    b"OH7FDN>APZMDR,OH7AA-1*,WIDE2-1,qAR,OH7AA:!6253.52N/02739.47E>036/010/A=000465 |!!!!!!!!!!!!!!|",
)
```

Output:

```text
TLM-001: construct Telemetry; encode CodecNotImplemented
  decode Opaque; preserved=b'T#000,199,000,255,073,123,01101001'
TLM-010: construct TelemetryDefinition; encode CodecNotImplemented
  decode Opaque; preserved=b':N0CALL-11:PARM.Battery,Btemp,ATemp,Pres,Alt,Camra,Chut,Sun,10m,ATV'
TLM-011: construct TelemetryDefinition; encode CodecNotImplemented
  decode Opaque; preserved=b':N0CALL-11:UNIT.v/100,deg.F,deg.F,Mbar,Kft,Click,OPEN,on,on,hi'
TLM-012: construct TelemetryDefinition; encode CodecNotImplemented
  decode Opaque; preserved=b':N0CALL-11:EQNS.0,5.2,0,0,.53,-32,3,4.39,49,-32,3,18,1,2,3'
TLM-013: construct TelemetryDefinition; encode CodecNotImplemented
  decode Opaque; preserved=b':N0CALL-11:BITS.10110000,Balloon project'
FAP-418: construct Position; encode CodecNotImplemented
  decode Position; lat=62.892000, lon=27.657833; tail=b'036/010/A=000465 |!!!!!!!!!!!!!!|'
```

## Messages, acknowledgments and bulletins

**Working:** basic messages and ack/rej. **Model-only:** reply-ack,
auto-answer, bulletin/announcement/group and NWS semantics. IDs remain strings
so leading zeros survive. NWS reference IDs and reply acknowledgments are
separate from ordinary message IDs.

```python
show("MSG-003", a.Message("W1AW", b"Hello", "1"), b"N0CALL>APRS::W1AW     :Hello{1")
show("MSG-013", a.Acknowledgment("W1AW", "1"), b"N0CALL>APRS::W1AW     :ack1")
show(
    "MSG-016",
    a.Acknowledgment("W1AW", "1", rejected=True),
    b"N0CALL>APRS::W1AW     :rej1",
)
show(
    "MSG-023",
    a.Message("W1AW", b"Reply", reply_ack=a.ReplyAck("01")),
    b"N0CALL>APRS::W1AW     :Reply{01}",
)
show(
    "MSG-026",
    a.AutoAnswer("W1AW", b"Away from keyboard"),
    b"N0CALL>APRS::W1AW     :AA:Away from keyboard",
)
show("MSG-028", a.Bulletin("0", b"Test notice"), b"N0CALL>APRS::BLN0     :Test notice")
show(
    "MSG-030",
    a.Bulletin("A", b"Test notice", announcement=True),
    b"N0CALL>APRS::BLNA     :Test notice",
)
show(
    "MSG-032",
    a.Bulletin("4", b"Test notice", group="WX"),
    b"N0CALL>APRS::BLN4WX   :Test notice",
)
show(
    "MSG-034",
    a.NWSBulletin(
        "NWS-WARN", b"092010z,THUNDER_STORM,AR_ASHLEY,", reference_id="S9JbA"
    ),
    b"N0CALL>APRS::NWS-WARN :092010z,THUNDER_STORM,AR_ASHLEY,{S9JbA",
)
```

Output:

```text
MSG-003: construct Message; encode b'N0CALL>APRS::W1AW     :Hello{1'
  decode Message; to='W1AW'; text=b'Hello'; id='1'
MSG-013: construct Acknowledgment; encode b'N0CALL>APRS::W1AW     :ack1'
  decode Acknowledgment; Acknowledgment(addressee='W1AW', message_id='1', rejected=False, reply_ack=None)
MSG-016: construct Acknowledgment; encode b'N0CALL>APRS::W1AW     :rej1'
  decode Acknowledgment; Acknowledgment(addressee='W1AW', message_id='1', rejected=True, reply_ack=None)
MSG-023: construct Message; encode CodecNotImplemented
  decode Opaque; preserved=b':W1AW     :Reply{01}'
MSG-026: construct AutoAnswer; encode CodecNotImplemented
  decode Opaque; preserved=b':W1AW     :AA:Away from keyboard'
MSG-028: construct Bulletin; encode CodecNotImplemented
  decode Opaque; preserved=b':BLN0     :Test notice'
MSG-030: construct Bulletin; encode CodecNotImplemented
  decode Opaque; preserved=b':BLNA     :Test notice'
MSG-032: construct Bulletin; encode CodecNotImplemented
  decode Opaque; preserved=b':BLN4WX   :Test notice'
MSG-034: construct NWSBulletin; encode CodecNotImplemented
  decode Opaque; preserved=b':NWS-WARN :092010z,THUNDER_STORM,AR_ASHLEY,{S9JbA'
```

## NTS radiograms

**Model-only codecs.** Each radiogram record is a separate `NTSMessage`, not a
whole assembled radiogram. `NTSText.line` selects N1–N6. All six record shapes
below have named fields; routing and delivery remain application concerns.

```python
show(
    "MSG-035",
    a.NTSMessage(
        "W1AW",
        a.NTSHeader("12", "R", "HXA", "N0CALL", "5", "REDMOND WA", "1800", "OCT 15"),
        "001",
    ),
    b"N0CALL>APRS::W1AW     :N#\\12\\R\\HXA\\N0CALL\\5\\REDMOND WA\\1800\\OCT 15{001",
)
show(
    "MSG-036",
    a.NTSMessage(
        "W1AW", a.NTSAddress(("ADAM", "123 MAIN ST", "REDMOND WA", "98052")), "001"
    ),
    b"N0CALL>APRS::W1AW     :NA\\ADAM\\123 MAIN ST\\REDMOND WA\\98052{001",
)
show(
    "MSG-037",
    a.NTSMessage("W1AW", a.NTSPhone("5550100"), "001"),
    b"N0CALL>APRS::W1AW     :NP\\5550100{001",
)
show(
    "MSG-038",
    a.NTSMessage("W1AW", a.NTSText(1, b"LINE 1 TEXT"), "001"),
    b"N0CALL>APRS::W1AW     :N1\\LINE 1 TEXT{001",
)
show(
    "MSG-044",
    a.NTSMessage("W1AW", a.NTSSignature(b"TEST SENDER"), "001"),
    b"N0CALL>APRS::W1AW     :NS\\TEST SENDER{001",
)
show(
    "MSG-045",
    a.NTSMessage("W1AW", a.NTSRouting("W1AW", "151800Z", "N0CALL", "151805Z"), "001"),
    b"N0CALL>APRS::W1AW     :NR\\W1AW\\151800Z\\N0CALL\\151805Z{001",
)
```

Output:

```text
MSG-035: construct NTSMessage; encode CodecNotImplemented
  decode Opaque; preserved=b':W1AW     :N#\\12\\R\\HXA\\N0CALL\\5\\REDMOND WA\\1800\\OCT 15{001'
MSG-036: construct NTSMessage; encode CodecNotImplemented
  decode Opaque; preserved=b':W1AW     :NA\\ADAM\\123 MAIN ST\\REDMOND WA\\98052{001'
MSG-037: construct NTSMessage; encode CodecNotImplemented
  decode Opaque; preserved=b':W1AW     :NP\\5550100{001'
MSG-038: construct NTSMessage; encode CodecNotImplemented
  decode Opaque; preserved=b':W1AW     :N1\\LINE 1 TEXT{001'
MSG-044: construct NTSMessage; encode CodecNotImplemented
  decode Opaque; preserved=b':W1AW     :NS\\TEST SENDER{001'
MSG-045: construct NTSMessage; encode CodecNotImplemented
  decode Opaque; preserved=b':W1AW     :NR\\W1AW\\151800Z\\N0CALL\\151805Z{001'
```

## Queries, responses and capabilities

**Model-only structured codecs.** General queries omit an addressee; directed
queries supply one. Response packets currently decode as ordinary `Message`
text, not `QueryResponse`. Capability tokens retain their order and optional
values. Unknown query names and capability names can be represented.

```python
show("QRY-001", a.Query("APRS"), b"N0CALL>APRS:?APRS?")
show(
    "QRY-008",
    a.Query("APRSH", addressee="W1AW", heard_station="N0CALL"),
    b"N0CALL>APRS::W1AW     :?APRSH N0CALL   ",
)
show(
    "QRY-015",
    a.QueryResponse("W1AW", a.DirectStations(("W1AW", "W2ABC"))),
    b"N0CALL>APRS::W1AW     :Directs= W1AW W2ABC",
)
show(
    "QRY-016",
    a.QueryResponse("W1AW", a.HeardStation("N0CALL", (1, 3, 2, None, None, 4, 5, 6))),
    b"N0CALL>APRS::W1AW     :N0CALL HEARD: 1 3 2 . . 4 5 6",
)
show(
    "QRY-017",
    a.QueryResponse(
        "W1AW",
        a.TraceRoute(
            a.Header("N0CALL", "APRS", (a.PathHop("DIGI1"), a.PathHop("WIDE", True)))
        ),
    ),
    b"N0CALL>APRS::W1AW     :N0CALL>APRS,DIGI1,WIDE*:",
)
show(
    "QRY-018",
    a.Capabilities(
        (
            a.CapabilityToken("IGATE"),
            a.CapabilityToken("MSG_CNT", b"43"),
            a.CapabilityToken("LOC_CNT", b"14"),
        )
    ),
    b"N0CALL>APRS:<IGATE,MSG_CNT=43,LOC_CNT=14",
)
```

Output:

```text
QRY-001: construct Query; encode CodecNotImplemented
  decode Opaque; preserved=b'?APRS?'
QRY-008: construct Query; encode CodecNotImplemented
  decode Opaque; preserved=b':W1AW     :?APRSH N0CALL   '
QRY-015: construct QueryResponse; encode CodecNotImplemented
  decode Message; to='W1AW'; text=b'Directs= W1AW W2ABC'; id=None
QRY-016: construct QueryResponse; encode CodecNotImplemented
  decode Message; to='W1AW'; text=b'N0CALL HEARD: 1 3 2 . . 4 5 6'; id=None
QRY-017: construct QueryResponse; encode CodecNotImplemented
  decode Message; to='W1AW'; text=b'N0CALL>APRS,DIGI1,WIDE*:'; id=None
QRY-018: construct Capabilities; encode CodecNotImplemented
  decode Opaque; preserved=b'<IGATE,MSG_CNT=43,LOC_CNT=14'
```

## Status, grid and beam reports

**Working:** text and DHM UTC timestamps. **Model-only:** grid/symbol and beam
extensions. Their input currently remains in `Status.text`; it is not decoded
into the structured fields shown in construction. HMS/local timestamp-looking
status text also remains text, as required by the specification.

```python
show("STA-002", a.Status(b"Ready"), b"N0CALL>APRS:>Ready")
show(
    "STA-007",
    a.Status(b"x" * 55, timestamp=time),
    b"N0CALL>APRS:>092345zxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
)
show(
    "STA-009",
    a.Status(b" Home", grid=a.GridLocator("IO91SX"), symbol=a.Symbol("/", "-")),
    b"N0CALL>APRS:>IO91SX/- Home",
)
show("STA-013", a.Status(b"Ready", beam=a.Beam(0, 10)), b"N0CALL>APRS:>Ready^01")
```

Output:

```text
STA-002: construct Status; encode b'N0CALL>APRS:>Ready'
  decode Status; text=b'Ready'; timestamp=None
STA-007: construct Status; encode b'N0CALL>APRS:>092345zxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
  decode Status; text=b'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'; timestamp=Timestamp(kind='dhm_utc', hour=23, minute=45, day=9, second=None, month=None, raw=None)
STA-009: construct Status; encode CodecNotImplemented
  decode Status; text=b'IO91SX/- Home'; timestamp=None
STA-013: construct Status; encode CodecNotImplemented
  decode Status; text=b'Ready^01'; timestamp=None
```

## NMEA sentences

**Model-only codecs.** The five sentence types in the baseline have explicit
fields: GGA, GLL, RMC, VTG and WPL. Raw date/time, checksum evidence and fix
validity are distinct. An unknown or invalid fix must not become a trusted
position merely because coordinates exist. These inputs have the exact checksums
from NME-001–005; current decoding preserves each entire sentence.

```python
show(
    "NME-001",
    a.NMEAReport(
        a.GGA(
            b"102705",
            a.Coordinates(51 + 57.9762 / 60, -29.3256 / 60),
            fix_quality=1,
            satellites=4,
            hdop=2,
            altitude_msl_m=75.7,
            geoid_separation_m=47.6,
        )
    ),
    b"N0CALL>APRS:$GPGGA,102705,5157.9762,N,00029.3256,W,1,04,2.0,75.7,M,47.6,M,,*62",
)
show(
    "NME-002",
    a.NMEAReport(
        a.GLL(a.Coordinates(25 + 54.459 / 60, -(80 + 20.187 / 60)), b"154027.281", "A")
    ),
    b"N0CALL>APRS:$GPGLL,2554.459,N,08020.187,W,154027.281,A*22",
)
show(
    "NME-003",
    a.NMEAReport(
        a.RMC(
            b"063909",
            b"291099",
            "A",
            a.Coordinates(33 + 49.4302 / 60, -(117 + 0.3721 / 60)),
            speed_knots=43.022,
            course_deg=89.3,
            magnetic_variation=13.6,
            magnetic_variation_direction="E",
        )
    ),
    b"N0CALL>APRS:$GPRMC,063909,A,3349.4302,N,11700.3721,W,43.022,89.3,291099,13.6,E*52",
)
show(
    "NME-004",
    a.NMEAReport(
        a.VTG(course_true_deg=318.7, speed_knots=35.1, speed_kmh_reported=65.0)
    ),
    b"N0CALL>APRS:$GPVTG,318.7,T,,M,35.1,N,65.0,K*69",
)
show(
    "NME-005",
    a.NMEAReport(a.WPL(a.Coordinates(latitude, longitude), b"AID2")),
    b"N0CALL>APRS:$GPWPL,4903.50,N,07201.75,W,AID2*2A",
)
```

Output:

```text
NME-001: construct NMEAReport; encode CodecNotImplemented
  decode Opaque; preserved=b'$GPGGA,102705,5157.9762,N,00029.3256,W,1,04,2.0,75.7,M,47.6,M,,*62'
NME-002: construct NMEAReport; encode CodecNotImplemented
  decode Opaque; preserved=b'$GPGLL,2554.459,N,08020.187,W,154027.281,A*22'
NME-003: construct NMEAReport; encode CodecNotImplemented
  decode Opaque; preserved=b'$GPRMC,063909,A,3349.4302,N,11700.3721,W,43.022,89.3,291099,13.6,E*52'
NME-004: construct NMEAReport; encode CodecNotImplemented
  decode Opaque; preserved=b'$GPVTG,318.7,T,,M,35.1,N,65.0,K*69'
NME-005: construct NMEAReport; encode CodecNotImplemented
  decode Opaque; preserved=b'$GPWPL,4903.50,N,07201.75,W,AID2*2A'
```

## Third-party, user-defined and raw packets

**Working:** bounded third-party nesting, user-defined data and explicit
invalid/test bodies. `Reserved` and `Opaque` allow raw construction without
claiming known semantics. User-defined data can contain all byte values in
unframed monitor packets; RF length limits still apply. Nesting is capped by
`DecodeOptions.max_depth` / `EncodeOptions.max_depth` (default four wrappers).

```python
inner = a.Packet(
    a.Header("W1AW", "APRS", (a.PathHop("TCPIP"), a.PathHop("N0GATE", True))),
    a.Message("N0CALL", b"Hello", "01"),
)
show(
    "NET-001",
    a.ThirdParty(inner),
    b"N0GATE>APRS,WIDE2-1:}W1AW>APRS,TCPIP,N0GATE*::N0CALL   :Hello{01",
    header=a.Header("N0GATE", "APRS", (a.PathHop("WIDE2-1"),)),
)
show("OTH-005", a.UserDefined(b"Q", b"1", b"qwerty"), b"N0CALL>APRS:{Q1qwerty")
show(
    "OTH-008",
    a.InvalidTest(
        b"191146,V,4214.2466,N,07303.5181,W,417.238,114.5,091099,14.7,W/GPS FIX"
    ),
    b"N0CALL>APRS:,191146,V,4214.2466,N,07303.5181,W,417.238,114.5,091099,14.7,W/GPS FIX",
)
show("OTH-031", a.Reserved(ord("~"), b"TEST"), b"N0CALL>APRS:~TEST")
show("OTH-014", a.Opaque(b'"TEST'), b'N0CALL>APRS:"TEST')
binary = a.Packet(header, a.UserDefined(b"Q", b"1", b"\x00\xff\r\n"))
wire = a.serialize_packet(binary)
print(wire)
print(a.parse_packet(wire).payload)
```

Output:

```text
NET-001: construct ThirdParty; encode b'N0GATE>APRS,WIDE2-1:}W1AW>APRS,TCPIP,N0GATE*::N0CALL   :Hello{01'
  decode ThirdParty; ThirdParty(packet=Packet(header=Header(source='W1AW', destination='APRS', path=(PathHop(address='TCPIP', repeated=False), PathHop(address='N0GATE', repeated=True))), payload=Message(addressee='N0CALL', text=b'Hello', message_id='01', reply_ack=None), header_semantics=None))
OTH-005: construct UserDefined; encode b'N0CALL>APRS:{Q1qwerty'
  decode UserDefined; UserDefined(user_id=b'Q', user_type=b'1', data=b'qwerty')
OTH-008: construct InvalidTest; encode b'N0CALL>APRS:,191146,V,4214.2466,N,07303.5181,W,417.238,114.5,091099,14.7,W/GPS FIX'
  decode InvalidTest; InvalidTest(data=b'191146,V,4214.2466,N,07303.5181,W,417.238,114.5,091099,14.7,W/GPS FIX')
OTH-031: construct Reserved; encode b'N0CALL>APRS:~TEST'
  decode Opaque; preserved=b'~TEST'
OTH-014: construct Opaque; encode b'N0CALL>APRS:"TEST'
  decode Opaque; preserved=b'"TEST'
b'N0CALL>APRS:{Q1\x00\xff\r\n'
UserDefined(user_id=b'Q', user_type=b'1', data=b'\x00\xff\r\n')
```

## Vendor, historical and external formats

**Model-only codecs.** Raw weather wrappers identify vendor families but do not
invent their measurement grammar. `Agrelo` models the bearing/quality layout in
APRS101 Appendix 1 p.103; its illustrative `%123/4` input remains opaque.
Maidenhead beacons, X1J and non-APRS beacons also remain opaque under the default
modern profile. Historical object/bulletin shapes use their `legacy=True` flag.

`ExternalExtension` is a named raw boundary for grammars outside the supplied
baseline. Its example deliberately wraps a real vendor input. There is **no**
fabricated polygon/line packet: an authoritative grammar is still needed.

```python
show(
    "OTH-001",
    a.RawWeather(
        "ultimeter_2000", b"!!006B005803500000----03E9--------002105140000005D"
    ),
    b"N0CALL>APRS:!!006B005803500000----03E9--------002105140000005D",
)
show(
    "OTH-002",
    a.RawWeather("ultimeter_ii", b"#50B7500820082"),
    b"N0CALL>APRS:#50B7500820082",
)
show(
    "OTH-003",
    a.RawWeather("ultw", b"$ULTW0031003702CE0069----000086A00001----011901CC00000005"),
    b"N0CALL>APRS:$ULTW0031003702CE0069----000086A00001----011901CC00000005",
)
show(
    "OTH-004",
    a.RawWeather("peet_logging", b"*7007600000000"),
    b"N0CALL>APRS:*7007600000000",
)
show("Agrelo", a.Agrelo(123, 4), b"N0CALL>APRS:%123/4")
show("OTH-012", a.MaidenheadBeacon(a.GridLocator("IO91")), b"N0CALL>APRS:[IO91]")
show(
    "OTH-034",
    a.LegacyPosition(b"X", a.Position(latitude, longitude)),
    b"N0CALL>BEACON:X!4903.50N/07201.75W-",
    header=a.Header("N0CALL", "BEACON"),
)
show("OTH-009", a.NonAPRSBeacon(b"UIDIGI ready"), b"N0CALL>APRS:UIDIGI ready")
show(
    "external-vendor",
    a.ExternalExtension(
        "vendor", b"$ULTW0031003702CE0069----000086A00001----011901CC00000005"
    ),
    b"N0CALL>APRS:$ULTW0031003702CE0069----000086A00001----011901CC00000005",
)
```

Output:

```text
OTH-001: construct RawWeather; encode CodecNotImplemented
  decode Opaque; preserved=b'!!006B005803500000----03E9--------002105140000005D'
OTH-002: construct RawWeather; encode CodecNotImplemented
  decode Opaque; preserved=b'#50B7500820082'
OTH-003: construct RawWeather; encode CodecNotImplemented
  decode Opaque; preserved=b'$ULTW0031003702CE0069----000086A00001----011901CC00000005'
OTH-004: construct RawWeather; encode CodecNotImplemented
  decode Opaque; preserved=b'*7007600000000'
Agrelo: construct Agrelo; encode CodecNotImplemented
  decode Opaque; preserved=b'%123/4'
OTH-012: construct MaidenheadBeacon; encode CodecNotImplemented
  decode Opaque; preserved=b'[IO91]'
OTH-034: construct LegacyPosition; encode CodecNotImplemented
  decode Opaque; preserved=b'X!4903.50N/07201.75W-'
OTH-009: construct NonAPRSBeacon; encode CodecNotImplemented
  decode Opaque; preserved=b'UIDIGI ready'
external-vendor: construct ExternalExtension; encode CodecNotImplemented
  decode Opaque; preserved=b'$ULTW0031003702CE0069----000086A00001----011901CC00000005'
```

## Strict decoding, recovery and line framing

The default preserves unsupported payloads as `Opaque`. Strict unsupported
handling raises `CodecNotImplemented`. Malformed supported fields have a separate
policy; invalid outer envelopes, missing context and depth limits still raise.
These options do not promise universal lossless recovery.

```python
wire = b"N0CALL>APRS:?APRS?"
try:
    a.parse_packet(wire, options=a.DecodeOptions(unsupported="raise"))
except a.CodecNotImplemented as error:
    print(type(error).__name__, str(error))

malformed = b"N0CALL>APRS:!9000.01N/07201.75W-"
recovered = a.parse_packet(malformed, options=a.DecodeOptions(malformed="opaque"))
print(recovered.payload)

line = a.serialize_tnc2_line(a.Packet(header, a.Status(b"Ready")))
print(line)
print(a.parse_tnc2_line(line).payload)
try:
    a.serialize_tnc2_line(binary)
except a.EnvelopeError as error:
    print(type(error).__name__, str(error))
```

Output:

```text
CodecNotImplemented unsupported information field family
Opaque(information=b'!9000.01N/07201.75W-', reason='coordinate out of range', diagnostic=Diagnostic(code='malformed', message='coordinate out of range'))
b'N0CALL>APRS:>Ready\r\n'
Status(text=b'Ready', timestamp=None, grid=None, symbol=None, beam=None)
EnvelopeError payload cannot be represented in line-oriented TNC2
```

The raw APIs do not strip CR/LF. Use the line helpers for transport terminators;
`original_wire` on a line-parsed packet excludes that terminator. Capabilities
can also be inspected without attempting a codec: `print(a.capability_for(a.MicE))`
or `print(a.get_capabilities())`. `partial` support is not a guarantee for every
field combination.

## JSON conversion

JSON works for full packets, standalone payloads and all structured fields,
including models whose APRS wire codecs are unimplemented. It is a separate
conversion API: no radio framing, coordinate quantization or wire-codec call
is involved. There is **no special type/discriminator key**.

`to_json` / `from_json` handle JSON text; `to_json_dict` / `from_json_dict` handle
JSON-compatible objects. `expected_type=...` gives a typed return and context
for a sparse standalone field. Otherwise meaningful present fields determine
the model. Unknown keys, conflicts and ambiguous shapes raise `JSONModelError`
(or its `AmbiguousJSONError` subclass), never get silently ignored.

```python
# The packet's header and payload remain distinct JSON objects.
json_packet = a.Packet(a.Header("N0CALL", "APRS"), a.Message("W1AW", b"Hello", "003"))
print(a.to_json(json_packet, indent=2))
restored: a.Packet = a.from_json(a.to_json(json_packet), expected_type=a.Packet)
print(restored.payload)
```

Output:

```text
{
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "addressee": "W1AW",
    "message_text": "Hello",
    "message_id": "003"
  }
}
Message(addressee='W1AW', text=b'Hello', message_id='003', reply_ack=None)
```

```python
# Standalone payload and field inference use semantic keys, not class tags.
print(a.to_json(a.Status(b"Ready")))
print(a.to_json(a.NonAPRSBeacon(b"Ready")))
print(a.from_json('{"channel_units":["deg.C",null,"V"]}'))
print(a.from_json('{"value":null,"unit":"mph","raw":"..."}'))
print(a.from_json_dict({"latitude_deg": 49, "longitude_deg": -72, "messaging": False}))
```

Output:

```text
{"status_text":"Ready"}
{"beacon_text":"Ready"}
TelemetryUnits(channels=('deg.C', None, 'V'))
Measurement(value=None, unit='mph', raw=b'...')
Position(latitude_deg=49.0, longitude_deg=-72.0, symbol=Symbol(table_id='/', code='-'), messaging=False, timestamp=None, tail=b'', encoding='uncompressed', ambiguity=None, compression=None, extensions=Extensions(motion=None, altitude=None, phg=None, radio_range=None, df_signal=None, df_bearing=None, dao=None, area=None, signpost=None, weather=None, storm=None, telemetry=None), comment=b'')
```

```python
# All 256 byte values are reversible; text is not implicitly UTF-8 encoded.
binary_json = a.to_json(a.UserDefined(b"Q", b"1", b"\x00\xff\r\n"))
print(binary_json)
print(a.from_json(binary_json))

# Missing reading, transmitted unavailable reading, and zero are distinct.
json_weather = a.WeatherReport(a.Weather(wind_speed=a.Measurement(None, "mph")))
print(a.to_json(json_weather))
print(a.from_json(a.to_json(json_weather)) == json_weather)

# JSON supports an object report even though its wire codec is missing.
json_object = a.ObjectReport(
    "AID", a.Location(49, -72), a.Timestamp("dhm_utc", 12, 30, day=17)
)
print(type(a.from_json(a.to_json(json_object))).__name__)
print(a.capability_for(json_object).encode)
```

Output:

```text
{"user_id":"Q","user_type":"1","data":"\u0000\u00ff\r\n"}
UserDefined(user_id=b'Q', user_type=b'1', data=b'\x00\xff\r\n')
{"weather":{"wind_speed":{"value":null,"unit":"mph"}}}
True
ObjectReport
unimplemented
```

```python
# An empty object supplies no evidence of which default field model is meant.
try:
    a.from_json("{}")
except a.AmbiguousJSONError as error:
    print(type(error).__name__)
empty_weather: a.Weather = a.from_json("{}", expected_type=a.Weather)
print(a.to_json(empty_weather))

try:
    a.from_json('{"status_text":"Ready","message_text":"Hello"}')
except a.JSONModelError as error:
    print(type(error).__name__)
```

Output:

```text
AmbiguousJSONError
{"wind_speed":null}
JSONModelError
```

Byte fields are Latin-1 byte-carrier strings, matching the vector document:
`"Hello"` represents ASCII bytes, `"\u00ff"` represents the single byte `0xff`.
The serializer escapes non-ASCII/control characters; characters above U+00FF
are rejected in byte fields. Normal string fields remain Unicode strings.

Compact output omits optional defaults but retains meaningful inference fields,
such as `messaging: false` for a position report. Use `include_defaults=True`
to emit all fields. Omitted optional fields and explicit `null` normalize to
the same Python `None` where the model defines that default; a measurement's
required `value: null` explicitly means unavailable. Required fields cannot be
omitted, and `null` is rejected for non-nullable fields.

JSON validates field types and enum choices, not every APRS range or cross-field
wire constraint. It preserves `original_wire` and diagnostic metadata when
present, but does not claim those bytes agree with edited semantic fields.
Nested packets are supported with a separate JSON `max_depth` (default 64).
See the [JSON schema and inference rules](docs/JSON_FORMAT.md) for all families,
field aliases, sparse/default shapes and limits.

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
  and policy options are keyword-only. The package version is `0.0.1a3`.

## License

`hamkit-aprs` is distributed under the terms of the [MIT](LICENSE) license.
