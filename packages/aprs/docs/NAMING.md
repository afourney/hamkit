# Public naming guide

Python model names and JSON type tags describe APRS concepts. Short names are
used where the meaning is clear; qualifiers distinguish different concepts.
The [JSON reference](JSON_FORMAT.md) lists all 82 models, their tags and fields.
Attribute names such as `wind_speed` describe the value they hold.

## Weather and telemetry

`Weather` contains measurements, an optional timestamp and a comment.
`Telemetry` contains channels, sequence, encoding/raw evidence and a comment.
Both models work as full payloads and as fixed nested fields. Their fields are
direct attributes in Python and direct properties in JSON.

Standalone/payload JSON requires `type: weather` or `type: telemetry`. Fixed
nested fields omit the tag because their declared class supplies context.
Weather and telemetry wire encoding/decoding are unimplemented.

## Short names in context

| Model or alias                                     | Meaning                                                                                      |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `Object`, `Item`                                   | Named APRS position reports, with and without an object timestamp.                           |
| `Extent`, `Bounds`                                 | A latitude/longitude cell's bounds, and a two-number axis interval.                          |
| `Grid`                                             | A grid locator with optional bounds and center.                                              |
| `Range`                                            | Radio range.                                                                                 |
| `Signal`, `Bearing`                                | Direction-finding signal and bearing information.                                            |
| `Hop`                                              | An address in a packet's path.                                                               |
| `Definition`                                       | A telemetry definition addressed to a station.                                               |
| `Parameters`, `Units`, `Equations`, `Bits`         | Telemetry definition variants.                                                               |
| `DefinitionValue`                                  | The union of telemetry definition variants.                                                  |
| `Radiogram`                                        | One NTS message record and its delivery envelope, not a guarantee of an assembled radiogram. |
| `Address`, `Phone`, `Text`, `Signature`, `Routing` | NTS record variants.                                                                         |
| `Footprint`                                        | A query's geographic scope.                                                                  |
| `Response`, `ResponseValue`                        | A query response and the union of its content variants.                                      |
| `Trace`                                            | Trace-route response content.                                                                |
| `Capability`                                       | A protocol capability token, distinct from runtime `CodecCapability`.                        |
| `NMEA`                                             | An NMEA report containing a typed sentence.                                                  |
| `Maidenhead`                                       | The historical bracket-style grid beacon.                                                    |
| `Beacon`                                           | Uninterpreted non-APRS beacon text.                                                          |
| `Invalid`                                          | An explicitly invalid/test payload.                                                          |

Named unions describe allowed values; they are not instantiable models or JSON
tags. Public policy aliases such as `ValidationProfile`, `TimestampKind` and
`TelemetryEncoding` include their subject so their values are understandable
outside a field annotation.

## Qualified names

These qualifiers distinguish packet formats, field meanings or operational roles.

| Python / JSON                                   | Reason                                                                                    |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `WaterHeight` / `water_height`                  | Gauge height and datum differ from altitude; “height” alone hides the measured quantity.  |
| `ReplyAck` / `reply_ack`                        | Embedded reply-ack IDs differ from a full `Acknowledgment` payload.                       |
| `NTSHeader` / `nts_header`                      | Radiogram header differs from the TNC2 `Header`.                                          |
| `NMEAMetadata` / `nmea_metadata`                | NMEA talker/checksum evidence differs from packet/header metadata.                        |
| `DecodeOptions` / `decode_options`              | Parsing policy differs from encoding policy.                                              |
| `EncodeOptions` / `encode_options`              | Construction policy differs from decoding policy.                                         |
| `HeaderSemantics` / `header_semantics`          | Interpreted destination/q-construct meaning differs from literal `Header`.                |
| `MicE` / `mic_e`                                | Established Mic-E protocol name, not two independently removable words.                   |
| `AutoAnswer` / `auto_answer`                    | Established automatic-answer message subtype.                                             |
| `NWSBulletin` / `nws_bulletin`                  | NWS product envelope differs from an ordinary `Bulletin`.                                 |
| `DirectStations` / `direct_stations`            | Explicitly reports directly heard stations, not arbitrary station lists.                  |
| `HeardStation` / `heard_station`                | Heard-response counts differ from a generic station identity.                             |
| `ThirdParty` / `third_party`                    | Established encapsulation protocol term.                                                  |
| `UserDefined` / `user_defined`                  | Established user-ID/type/data protocol envelope.                                          |
| `RawWeather` / `raw_weather`                    | Vendor bytes and optional interpretation differ from structured `Weather`.                |
| `LegacyPosition` / `legacy_position`            | Historical prefix/position wrapper differs from `Position`.                               |
| `ExternalExtension` / `external_extension`      | External/vendor grammar and source evidence differ from standard `Extensions`.            |
| `EncodedPacketFields` / `encoded_packet_fields` | Joint header/information encoding result differs from semantic `Packet` or a radio frame. |
