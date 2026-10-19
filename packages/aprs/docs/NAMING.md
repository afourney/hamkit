# Public naming guide

Python model names and JSON type tags describe APRS concepts. Short names are
used where the meaning is clear inside an APRS library; a qualifier is added
where a short name would collide with another concept or a common Python name.
The [JSON reference](JSON_FORMAT.md) lists every model, its tag and fields.
Attribute names such as `wind_speed` describe the value they hold. Everything
public is exported from `hamkit.aprs`; its submodules are private. The models
are not designed for subclassing: serialization, `check_packet` and JSON export
all reject subclass instances.

## Weather and telemetry

`Weather` contains measurements, an optional timestamp and a comment.
`Telemetry` contains channels, sequence, encoding/raw evidence and a comment.
Both models work as full payloads and as nested extension fields. Their fields
are direct attributes in Python and direct properties in JSON. Whether a report
is complete (required slots, timestamp) is a conformance question, checked when
the packet is sent, not a property of the model.

## Short names in context

| Model or alias               | Meaning                                                                                      |
| ---------------------------- | -------------------------------------------------------------------------------------------- |
| `Object`, `Item`             | Named APRS position reports, with and without an object timestamp.                           |
| `Extent`, `Bounds`           | A latitude/longitude cell, returned by grid and ambiguity properties.                        |
| `Grid`                       | A Maidenhead locator; its bounds and center are computed.                                    |
| `Range`                      | Radio range.                                                                                 |
| `Signal`, `Bearing`          | Direction-finding signal and bearing information.                                            |
| `Hop`                        | An address in a packet's path.                                                               |
| `Radiogram`                  | One NTS message record and its delivery envelope, not a guarantee of an assembled radiogram. |
| `Footprint`                  | A query's geographic scope.                                                                  |
| `Response`, `ResponseValue`  | A query response and the union of its content variants.                                      |
| `Trace`                      | Trace-route response content.                                                                |
| `Capabilities`, `Capability` | A station's advertised capability tokens, distinct from `CodecSupport`.                      |
| `NMEA`                       | An NMEA report containing a typed sentence.                                                  |
| `Maidenhead`                 | The historical bracket-style grid beacon.                                                    |
| `Beacon`                     | Uninterpreted non-APRS beacon text.                                                          |
| `Invalid`                    | An explicitly invalid/test payload.                                                          |
| `Diagnostic`                 | One finding: unsupported, malformed or nonconforming, with a field path.                     |
| `Malformed`                  | Input with undecodable fields; a parse result, never a Packet or payload.                    |

Named unions describe allowed values; they are not instantiable models or JSON
tags. Type aliases such as `TimestampKind` and
`TelemetryEncoding` include their subject so their values are understandable
outside a field annotation.

## Qualified names

These qualifiers distinguish packet formats, field meanings or operational roles.

| Python / JSON                                           | Reason                                                                                   |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `TelemetryDefinition` / `telemetry_definition`          | A PARM./UNIT./EQNS./BITS. message; "definition" alone says nothing.                      |
| `TelemetryParameters`, `TelemetryUnits` / `telemetry_…` | Telemetry channel names and units; `Units` would collide with the measurement `Unit`.    |
| `TelemetryEquations`, `TelemetryBits` / `telemetry_…`   | Calibration coefficients and sense bits for telemetry channels.                          |
| `NTSHeader`, `NTSAddress`, `NTSText` / `nts_…`          | NTS radiogram records; `Address` or `Text` would read as an AX.25 address or plain text. |
| `NTSPhone`, `NTSSignature`, `NTSRouting` / `nts_…`      | The remaining NTS record variants, named consistently.                                   |
| `WaterHeight` / `water_height`                          | Gauge height and datum differ from altitude; “height” alone hides the measured quantity. |
| `NMEAMetadata` / `nmea_metadata`                        | NMEA talker/checksum evidence differs from packet/header metadata.                       |
| `MicE` / `mic_e`                                        | Established Mic-E protocol name, not two independently removable words.                  |
| `AutoAnswer` / `auto_answer`                            | Established automatic-answer message subtype.                                            |
| `NWSBulletin` / `nws_bulletin`                          | NWS product envelope differs from an ordinary `Bulletin`.                                |
| `DirectStations` / `direct_stations`                    | Explicitly reports directly heard stations, not arbitrary station lists.                 |
| `HeardStation` / `heard_station`                        | Heard-response counts differ from a generic station identity.                            |
| `ThirdParty` / `third_party`                            | Established encapsulation protocol term.                                                 |
| `UserDefined` / `user_defined`                          | Established user-ID/type/data protocol envelope.                                         |
| `RawWeather` / `raw_weather`                            | Vendor bytes and optional interpretation differ from structured `Weather`.               |
| `LegacyPosition` / `legacy_position`                    | Historical prefix/position wrapper differs from `Position`.                              |
| `ExternalExtension` / `external_extension`              | External/vendor grammar and source evidence differ from standard `Extensions`.           |
| `CodecSupport`, `codec_support()`                       | Which wire codecs exist; unrelated to a station's `Capabilities`.                        |

## Functions and errors

Wire functions pair `parse_*` with `serialize_*` at each level: packet, payload
and TNC2 line. JSON functions pair `from_json*` with `to_json*`. `check_packet`
returns conformance findings; `validate_packet` raises exactly as
`serialize_packet` would. Every exception ends in `Error` and derives from
`APRSError`, itself a `ValueError`.
