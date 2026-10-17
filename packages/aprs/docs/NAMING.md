# Public naming audit

Version 0.0.1a5 simplifies the unreleased API. There are 82 serializable models
(previously 84), still covering 29 payload families. No draft compatibility
aliases or old JSON tags remain. The [JSON reference](JSON_FORMAT.md) gives the
canonical complete shapes. Only type names/tags change; attribute names such as
`wind_speed` stay descriptive.

## Shared weather and telemetry

`WeatherReport(weather, timestamp, comment)` and `Weather` are now one `Weather`
model, with measurements, optional timestamp and comment directly on it.
`Telemetry(data, comment)` and `TelemetryData` are now one `Telemetry`, with
channels, sequence, encoding/raw evidence and comment directly on it. Constructors
no longer take the redundant `weather` or `data` wrapper arguments. All fields
are preserved, including raw evidence and report comments.

Both models work as full payloads and as fixed nested fields. Standalone/payload
JSON requires `type: weather` or `type: telemetry`; fixed nested fields omit the
tag because their declared class supplies context. This does not grant new wire
support: weather and telemetry encoding/decoding remain unimplemented.

## Python names

| Before                    | After             |
| ------------------------- | ----------------- |
| `CellBounds`              | `Extent`          |
| `GridLocator`             | `Grid`            |
| `RadioRange`              | `Range`           |
| `DFSignal`                | `Signal`          |
| `DFBearing`               | `Bearing`         |
| `TelemetryData`           | `Telemetry`       |
| `TelemetryParameters`     | `Parameters`      |
| `TelemetryUnits`          | `Units`           |
| `TelemetryEquations`      | `Equations`       |
| `TelemetryBits`           | `Bits`            |
| `NTSAddress`              | `Address`         |
| `NTSPhone`                | `Phone`           |
| `NTSText`                 | `Text`            |
| `NTSSignature`            | `Signature`       |
| `NTSRouting`              | `Routing`         |
| `QueryFootprint`          | `Footprint`       |
| `CapabilityToken`         | `Capability`      |
| `PathHop`                 | `Hop`             |
| `ObjectReport`            | `Object`          |
| `ItemReport`              | `Item`            |
| `WeatherReport`           | `Weather`         |
| `TelemetryDefinition`     | `Definition`      |
| `NTSMessage`              | `Radiogram`       |
| `TraceRoute`              | `Trace`           |
| `QueryResponse`           | `Response`        |
| `NMEAReport`              | `NMEA`            |
| `MaidenheadBeacon`        | `Maidenhead`      |
| `NonAPRSBeacon`           | `Beacon`          |
| `InvalidTest`             | `Invalid`         |
| `TelemetryDefinitionData` | `DefinitionValue` |
| `QueryResponseData`       | `ResponseValue`   |

`Weather` and `Telemetry` also retain their existing names while absorbing the
other model's fields. `DefinitionValue` and `ResponseValue` remain named unions,
not instantiable models or JSON tags. `Radiogram` represents one NTS message
record and its delivery envelope, not a guarantee of an assembled radiogram.
`Extent` is a latitude/longitude cell's bounds; `Bounds` remains the two-number
axis interval alias. `Capability` is a protocol capability token, distinct from
runtime `CodecCapability`. `Range` is radio range; `Grid` is a grid locator.

## JSON tags

| Before                 | After        |
| ---------------------- | ------------ |
| `cell_bounds`          | `extent`     |
| `grid_locator`         | `grid`       |
| `radio_range`          | `range`      |
| `df_signal`            | `signal`     |
| `df_bearing`           | `bearing`    |
| `weather_fields`       | `weather`    |
| `telemetry_data`       | `telemetry`  |
| `telemetry_parameters` | `parameters` |
| `telemetry_units`      | `units`      |
| `telemetry_equations`  | `equations`  |
| `telemetry_bits`       | `bits`       |
| `nts_address`          | `address`    |
| `nts_phone`            | `phone`      |
| `nts_text`             | `text`       |
| `nts_signature`        | `signature`  |
| `nts_routing`          | `routing`    |
| `query_footprint`      | `footprint`  |
| `capability_token`     | `capability` |
| `path_hop`             | `hop`        |
| `telemetry_definition` | `definition` |
| `nts_message`          | `radiogram`  |
| `trace_route`          | `trace`      |
| `query_response`       | `response`   |
| `maidenhead_beacon`    | `maidenhead` |
| `non_aprs_beacon`      | `beacon`     |
| `invalid_test`         | `invalid`    |

Existing `weather` and `telemetry` payload tags now identify the merged models;
telemetry's channels move from `data` to direct fields. Tags already short, such
as `object`, `item` and `nmea`, stay unchanged while Python adopts matching names.

## Retained qualifiers

These names carry distinctions that would be lost by dropping a word. Unchanged
single-word names and protocol acronyms are not renamed just for uniformity.
Public policy aliases such as `ValidationProfile`, `TimestampKind` and
`TelemetryEncoding` retain their subject so their values are understandable
outside a field annotation. Wire-codec errors/options and runtime capability
metadata likewise keep their operational role.

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

No new codecs or transmissions are introduced. The naming changes preserve
bytes, default/null distinctions, strict validation, nested packets, and explicit
unsupported-codec behavior.
