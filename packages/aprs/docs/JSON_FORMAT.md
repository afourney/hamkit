# APRS JSON reference

This is the canonical JSON format for `hamkit-aprs` 0.0.1a4. Examples are
pretty-printed, executable data, with nested values expanded. They illustrate
values, not legal ranges or complete APRS wire support. The field tables are the
shape contract: every field, requiredness, default, allowed enum, unit and nested
model is listed. All 84 serializable models and all 29 payload families appear.

## Contents

- [Reading and writing](#reading-and-writing)
- [Tags and context](#tags-and-context)
- [Values, defaults and constraints](#values-defaults-and-constraints)
- [Type map and object catalog](#type-map-and-object-catalog)
- [Nested union examples](#nested-union-examples)
- [Complete weather packet](#complete-weather-packet)
- [Regeneration and validation](#regeneration-and-validation)

## Reading and writing

`to_json(model, indent=2)` returns text. `to_json_dict(model)` returns a JSON-safe
dictionary. `from_json(text)` and `from_json_dict(mapping)` return typed models.
Use `expected_type=WeatherReport` to check a particular class; typed overloads
preserve the concrete return annotation. This does not waive payload tags.
`include_defaults=True` prints all fields, as in this catalog. The normal compact
output omits default-valued optional fields, but always retains `type` where
required. Object property order is not meaningful.

## Tags and context

- Every standalone object has a lowercase semantic `type`, including `packet`,
  `measurement`, and `header`. Tags are explicitly registered protocol-independent
  names; Python class names cannot be loaded dynamically.
- Every payload requires its own `type`, whether standalone, in `Packet.payload`,
  or in a fixed payload field such as `LegacyPosition.position`.
- Nested unions of multiple model classes require a tag: telemetry definitions,
  NMEA sentences, NTS records and query responses. The tags allowed at each union
  are exactly those of its linked models in the tables below.
- Fixed nested models are emitted without tags: a measurement's containing field
  already specifies `Measurement`; a header field specifies `Header`. Optional
  fixed models remain untagged when present. Arrays follow the same rule for
  their declared element type. Scalar unions use strict JSON value types.
- An untagged standalone fixed field may be read only with explicit
  `expected_type=Measurement` (or another concrete non-payload class). A supplied
  tag must always agree with that class. There is no structural inference.
- `WeatherReport` is flattened: measurements, software/device codes and raw
  weather evidence sit alongside `"type": "weather"`, timestamp and comment.
  There is no `weather` wrapper. Python still uses `WeatherReport.weather`.
  A standalone `Weather` field has tag `weather_fields`; nested `Weather` fields
  elsewhere are ordinary fixed objects. An empty weather payload is
  `{"type":"weather"}`.
- Third-party payloads contain `packet`, whose fixed Packet object is untagged;
  the inner `payload` has its own tag. See [ThirdParty](#thirdparty).
- Older untagged inferred shapes and ambiguity-driven field aliases are not
  accepted. JSON field names now match Python attributes except weather flattening.

## Values, defaults and constraints

- `bytes` are Latin-1 JSON strings: each U+0000–U+00FF code point represents one
  byte. JSON escapes such as `\u0000` and `\u00ff` preserve arbitrary binary data;
  this is not base64 and does not decode bytes as UTF-8. `to_json` emits ASCII-safe
  escapes. Ordinary string fields may contain Unicode outside Latin-1.
- Tuples become arrays. Fixed tuples require the exact length in the table;
  variadic tuples may be empty. Numbers are finite, booleans are not integers,
  numeric strings are not numbers, and enums match exactly, including case.
- Missing optional fields receive the listed Python defaults. Explicit null is
  accepted only where the type allows null. The model does not remember whether
  optional `None` came from omission or explicit null. Missing required fields
  fail, even when their type permits null.
- An absent weather measurement (`null` or omitted) differs from a present
  measurement with `value: null` (unavailable reading), and both differ from zero.
- Unit strings are the exhaustive `Measurement.unit` enum below. Units are
  explicit; conversion performs no unit conversion. Use semantically appropriate
  units for the weather quantity (e.g. degrees, mph, fahrenheit and hPa).
- `original_wire`, raw fields and diagnostic metadata are preserved, including
  fields ignored by dataclass equality. They do not override edited structured
  values. JSON conversion is a semantic round trip, not preservation of JSON
  whitespace, key order, omitted-null history or numeric spelling.
- Unknown fields, duplicate JSON keys, unknown/missing/incompatible tags and
  invalid scalar types raise `JSONModelError` (an `APRSError`/`ValueError`). There
  is no arbitrary class loading or fallback to a different family.
- This layer validates shape and annotated types, not all APRS numeric ranges,
  cross-field constraints or wire encodability. It neither guesses timestamps
  nor quantizes coordinates. Consult [wire coverage](API_COVERAGE.md).
  Weather JSON works even though weather wire encoding is unimplemented.
- `max_depth` defaults to 64 and accepts integers 1–128. Cycles and excessive
  nesting fail. This is not an input-size bound. `include_defaults` must be bool;
  `indent` is null or a nonnegative integer.

## Type map and object catalog

Tags in this table are exhaustive for standalone models. Payload tags are also
required at any nested payload boundary. Every example includes optional fields
and defaults so its complete shape is visible; null optional nested objects link
to their own fully expanded object examples in the field table.

| Model                                       | Stable type             | Role              |
| ------------------------------------------- | ----------------------- | ----------------- |
| [Measurement](#measurement)                 | `measurement`           | field / container |
| [Timestamp](#timestamp)                     | `timestamp`             | field / container |
| [Coordinates](#coordinates)                 | `coordinates`           | field / container |
| [CellBounds](#cellbounds)                   | `cell_bounds`           | field / container |
| [Ambiguity](#ambiguity)                     | `ambiguity`             | field / container |
| [Symbol](#symbol)                           | `symbol`                | field / container |
| [GridLocator](#gridlocator)                 | `grid_locator`          | field / container |
| [Motion](#motion)                           | `motion`                | field / container |
| [Altitude](#altitude)                       | `altitude`              | field / container |
| [RadioRange](#radiorange)                   | `radio_range`           | field / container |
| [PHG](#phg)                                 | `phg`                   | field / container |
| [DFSignal](#dfsignal)                       | `df_signal`             | field / container |
| [DFBearing](#dfbearing)                     | `df_bearing`            | field / container |
| [Compression](#compression)                 | `compression`           | field / container |
| [DAO](#dao)                                 | `dao`                   | field / container |
| [Area](#area)                               | `area`                  | field / container |
| [Signpost](#signpost)                       | `signpost`              | field / container |
| [WaterHeight](#waterheight)                 | `water_height`          | field / container |
| [Weather](#weather)                         | `weather_fields`        | field / container |
| [Storm](#storm)                             | `storm`                 | field / container |
| [TelemetryData](#telemetrydata)             | `telemetry_data`        | field / container |
| [Extensions](#extensions)                   | `extensions`            | field / container |
| [Location](#location)                       | `location`              | field / container |
| [Beam](#beam)                               | `beam`                  | field / container |
| [ReplyAck](#replyack)                       | `reply_ack`             | field / container |
| [TelemetryParameters](#telemetryparameters) | `telemetry_parameters`  | field / container |
| [TelemetryUnits](#telemetryunits)           | `telemetry_units`       | field / container |
| [Calibration](#calibration)                 | `calibration`           | field / container |
| [TelemetryEquations](#telemetryequations)   | `telemetry_equations`   | field / container |
| [TelemetryBits](#telemetrybits)             | `telemetry_bits`        | field / container |
| [NTSHeader](#ntsheader)                     | `nts_header`            | field / container |
| [NTSAddress](#ntsaddress)                   | `nts_address`           | field / container |
| [NTSPhone](#ntsphone)                       | `nts_phone`             | field / container |
| [NTSText](#ntstext)                         | `nts_text`              | field / container |
| [NTSSignature](#ntssignature)               | `nts_signature`         | field / container |
| [NTSRouting](#ntsrouting)                   | `nts_routing`           | field / container |
| [QueryFootprint](#queryfootprint)           | `query_footprint`       | field / container |
| [CapabilityToken](#capabilitytoken)         | `capability_token`      | field / container |
| [NMEAMetadata](#nmeametadata)               | `nmea_metadata`         | field / container |
| [GGA](#gga)                                 | `gga`                   | field / container |
| [GLL](#gll)                                 | `gll`                   | field / container |
| [RMC](#rmc)                                 | `rmc`                   | field / container |
| [VTG](#vtg)                                 | `vtg`                   | field / container |
| [WPL](#wpl)                                 | `wpl`                   | field / container |
| [DecodeOptions](#decodeoptions)             | `decode_options`        | field / container |
| [EncodeOptions](#encodeoptions)             | `encode_options`        | field / container |
| [PathHop](#pathhop)                         | `path_hop`              | field / container |
| [Header](#header)                           | `header`                | field / container |
| [HeaderSemantics](#headersemantics)         | `header_semantics`      | field / container |
| [Position](#position)                       | `position`              | payload           |
| [MicE](#mice)                               | `mic_e`                 | payload           |
| [ObjectReport](#objectreport)               | `object`                | payload           |
| [ItemReport](#itemreport)                   | `item`                  | payload           |
| [WeatherReport](#weatherreport)             | `weather`               | payload           |
| [Telemetry](#telemetry)                     | `telemetry`             | payload           |
| [TelemetryDefinition](#telemetrydefinition) | `telemetry_definition`  | payload           |
| [Status](#status)                           | `status`                | payload           |
| [Message](#message)                         | `message`               | payload           |
| [Acknowledgment](#acknowledgment)           | `acknowledgment`        | payload           |
| [AutoAnswer](#autoanswer)                   | `auto_answer`           | payload           |
| [Bulletin](#bulletin)                       | `bulletin`              | payload           |
| [NWSBulletin](#nwsbulletin)                 | `nws_bulletin`          | payload           |
| [NTSMessage](#ntsmessage)                   | `nts_message`           | payload           |
| [Query](#query)                             | `query`                 | payload           |
| [DirectStations](#directstations)           | `direct_stations`       | field / container |
| [HeardStation](#heardstation)               | `heard_station`         | field / container |
| [TraceRoute](#traceroute)                   | `trace_route`           | field / container |
| [QueryResponse](#queryresponse)             | `query_response`        | payload           |
| [Capabilities](#capabilities)               | `capabilities`          | payload           |
| [NMEAReport](#nmeareport)                   | `nmea`                  | payload           |
| [ThirdParty](#thirdparty)                   | `third_party`           | payload           |
| [UserDefined](#userdefined)                 | `user_defined`          | payload           |
| [RawWeather](#rawweather)                   | `raw_weather`           | payload           |
| [Agrelo](#agrelo)                           | `agrelo`                | payload           |
| [MaidenheadBeacon](#maidenheadbeacon)       | `maidenhead_beacon`     | payload           |
| [LegacyPosition](#legacyposition)           | `legacy_position`       | payload           |
| [NonAPRSBeacon](#nonaprsbeacon)             | `non_aprs_beacon`       | payload           |
| [InvalidTest](#invalidtest)                 | `invalid_test`          | payload           |
| [Reserved](#reserved)                       | `reserved`              | payload           |
| [ExternalExtension](#externalextension)     | `external_extension`    | payload           |
| [Diagnostic](#diagnostic)                   | `diagnostic`            | field / container |
| [Opaque](#opaque)                           | `opaque`                | payload           |
| [Packet](#packet)                           | `packet`                | field / container |
| [EncodedPacketFields](#encodedpacketfields) | `encoded_packet_fields` | field / container |

### Measurement

Standalone tag: `measurement`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "measurement",
  "value": null,
  "unit": "mph",
  "raw": "..."
}
```

| Field   | JSON value / allowed values                                                                                                                                                                                                                                                      | Presence / default                      |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `type`  | `"measurement"`                                                                                                                                                                                                                                                                  | required standalone; nested rules above |
| `value` | finite number or null                                                                                                                                                                                                                                                            | **required**                            |
| `unit`  | `'degrees'`, `'knots'`, `'mph'`, `'m/s'`, `'km/h'`, `'feet'`, `'meters'`, `'miles'`, `'nautical_miles'`, `'fahrenheit'`, `'celsius'`, `'percent'`, `'hPa'`, `'inches'`, `'mm'`, `'W/m2'`, `'watts'`, `'dBi'`, `'dB'`, `'S_units'`, `'count'`, `'raw'`, `'disputed_knots_or_mph'` | **required**                            |
| `raw`   | Latin-1 byte string or null                                                                                                                                                                                                                                                      | optional; default `null`                |

### Timestamp

Standalone tag: `timestamp`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "timestamp",
  "kind": "mdhm_utc",
  "hour": 12,
  "minute": 30,
  "day": 17,
  "second": null,
  "month": 10,
  "raw": null
}
```

| Field    | JSON value / allowed values                           | Presence / default                      |
| -------- | ----------------------------------------------------- | --------------------------------------- |
| `type`   | `"timestamp"`                                         | required standalone; nested rules above |
| `kind`   | `'dhm_utc'`, `'dhm_local'`, `'hms_utc'`, `'mdhm_utc'` | **required**                            |
| `hour`   | integer                                               | **required**                            |
| `minute` | integer                                               | **required**                            |
| `day`    | integer or null                                       | optional; default `null`                |
| `second` | integer or null                                       | optional; default `null`                |
| `month`  | integer or null                                       | optional; default `null`                |
| `raw`    | Latin-1 byte string or null                           | optional; default `null`                |

### Coordinates

Standalone tag: `coordinates`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "coordinates",
  "latitude_deg": 49,
  "longitude_deg": -72
}
```

| Field           | JSON value / allowed values | Presence / default                      |
| --------------- | --------------------------- | --------------------------------------- |
| `type`          | `"coordinates"`             | required standalone; nested rules above |
| `latitude_deg`  | finite number               | **required**                            |
| `longitude_deg` | finite number               | **required**                            |

### CellBounds

Standalone tag: `cell_bounds`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "cell_bounds",
  "latitude": [49, 50],
  "longitude": [-73, -72]
}
```

| Field       | JSON value / allowed values                            | Presence / default                      |
| ----------- | ------------------------------------------------------ | --------------------------------------- |
| `type`      | `"cell_bounds"`                                        | required standalone; nested rules above |
| `latitude`  | array of exactly 2 items: finite number, finite number | **required**                            |
| `longitude` | array of exactly 2 items: finite number, finite number | **required**                            |

### Ambiguity

Standalone tag: `ambiguity`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "ambiguity",
  "digits": 4,
  "cell_bounds": {
    "latitude": [49, 50],
    "longitude": [-73, -72]
  },
  "representative": "center"
}
```

| Field            | JSON value / allowed values       | Presence / default                      |
| ---------------- | --------------------------------- | --------------------------------------- |
| `type`           | `"ambiguity"`                     | required standalone; nested rules above |
| `digits`         | integer                           | **required**                            |
| `cell_bounds`    | [CellBounds](#cellbounds) or null | optional; default `null`                |
| `representative` | `'center'`                        | optional; default `'center'`            |

### Symbol

Standalone tag: `symbol`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "symbol",
  "table_id": "a",
  "code": ">"
}
```

| Field      | JSON value / allowed values | Presence / default                      |
| ---------- | --------------------------- | --------------------------------------- |
| `type`     | `"symbol"`                  | required standalone; nested rules above |
| `table_id` | string                      | optional; default `'/'`                 |
| `code`     | string                      | optional; default `'-'`                 |

### GridLocator

Standalone tag: `grid_locator`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "grid_locator",
  "locator": "IO91SX",
  "bounds": {
    "latitude": [49, 50],
    "longitude": [-73, -72]
  },
  "center": {
    "latitude_deg": 49,
    "longitude_deg": -72
  }
}
```

| Field     | JSON value / allowed values         | Presence / default                      |
| --------- | ----------------------------------- | --------------------------------------- |
| `type`    | `"grid_locator"`                    | required standalone; nested rules above |
| `locator` | string                              | **required**                            |
| `bounds`  | [CellBounds](#cellbounds) or null   | optional; default `null`                |
| `center`  | [Coordinates](#coordinates) or null | optional; default `null`                |

### Motion

Standalone tag: `motion`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "motion",
  "course_deg": 360,
  "speed_knots": 12,
  "course_code": 360,
  "speed_code": 12,
  "raw": "360/012",
  "zero_pair": "unspecified"
}
```

| Field         | JSON value / allowed values                               | Presence / default                      |
| ------------- | --------------------------------------------------------- | --------------------------------------- |
| `type`        | `"motion"`                                                | required standalone; nested rules above |
| `course_deg`  | finite number or null                                     | optional; default `null`                |
| `speed_knots` | finite number or null                                     | optional; default `null`                |
| `course_code` | integer or null                                           | optional; default `null`                |
| `speed_code`  | integer or null                                           | optional; default `null`                |
| `raw`         | Latin-1 byte string or null                               | optional; default `null`                |
| `zero_pair`   | `'unavailable'`, `'fixed'`, `'measured'`, `'unspecified'` | optional; default `'unspecified'`       |

### Altitude

Standalone tag: `altitude`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "altitude",
  "measurement": {
    "value": 123,
    "unit": "meters",
    "raw": null
  },
  "encoding": "mic_e",
  "reference": "unspecified"
}
```

| Field         | JSON value / allowed values                             | Presence / default                      |
| ------------- | ------------------------------------------------------- | --------------------------------------- |
| `type`        | `"altitude"`                                            | required standalone; nested rules above |
| `measurement` | [Measurement](#measurement)                             | **required**                            |
| `encoding`    | `'feet_extension'`, `'compressed'`, `'mic_e'`, `'nmea'` | **required**                            |
| `reference`   | `'unspecified'`, `'MSL'`, `'ellipsoid'`                 | optional; default `'unspecified'`       |

### RadioRange

Standalone tag: `radio_range`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "radio_range",
  "miles": 12,
  "raw": null
}
```

| Field   | JSON value / allowed values | Presence / default                      |
| ------- | --------------------------- | --------------------------------------- |
| `type`  | `"radio_range"`             | required standalone; nested rules above |
| `miles` | finite number               | **required**                            |
| `raw`   | Latin-1 byte string or null | optional; default `null`                |

### PHG

Standalone tag: `phg`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "phg",
  "power_w": 25,
  "height_haat_ft": 80,
  "gain_dbi": 3,
  "directivity_deg": null,
  "raw": null,
  "range_miles_1_0": null,
  "display_radius_miles_1_1": null,
  "rate_per_hour": null
}
```

| Field                      | JSON value / allowed values | Presence / default                      |
| -------------------------- | --------------------------- | --------------------------------------- |
| `type`                     | `"phg"`                     | required standalone; nested rules above |
| `power_w`                  | finite number               | **required**                            |
| `height_haat_ft`           | finite number               | **required**                            |
| `gain_dbi`                 | finite number               | **required**                            |
| `directivity_deg`          | finite number or null       | optional; default `null`                |
| `raw`                      | Latin-1 byte string or null | optional; default `null`                |
| `range_miles_1_0`          | finite number or null       | optional; default `null`                |
| `display_radius_miles_1_1` | finite number or null       | optional; default `null`                |
| `rate_per_hour`            | integer or null             | optional; default `null`                |

### DFSignal

Standalone tag: `df_signal`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "df_signal",
  "s_units": 5,
  "height_haat_ft": 80,
  "gain_db": 3,
  "directivity_deg": null,
  "raw": null
}
```

| Field             | JSON value / allowed values | Presence / default                      |
| ----------------- | --------------------------- | --------------------------------------- |
| `type`            | `"df_signal"`               | required standalone; nested rules above |
| `s_units`         | integer                     | **required**                            |
| `height_haat_ft`  | finite number               | **required**                            |
| `gain_db`         | finite number               | **required**                            |
| `directivity_deg` | finite number or null       | optional; default `null`                |
| `raw`             | Latin-1 byte string or null | optional; default `null`                |

### DFBearing

Standalone tag: `df_bearing`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "df_bearing",
  "bearing_deg": 120,
  "hits_code": 3,
  "range_code": 2,
  "quality_code": 7,
  "manual": false,
  "usable": null,
  "range_miles": null,
  "accuracy_less_than_deg": null,
  "raw": null
}
```

| Field                    | JSON value / allowed values | Presence / default                      |
| ------------------------ | --------------------------- | --------------------------------------- |
| `type`                   | `"df_bearing"`              | required standalone; nested rules above |
| `bearing_deg`            | finite number               | **required**                            |
| `hits_code`              | integer                     | **required**                            |
| `range_code`             | integer                     | **required**                            |
| `quality_code`           | integer                     | **required**                            |
| `manual`                 | boolean                     | optional; default `false`               |
| `usable`                 | boolean or null             | optional; default `null`                |
| `range_miles`            | finite number or null       | optional; default `null`                |
| `accuracy_less_than_deg` | finite number or null       | optional; default `null`                |
| `raw`                    | Latin-1 byte string or null | optional; default `null`                |

### Compression

Standalone tag: `compression`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "compression",
  "type_value": 0,
  "fix": "old",
  "nmea_source": "other",
  "origin_code": 0,
  "csT_raw": null,
  "ignored": false
}
```

| Field         | JSON value / allowed values          | Presence / default                      |
| ------------- | ------------------------------------ | --------------------------------------- |
| `type`        | `"compression"`                      | required standalone; nested rules above |
| `type_value`  | integer                              | **required**                            |
| `fix`         | `'old'`, `'current'`                 | **required**                            |
| `nmea_source` | `'other'`, `'GLL'`, `'GGA'`, `'RMC'` | **required**                            |
| `origin_code` | integer                              | **required**                            |
| `csT_raw`     | Latin-1 byte string or null          | optional; default `null`                |
| `ignored`     | boolean                              | optional; default `false`               |

### DAO

Standalone tag: `dao`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "dao",
  "datum_byte": "W",
  "latitude_precision": 1,
  "longitude_precision": 2,
  "encoding": "decimal",
  "raw": null
}
```

| Field                 | JSON value / allowed values | Presence / default                      |
| --------------------- | --------------------------- | --------------------------------------- |
| `type`                | `"dao"`                     | required standalone; nested rules above |
| `datum_byte`          | string                      | **required**                            |
| `latitude_precision`  | integer                     | **required**                            |
| `longitude_precision` | integer                     | **required**                            |
| `encoding`            | `'decimal'`, `'base91'`     | **required**                            |
| `raw`                 | Latin-1 byte string or null | optional; default `null`                |

### Area

Standalone tag: `area`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "area",
  "shape_code": 0,
  "color_code": 3,
  "latitude_offset_code": 10,
  "longitude_offset_code": 10,
  "corridor_half_width_miles": null,
  "latitude_offset_deg": null,
  "longitude_offset_deg": null,
  "transmitted_anchor": "lower_reference"
}
```

| Field                       | JSON value / allowed values            | Presence / default                      |
| --------------------------- | -------------------------------------- | --------------------------------------- |
| `type`                      | `"area"`                               | required standalone; nested rules above |
| `shape_code`                | integer                                | **required**                            |
| `color_code`                | integer                                | **required**                            |
| `latitude_offset_code`      | integer                                | **required**                            |
| `longitude_offset_code`     | integer                                | **required**                            |
| `corridor_half_width_miles` | finite number or null                  | optional; default `null`                |
| `latitude_offset_deg`       | finite number or null                  | optional; default `null`                |
| `longitude_offset_deg`      | finite number or null                  | optional; default `null`                |
| `transmitted_anchor`        | `'lower_reference'`, `'circle_center'` | optional; default `'lower_reference'`   |

### Signpost

Standalone tag: `signpost`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "signpost",
  "label": "55"
}
```

| Field   | JSON value / allowed values | Presence / default                      |
| ------- | --------------------------- | --------------------------------------- |
| `type`  | `"signpost"`                | required standalone; nested rules above |
| `label` | Latin-1 byte string         | **required**                            |

### WaterHeight

Standalone tag: `water_height`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "water_height",
  "measurement": {
    "value": 20.1,
    "unit": "feet",
    "raw": null
  },
  "reference_datum": null
}
```

| Field             | JSON value / allowed values | Presence / default                      |
| ----------------- | --------------------------- | --------------------------------------- |
| `type`            | `"water_height"`            | required standalone; nested rules above |
| `measurement`     | [Measurement](#measurement) | **required**                            |
| `reference_datum` | string or null              | optional; default `null`                |

### Weather

Standalone tag: `weather_fields`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "weather_fields",
  "wind_direction": null,
  "wind_speed": {
    "value": null,
    "unit": "mph",
    "raw": "..."
  },
  "gust": null,
  "temperature": null,
  "humidity": {
    "value": 100,
    "unit": "percent",
    "raw": "00"
  },
  "pressure": null,
  "rain_1h": null,
  "rain_24h": null,
  "rain_since_midnight": null,
  "snow_24h": null,
  "luminosity": null,
  "rain_counter": null,
  "water_height": null,
  "software_code": null,
  "device_code": null,
  "raw": null
}
```

| Field                 | JSON value / allowed values         | Presence / default                      |
| --------------------- | ----------------------------------- | --------------------------------------- |
| `type`                | `"weather_fields"`                  | required standalone; nested rules above |
| `wind_direction`      | [Measurement](#measurement) or null | optional; default `null`                |
| `wind_speed`          | [Measurement](#measurement) or null | optional; default `null`                |
| `gust`                | [Measurement](#measurement) or null | optional; default `null`                |
| `temperature`         | [Measurement](#measurement) or null | optional; default `null`                |
| `humidity`            | [Measurement](#measurement) or null | optional; default `null`                |
| `pressure`            | [Measurement](#measurement) or null | optional; default `null`                |
| `rain_1h`             | [Measurement](#measurement) or null | optional; default `null`                |
| `rain_24h`            | [Measurement](#measurement) or null | optional; default `null`                |
| `rain_since_midnight` | [Measurement](#measurement) or null | optional; default `null`                |
| `snow_24h`            | [Measurement](#measurement) or null | optional; default `null`                |
| `luminosity`          | [Measurement](#measurement) or null | optional; default `null`                |
| `rain_counter`        | [Measurement](#measurement) or null | optional; default `null`                |
| `water_height`        | [WaterHeight](#waterheight) or null | optional; default `null`                |
| `software_code`       | Latin-1 byte string or null         | optional; default `null`                |
| `device_code`         | Latin-1 byte string or null         | optional; default `null`                |
| `raw`                 | Latin-1 byte string or null         | optional; default `null`                |

### Storm

Standalone tag: `storm`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "storm",
  "kind": "HC",
  "predicted": false,
  "sustained_wind_knots": 80,
  "peak_gust_knots": 100,
  "central_pressure_hpa": 990,
  "hurricane_radius_nm": 20,
  "tropical_storm_radius_nm": 50,
  "whole_gale_radius_nm": null,
  "raw": null
}
```

| Field                      | JSON value / allowed values | Presence / default                      |
| -------------------------- | --------------------------- | --------------------------------------- |
| `type`                     | `"storm"`                   | required standalone; nested rules above |
| `kind`                     | `'HC'`, `'TS'`, `'TD'`      | **required**                            |
| `predicted`                | boolean                     | **required**                            |
| `sustained_wind_knots`     | finite number               | **required**                            |
| `peak_gust_knots`          | finite number               | **required**                            |
| `central_pressure_hpa`     | finite number               | **required**                            |
| `hurricane_radius_nm`      | finite number               | **required**                            |
| `tropical_storm_radius_nm` | finite number               | **required**                            |
| `whole_gale_radius_nm`     | finite number or null       | optional; default `null`                |
| `raw`                      | Latin-1 byte string or null | optional; default `null`                |

### TelemetryData

Standalone tag: `telemetry_data`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "telemetry_data",
  "analog": [1, null, 3],
  "digital": [true, null],
  "sequence": "MIC",
  "encoding": "mic_e_hex",
  "sequence_raw": null,
  "raw": null,
  "mic_comma": true
}
```

| Field          | JSON value / allowed values                                                         | Presence / default                      |
| -------------- | ----------------------------------------------------------------------------------- | --------------------------------------- |
| `type`         | `"telemetry_data"`                                                                  | required standalone; nested rules above |
| `analog`       | array of finite number or null                                                      | optional; default `[]`                  |
| `digital`      | array of boolean or null                                                            | optional; default `[]`                  |
| `sequence`     | integer or `'MIC'` or null                                                          | optional; default `null`                |
| `encoding`     | `'classic'`, `'mic_e_hex'`, `'mic_e_binary'`, `'base91_comment'`, `'compatibility'` | optional; default `'classic'`           |
| `sequence_raw` | Latin-1 byte string or null                                                         | optional; default `null`                |
| `raw`          | Latin-1 byte string or null                                                         | optional; default `null`                |
| `mic_comma`    | boolean                                                                             | optional; default `true`                |

### Extensions

Standalone tag: `extensions`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "extensions",
  "motion": null,
  "altitude": null,
  "phg": null,
  "radio_range": null,
  "df_signal": null,
  "df_bearing": null,
  "dao": null,
  "area": null,
  "signpost": null,
  "weather": {
    "wind_direction": null,
    "wind_speed": null,
    "gust": null,
    "temperature": {
      "value": 32,
      "unit": "fahrenheit",
      "raw": null
    },
    "humidity": null,
    "pressure": null,
    "rain_1h": null,
    "rain_24h": null,
    "rain_since_midnight": null,
    "snow_24h": null,
    "luminosity": null,
    "rain_counter": null,
    "water_height": null,
    "software_code": null,
    "device_code": null,
    "raw": null
  },
  "storm": null,
  "telemetry": null
}
```

| Field         | JSON value / allowed values             | Presence / default                      |
| ------------- | --------------------------------------- | --------------------------------------- |
| `type`        | `"extensions"`                          | required standalone; nested rules above |
| `motion`      | [Motion](#motion) or null               | optional; default `null`                |
| `altitude`    | [Altitude](#altitude) or null           | optional; default `null`                |
| `phg`         | [PHG](#phg) or null                     | optional; default `null`                |
| `radio_range` | [RadioRange](#radiorange) or null       | optional; default `null`                |
| `df_signal`   | [DFSignal](#dfsignal) or null           | optional; default `null`                |
| `df_bearing`  | [DFBearing](#dfbearing) or null         | optional; default `null`                |
| `dao`         | [DAO](#dao) or null                     | optional; default `null`                |
| `area`        | [Area](#area) or null                   | optional; default `null`                |
| `signpost`    | [Signpost](#signpost) or null           | optional; default `null`                |
| `weather`     | [Weather](#weather) or null             | optional; default `null`                |
| `storm`       | [Storm](#storm) or null                 | optional; default `null`                |
| `telemetry`   | [TelemetryData](#telemetrydata) or null | optional; default `null`                |

### Location

Standalone tag: `location`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "location",
  "latitude_deg": 49,
  "longitude_deg": -72,
  "symbol": {
    "table_id": "/",
    "code": "-"
  },
  "ambiguity": null,
  "extensions": {
    "motion": null,
    "altitude": null,
    "phg": null,
    "radio_range": null,
    "df_signal": null,
    "df_bearing": null,
    "dao": null,
    "area": null,
    "signpost": null,
    "weather": null,
    "storm": null,
    "telemetry": null
  },
  "tail": "",
  "comment": ""
}
```

| Field           | JSON value / allowed values     | Presence / default                                            |
| --------------- | ------------------------------- | ------------------------------------------------------------- |
| `type`          | `"location"`                    | required standalone; nested rules above                       |
| `latitude_deg`  | finite number                   | **required**                                                  |
| `longitude_deg` | finite number                   | **required**                                                  |
| `symbol`        | [Symbol](#symbol)               | optional; default [Symbol](#symbol) with its defaults         |
| `ambiguity`     | [Ambiguity](#ambiguity) or null | optional; default `null`                                      |
| `extensions`    | [Extensions](#extensions)       | optional; default [Extensions](#extensions) with its defaults |
| `tail`          | Latin-1 byte string             | optional; default `""`                                        |
| `comment`       | Latin-1 byte string             | optional; default `""`                                        |

### Beam

Standalone tag: `beam`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "beam",
  "heading_deg": 90,
  "erp_w": 100,
  "raw": null
}
```

| Field         | JSON value / allowed values | Presence / default                      |
| ------------- | --------------------------- | --------------------------------------- |
| `type`        | `"beam"`                    | required standalone; nested rules above |
| `heading_deg` | finite number               | **required**                            |
| `erp_w`       | finite number               | **required**                            |
| `raw`         | Latin-1 byte string or null | optional; default `null`                |

### ReplyAck

Standalone tag: `reply_ack`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "reply_ack",
  "message_number": "01",
  "previous_ack": "02"
}
```

| Field            | JSON value / allowed values | Presence / default                      |
| ---------------- | --------------------------- | --------------------------------------- |
| `type`           | `"reply_ack"`               | required standalone; nested rules above |
| `message_number` | string                      | **required**                            |
| `previous_ack`   | string or null              | optional; default `null`                |

### TelemetryParameters

Standalone tag: `telemetry_parameters`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "telemetry_parameters",
  "channels": ["Temperature", null, "Voltage"]
}
```

| Field      | JSON value / allowed values | Presence / default                      |
| ---------- | --------------------------- | --------------------------------------- |
| `type`     | `"telemetry_parameters"`    | required standalone; nested rules above |
| `channels` | array of string or null     | **required**                            |

### TelemetryUnits

Standalone tag: `telemetry_units`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "telemetry_units",
  "channels": ["deg.C", null, "V"]
}
```

| Field      | JSON value / allowed values | Presence / default                      |
| ---------- | --------------------------- | --------------------------------------- |
| `type`     | `"telemetry_units"`         | required standalone; nested rules above |
| `channels` | array of string or null     | **required**                            |

### Calibration

Standalone tag: `calibration`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "calibration",
  "a": 0,
  "b": 1,
  "c": 0
}
```

| Field  | JSON value / allowed values | Presence / default                      |
| ------ | --------------------------- | --------------------------------------- |
| `type` | `"calibration"`             | required standalone; nested rules above |
| `a`    | finite number               | **required**                            |
| `b`    | finite number               | **required**                            |
| `c`    | finite number               | **required**                            |

### TelemetryEquations

Standalone tag: `telemetry_equations`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "telemetry_equations",
  "coefficients": [
    {
      "a": 0,
      "b": 1,
      "c": 0
    },
    null
  ]
}
```

| Field          | JSON value / allowed values                  | Presence / default                      |
| -------------- | -------------------------------------------- | --------------------------------------- |
| `type`         | `"telemetry_equations"`                      | required standalone; nested rules above |
| `coefficients` | array of [Calibration](#calibration) or null | **required**                            |

### TelemetryBits

Standalone tag: `telemetry_bits`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "telemetry_bits",
  "sense": [true, true, true, true, true, true, true, true],
  "project_title": "Project"
}
```

| Field           | JSON value / allowed values | Presence / default                      |
| --------------- | --------------------------- | --------------------------------------- |
| `type`          | `"telemetry_bits"`          | required standalone; nested rules above |
| `sense`         | array of boolean or null    | **required**                            |
| `project_title` | Latin-1 byte string         | optional; default `""`                  |

### NTSHeader

Standalone tag: `nts_header`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nts_header",
  "number": "12",
  "precedence": "R",
  "handling": "HXA",
  "originator": "N0CALL",
  "check": "5",
  "place": "REDMOND WA",
  "time": "1800",
  "date": "OCT 15"
}
```

| Field        | JSON value / allowed values | Presence / default                      |
| ------------ | --------------------------- | --------------------------------------- |
| `type`       | `"nts_header"`              | required standalone; nested rules above |
| `number`     | string                      | **required**                            |
| `precedence` | string                      | **required**                            |
| `handling`   | string                      | **required**                            |
| `originator` | string                      | **required**                            |
| `check`      | string                      | **required**                            |
| `place`      | string                      | **required**                            |
| `time`       | string                      | **required**                            |
| `date`       | string                      | **required**                            |

### NTSAddress

Standalone tag: `nts_address`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nts_address",
  "lines": ["ADAM", "123 MAIN ST", "REDMOND WA", "98052"]
}
```

| Field   | JSON value / allowed values                              | Presence / default                      |
| ------- | -------------------------------------------------------- | --------------------------------------- |
| `type`  | `"nts_address"`                                          | required standalone; nested rules above |
| `lines` | array of exactly 4 items: string, string, string, string | **required**                            |

### NTSPhone

Standalone tag: `nts_phone`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nts_phone",
  "number": "5550100"
}
```

| Field    | JSON value / allowed values | Presence / default                      |
| -------- | --------------------------- | --------------------------------------- |
| `type`   | `"nts_phone"`               | required standalone; nested rules above |
| `number` | string                      | **required**                            |

### NTSText

Standalone tag: `nts_text`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nts_text",
  "line": 1,
  "text": "Hello"
}
```

| Field  | JSON value / allowed values  | Presence / default                      |
| ------ | ---------------------------- | --------------------------------------- |
| `type` | `"nts_text"`                 | required standalone; nested rules above |
| `line` | `1`, `2`, `3`, `4`, `5`, `6` | **required**                            |
| `text` | Latin-1 byte string          | **required**                            |

### NTSSignature

Standalone tag: `nts_signature`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nts_signature",
  "text": "N0CALL"
}
```

| Field  | JSON value / allowed values | Presence / default                      |
| ------ | --------------------------- | --------------------------------------- |
| `type` | `"nts_signature"`           | required standalone; nested rules above |
| `text` | Latin-1 byte string         | **required**                            |

### NTSRouting

Standalone tag: `nts_routing`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nts_routing",
  "received_from": "W1AW",
  "received_at": "151800Z",
  "sent_to": "N0CALL",
  "sent_at": "151805Z"
}
```

| Field           | JSON value / allowed values | Presence / default                      |
| --------------- | --------------------------- | --------------------------------------- |
| `type`          | `"nts_routing"`             | required standalone; nested rules above |
| `received_from` | string                      | **required**                            |
| `received_at`   | string                      | **required**                            |
| `sent_to`       | string                      | **required**                            |
| `sent_at`       | string                      | **required**                            |

### QueryFootprint

Standalone tag: `query_footprint`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "query_footprint",
  "center": {
    "latitude_deg": 49,
    "longitude_deg": -72
  },
  "radius_miles": 20
}
```

| Field          | JSON value / allowed values | Presence / default                      |
| -------------- | --------------------------- | --------------------------------------- |
| `type`         | `"query_footprint"`         | required standalone; nested rules above |
| `center`       | [Coordinates](#coordinates) | **required**                            |
| `radius_miles` | finite number               | **required**                            |

### CapabilityToken

Standalone tag: `capability_token`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "capability_token",
  "name": "MSG_CNT",
  "value": "43"
}
```

| Field   | JSON value / allowed values | Presence / default                      |
| ------- | --------------------------- | --------------------------------------- |
| `type`  | `"capability_token"`        | required standalone; nested rules above |
| `name`  | string                      | **required**                            |
| `value` | Latin-1 byte string or null | optional; default `null`                |

### NMEAMetadata

Standalone tag: `nmea_metadata`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nmea_metadata",
  "talker": "GP",
  "checksum_supplied": "00",
  "checksum_valid": false,
  "fields_raw": []
}
```

| Field               | JSON value / allowed values  | Presence / default                      |
| ------------------- | ---------------------------- | --------------------------------------- |
| `type`              | `"nmea_metadata"`            | required standalone; nested rules above |
| `talker`            | string                       | optional; default `'GP'`                |
| `checksum_supplied` | string or null               | optional; default `null`                |
| `checksum_valid`    | boolean or null              | optional; default `null`                |
| `fields_raw`        | array of Latin-1 byte string | optional; default `[]`                  |

### GGA

Standalone tag: `gga`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "gga",
  "time_utc": "123000",
  "coordinates": {
    "latitude_deg": 49,
    "longitude_deg": -72
  },
  "fix_quality": 0,
  "satellites": null,
  "hdop": null,
  "altitude_msl_m": 12,
  "geoid_separation_m": 3,
  "dgps_age": null,
  "dgps_station": null
}
```

| Field                | JSON value / allowed values         | Presence / default                      |
| -------------------- | ----------------------------------- | --------------------------------------- |
| `type`               | `"gga"`                             | required standalone; nested rules above |
| `time_utc`           | Latin-1 byte string                 | **required**                            |
| `coordinates`        | [Coordinates](#coordinates) or null | **required**                            |
| `fix_quality`        | integer                             | **required**                            |
| `satellites`         | integer or null                     | optional; default `null`                |
| `hdop`               | finite number or null               | optional; default `null`                |
| `altitude_msl_m`     | finite number or null               | optional; default `null`                |
| `geoid_separation_m` | finite number or null               | optional; default `null`                |
| `dgps_age`           | Latin-1 byte string or null         | optional; default `null`                |
| `dgps_station`       | Latin-1 byte string or null         | optional; default `null`                |

### GLL

Standalone tag: `gll`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "gll",
  "coordinates": {
    "latitude_deg": 49,
    "longitude_deg": -72
  },
  "time_utc": "123000",
  "fix_status": "V"
}
```

| Field         | JSON value / allowed values         | Presence / default                      |
| ------------- | ----------------------------------- | --------------------------------------- |
| `type`        | `"gll"`                             | required standalone; nested rules above |
| `coordinates` | [Coordinates](#coordinates) or null | **required**                            |
| `time_utc`    | Latin-1 byte string                 | **required**                            |
| `fix_status`  | `'A'`, `'V'`                        | **required**                            |

### RMC

Standalone tag: `rmc`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "rmc",
  "time_utc": "123000",
  "date_ddmmyy": "171026",
  "fix_status": "A",
  "coordinates": {
    "latitude_deg": 49,
    "longitude_deg": -72
  },
  "speed_knots": 12,
  "course_deg": 90,
  "magnetic_variation": null,
  "magnetic_variation_direction": null
}
```

| Field                          | JSON value / allowed values         | Presence / default                      |
| ------------------------------ | ----------------------------------- | --------------------------------------- |
| `type`                         | `"rmc"`                             | required standalone; nested rules above |
| `time_utc`                     | Latin-1 byte string                 | **required**                            |
| `date_ddmmyy`                  | Latin-1 byte string                 | **required**                            |
| `fix_status`                   | `'A'`, `'V'`                        | **required**                            |
| `coordinates`                  | [Coordinates](#coordinates) or null | **required**                            |
| `speed_knots`                  | finite number or null               | optional; default `null`                |
| `course_deg`                   | finite number or null               | optional; default `null`                |
| `magnetic_variation`           | finite number or null               | optional; default `null`                |
| `magnetic_variation_direction` | `'E'`, `'W'` or null                | optional; default `null`                |

### VTG

Standalone tag: `vtg`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "vtg",
  "course_true_deg": 90,
  "course_magnetic_deg": 89,
  "speed_knots": 10,
  "speed_kmh_reported": 18.52
}
```

| Field                 | JSON value / allowed values | Presence / default                      |
| --------------------- | --------------------------- | --------------------------------------- |
| `type`                | `"vtg"`                     | required standalone; nested rules above |
| `course_true_deg`     | finite number or null       | optional; default `null`                |
| `course_magnetic_deg` | finite number or null       | optional; default `null`                |
| `speed_knots`         | finite number or null       | optional; default `null`                |
| `speed_kmh_reported`  | finite number or null       | optional; default `null`                |

### WPL

Standalone tag: `wpl`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "wpl",
  "coordinates": {
    "latitude_deg": 49,
    "longitude_deg": -72
  },
  "name": "HOME"
}
```

| Field         | JSON value / allowed values | Presence / default                      |
| ------------- | --------------------------- | --------------------------------------- |
| `type`        | `"wpl"`                     | required standalone; nested rules above |
| `coordinates` | [Coordinates](#coordinates) | **required**                            |
| `name`        | Latin-1 byte string         | **required**                            |

### DecodeOptions

Standalone tag: `decode_options`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "decode_options",
  "unsupported": "opaque",
  "malformed": "raise",
  "max_depth": 4,
  "specification": "core-1.1"
}
```

| Field           | JSON value / allowed values                             | Presence / default                      |
| --------------- | ------------------------------------------------------- | --------------------------------------- |
| `type`          | `"decode_options"`                                      | required standalone; nested rules above |
| `unsupported`   | `'opaque'`, `'raise'`                                   | optional; default `'opaque'`            |
| `malformed`     | `'raise'`, `'opaque'`                                   | optional; default `'raise'`             |
| `max_depth`     | integer                                                 | optional; default `4`                   |
| `specification` | `'core-1.1'`, `'historical-1.0'`, `'compatibility-fap'` | optional; default `'core-1.1'`          |

### EncodeOptions

Standalone tag: `encode_options`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "encode_options",
  "max_depth": 4,
  "specification": "core-1.1",
  "destination": "derive"
}
```

| Field           | JSON value / allowed values                             | Presence / default                      |
| --------------- | ------------------------------------------------------- | --------------------------------------- |
| `type`          | `"encode_options"`                                      | required standalone; nested rules above |
| `max_depth`     | integer                                                 | optional; default `4`                   |
| `specification` | `'core-1.1'`, `'historical-1.0'`, `'compatibility-fap'` | optional; default `'core-1.1'`          |
| `destination`   | `'derive'`, `'require_match'`                           | optional; default `'derive'`            |

### PathHop

Standalone tag: `path_hop`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "path_hop",
  "address": "WIDE1-1",
  "repeated": false
}
```

| Field      | JSON value / allowed values | Presence / default                      |
| ---------- | --------------------------- | --------------------------------------- |
| `type`     | `"path_hop"`                | required standalone; nested rules above |
| `address`  | string                      | **required**                            |
| `repeated` | boolean                     | optional; default `false`               |

### Header

Standalone tag: `header`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "header",
  "source": "N0CALL",
  "destination": "APRS",
  "path": []
}
```

| Field         | JSON value / allowed values  | Presence / default                      |
| ------------- | ---------------------------- | --------------------------------------- |
| `type`        | `"header"`                   | required standalone; nested rules above |
| `source`      | string                       | **required**                            |
| `destination` | string                       | **required**                            |
| `path`        | array of [PathHop](#pathhop) | optional; default `[]`                  |

### HeaderSemantics

Standalone tag: `header_semantics`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "header_semantics",
  "destination_grid": {
    "locator": "IO91SX",
    "bounds": {
      "latitude": [49, 50],
      "longitude": [-73, -72]
    },
    "center": {
      "latitude_deg": 49,
      "longitude_deg": -72
    }
  },
  "destination_symbol": null,
  "source_ssid_symbol": null,
  "destination_ssid_route": null,
  "software_identifier": null,
  "q_construct": null
}
```

| Field                    | JSON value / allowed values         | Presence / default                      |
| ------------------------ | ----------------------------------- | --------------------------------------- |
| `type`                   | `"header_semantics"`                | required standalone; nested rules above |
| `destination_grid`       | [GridLocator](#gridlocator) or null | optional; default `null`                |
| `destination_symbol`     | [Symbol](#symbol) or null           | optional; default `null`                |
| `source_ssid_symbol`     | [Symbol](#symbol) or null           | optional; default `null`                |
| `destination_ssid_route` | integer or null                     | optional; default `null`                |
| `software_identifier`    | string or null                      | optional; default `null`                |
| `q_construct`            | string or null                      | optional; default `null`                |

### Position

Standalone tag: `position`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "position",
  "latitude_deg": 49,
  "longitude_deg": -72,
  "symbol": {
    "table_id": "/",
    "code": "-"
  },
  "messaging": false,
  "timestamp": null,
  "tail": "",
  "encoding": "uncompressed",
  "ambiguity": null,
  "compression": null,
  "extensions": {
    "motion": null,
    "altitude": null,
    "phg": null,
    "radio_range": null,
    "df_signal": null,
    "df_bearing": null,
    "dao": null,
    "area": null,
    "signpost": null,
    "weather": null,
    "storm": null,
    "telemetry": null
  },
  "comment": ""
}
```

| Field           | JSON value / allowed values         | Presence / default                                            |
| --------------- | ----------------------------------- | ------------------------------------------------------------- |
| `type`          | `"position"`                        | required standalone; nested rules above                       |
| `latitude_deg`  | finite number                       | **required**                                                  |
| `longitude_deg` | finite number                       | **required**                                                  |
| `symbol`        | [Symbol](#symbol)                   | optional; default [Symbol](#symbol) with its defaults         |
| `messaging`     | boolean                             | optional; default `false`                                     |
| `timestamp`     | [Timestamp](#timestamp) or null     | optional; default `null`                                      |
| `tail`          | Latin-1 byte string                 | optional; default `""`                                        |
| `encoding`      | `'uncompressed'`, `'compressed'`    | optional; default `'uncompressed'`                            |
| `ambiguity`     | [Ambiguity](#ambiguity) or null     | optional; default `null`                                      |
| `compression`   | [Compression](#compression) or null | optional; default `null`                                      |
| `extensions`    | [Extensions](#extensions)           | optional; default [Extensions](#extensions) with its defaults |
| `comment`       | Latin-1 byte string                 | optional; default `""`                                        |

### MicE

Standalone tag: `mic_e`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "mic_e",
  "position": {
    "latitude_deg": 49,
    "longitude_deg": -72,
    "symbol": {
      "table_id": "/",
      "code": "-"
    },
    "ambiguity": null,
    "extensions": {
      "motion": null,
      "altitude": null,
      "phg": null,
      "radio_range": null,
      "df_signal": null,
      "df_bearing": null,
      "dao": null,
      "area": null,
      "signpost": null,
      "weather": null,
      "storm": null,
      "telemetry": null
    },
    "tail": "",
    "comment": ""
  },
  "comment_bits": [true, false, true],
  "comment_set": "standard",
  "dti": 96,
  "fix": "current",
  "type_marker": "",
  "grid": null,
  "grid_symbol": null,
  "destination_raw": null,
  "longitude_offset": null
}
```

| Field              | JSON value / allowed values                         | Presence / default                      |
| ------------------ | --------------------------------------------------- | --------------------------------------- |
| `type`             | `"mic_e"`                                           | required standalone; nested rules above |
| `position`         | [Location](#location)                               | **required**                            |
| `comment_bits`     | array of exactly 3 items: boolean, boolean, boolean | **required**                            |
| `comment_set`      | `'standard'`, `'custom'`                            | optional; default `'standard'`          |
| `dti`              | `96`, `39`, `28`, `29`                              | optional; default `96`                  |
| `fix`              | `'current'`, `'old'`, `'unknown'`                   | optional; default `'current'`           |
| `type_marker`      | Latin-1 byte string                                 | optional; default `""`                  |
| `grid`             | [GridLocator](#gridlocator) or null                 | optional; default `null`                |
| `grid_symbol`      | [Symbol](#symbol) or null                           | optional; default `null`                |
| `destination_raw`  | string or null                                      | optional; default `null`                |
| `longitude_offset` | integer or null                                     | optional; default `null`                |

### ObjectReport

Standalone tag: `object`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "object",
  "name": "AID #2",
  "position": {
    "latitude_deg": 49,
    "longitude_deg": -72,
    "symbol": {
      "table_id": "/",
      "code": "-"
    },
    "ambiguity": null,
    "extensions": {
      "motion": null,
      "altitude": null,
      "phg": null,
      "radio_range": null,
      "df_signal": null,
      "df_bearing": null,
      "dao": null,
      "area": null,
      "signpost": null,
      "weather": null,
      "storm": null,
      "telemetry": null
    },
    "tail": "",
    "comment": ""
  },
  "timestamp": {
    "kind": "dhm_utc",
    "hour": 12,
    "minute": 30,
    "day": 17,
    "second": null,
    "month": null,
    "raw": null
  },
  "alive": false,
  "name_raw": "AID #2   ",
  "legacy": false,
  "encoding": "uncompressed",
  "compression": null
}
```

| Field         | JSON value / allowed values         | Presence / default                      |
| ------------- | ----------------------------------- | --------------------------------------- |
| `type`        | `"object"`                          | required standalone; nested rules above |
| `name`        | string                              | **required**                            |
| `position`    | [Location](#location)               | **required**                            |
| `timestamp`   | [Timestamp](#timestamp)             | **required**                            |
| `alive`       | boolean                             | optional; default `true`                |
| `name_raw`    | Latin-1 byte string or null         | optional; default `null`                |
| `legacy`      | boolean                             | optional; default `false`               |
| `encoding`    | `'uncompressed'`, `'compressed'`    | optional; default `'uncompressed'`      |
| `compression` | [Compression](#compression) or null | optional; default `null`                |

### ItemReport

Standalone tag: `item`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "item",
  "name": "abc",
  "position": {
    "latitude_deg": 49,
    "longitude_deg": -72,
    "symbol": {
      "table_id": "/",
      "code": "-"
    },
    "ambiguity": null,
    "extensions": {
      "motion": null,
      "altitude": null,
      "phg": null,
      "radio_range": null,
      "df_signal": null,
      "df_bearing": null,
      "dao": null,
      "area": null,
      "signpost": null,
      "weather": null,
      "storm": null,
      "telemetry": null
    },
    "tail": "",
    "comment": ""
  },
  "alive": false,
  "name_raw": null,
  "encoding": "uncompressed",
  "compression": null
}
```

| Field         | JSON value / allowed values         | Presence / default                      |
| ------------- | ----------------------------------- | --------------------------------------- |
| `type`        | `"item"`                            | required standalone; nested rules above |
| `name`        | string                              | **required**                            |
| `position`    | [Location](#location)               | **required**                            |
| `alive`       | boolean                             | optional; default `true`                |
| `name_raw`    | Latin-1 byte string or null         | optional; default `null`                |
| `encoding`    | `'uncompressed'`, `'compressed'`    | optional; default `'uncompressed'`      |
| `compression` | [Compression](#compression) or null | optional; default `null`                |

### WeatherReport

Standalone tag: `weather`. [Back to type map](#type-map-and-object-catalog).

Weather measurements are direct JSON properties; `weather` is not a JSON property.

```json
{
  "type": "weather",
  "wind_direction": {
    "value": 270,
    "unit": "degrees",
    "raw": null
  },
  "wind_speed": {
    "value": 12,
    "unit": "mph",
    "raw": null
  },
  "gust": null,
  "temperature": {
    "value": 68,
    "unit": "fahrenheit",
    "raw": null
  },
  "humidity": null,
  "pressure": {
    "value": 1013.2,
    "unit": "hPa",
    "raw": null
  },
  "rain_1h": null,
  "rain_24h": null,
  "rain_since_midnight": null,
  "snow_24h": null,
  "luminosity": null,
  "rain_counter": null,
  "water_height": null,
  "software_code": null,
  "device_code": null,
  "raw": null,
  "timestamp": {
    "kind": "mdhm_utc",
    "hour": 12,
    "minute": 30,
    "day": 17,
    "second": null,
    "month": 10,
    "raw": null
  },
  "comment": ""
}
```

| Field                 | JSON value / allowed values         | Presence / default                      |
| --------------------- | ----------------------------------- | --------------------------------------- |
| `type`                | `"weather"`                         | required standalone; nested rules above |
| `wind_direction`      | [Measurement](#measurement) or null | optional; default `null`                |
| `wind_speed`          | [Measurement](#measurement) or null | optional; default `null`                |
| `gust`                | [Measurement](#measurement) or null | optional; default `null`                |
| `temperature`         | [Measurement](#measurement) or null | optional; default `null`                |
| `humidity`            | [Measurement](#measurement) or null | optional; default `null`                |
| `pressure`            | [Measurement](#measurement) or null | optional; default `null`                |
| `rain_1h`             | [Measurement](#measurement) or null | optional; default `null`                |
| `rain_24h`            | [Measurement](#measurement) or null | optional; default `null`                |
| `rain_since_midnight` | [Measurement](#measurement) or null | optional; default `null`                |
| `snow_24h`            | [Measurement](#measurement) or null | optional; default `null`                |
| `luminosity`          | [Measurement](#measurement) or null | optional; default `null`                |
| `rain_counter`        | [Measurement](#measurement) or null | optional; default `null`                |
| `water_height`        | [WaterHeight](#waterheight) or null | optional; default `null`                |
| `software_code`       | Latin-1 byte string or null         | optional; default `null`                |
| `device_code`         | Latin-1 byte string or null         | optional; default `null`                |
| `raw`                 | Latin-1 byte string or null         | optional; default `null`                |
| `timestamp`           | [Timestamp](#timestamp) or null     | optional; default `null`                |
| `comment`             | Latin-1 byte string                 | optional; default `""`                  |

### Telemetry

Standalone tag: `telemetry`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "telemetry",
  "data": {
    "analog": [1, 2, 3, 4, 5],
    "digital": [true, true, true, true, true, true, true, true],
    "sequence": 1,
    "encoding": "classic",
    "sequence_raw": null,
    "raw": null,
    "mic_comma": true
  },
  "comment": ""
}
```

| Field     | JSON value / allowed values     | Presence / default                      |
| --------- | ------------------------------- | --------------------------------------- |
| `type`    | `"telemetry"`                   | required standalone; nested rules above |
| `data`    | [TelemetryData](#telemetrydata) | **required**                            |
| `comment` | Latin-1 byte string             | optional; default `""`                  |

### TelemetryDefinition

Standalone tag: `telemetry_definition`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "telemetry_definition",
  "addressee": "N0CALL",
  "definition": {
    "type": "telemetry_parameters",
    "channels": ["Temperature"]
  },
  "values_raw": []
}
```

| Field        | JSON value / allowed values                                                                                                                                      | Presence / default                      |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `type`       | `"telemetry_definition"`                                                                                                                                         | required standalone; nested rules above |
| `addressee`  | string                                                                                                                                                           | **required**                            |
| `definition` | [TelemetryParameters](#telemetryparameters) or [TelemetryUnits](#telemetryunits) or [TelemetryEquations](#telemetryequations) or [TelemetryBits](#telemetrybits) | **required**                            |
| `values_raw` | array of Latin-1 byte string                                                                                                                                     | optional; default `[]`                  |

### Status

Standalone tag: `status`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "status",
  "text": "Ready",
  "timestamp": null,
  "grid": null,
  "symbol": null,
  "beam": null
}
```

| Field       | JSON value / allowed values         | Presence / default                      |
| ----------- | ----------------------------------- | --------------------------------------- |
| `type`      | `"status"`                          | required standalone; nested rules above |
| `text`      | Latin-1 byte string                 | optional; default `""`                  |
| `timestamp` | [Timestamp](#timestamp) or null     | optional; default `null`                |
| `grid`      | [GridLocator](#gridlocator) or null | optional; default `null`                |
| `symbol`    | [Symbol](#symbol) or null           | optional; default `null`                |
| `beam`      | [Beam](#beam) or null               | optional; default `null`                |

### Message

Standalone tag: `message`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "message",
  "addressee": "W1AW",
  "text": "Hello",
  "message_id": "003",
  "reply_ack": null
}
```

| Field        | JSON value / allowed values   | Presence / default                      |
| ------------ | ----------------------------- | --------------------------------------- |
| `type`       | `"message"`                   | required standalone; nested rules above |
| `addressee`  | string                        | **required**                            |
| `text`       | Latin-1 byte string           | optional; default `""`                  |
| `message_id` | string or null                | optional; default `null`                |
| `reply_ack`  | [ReplyAck](#replyack) or null | optional; default `null`                |

### Acknowledgment

Standalone tag: `acknowledgment`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "acknowledgment",
  "addressee": "W1AW",
  "message_id": "003",
  "rejected": false,
  "reply_ack": null
}
```

| Field        | JSON value / allowed values   | Presence / default                      |
| ------------ | ----------------------------- | --------------------------------------- |
| `type`       | `"acknowledgment"`            | required standalone; nested rules above |
| `addressee`  | string                        | **required**                            |
| `message_id` | string                        | **required**                            |
| `rejected`   | boolean                       | optional; default `false`               |
| `reply_ack`  | [ReplyAck](#replyack) or null | optional; default `null`                |

### AutoAnswer

Standalone tag: `auto_answer`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "auto_answer",
  "addressee": "W1AW",
  "text": "Away",
  "previous_ack": "02"
}
```

| Field          | JSON value / allowed values | Presence / default                      |
| -------------- | --------------------------- | --------------------------------------- |
| `type`         | `"auto_answer"`             | required standalone; nested rules above |
| `addressee`    | string                      | **required**                            |
| `text`         | Latin-1 byte string         | **required**                            |
| `previous_ack` | string or null              | optional; default `null`                |

### Bulletin

Standalone tag: `bulletin`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "bulletin",
  "identifier": "1",
  "text": "Notice",
  "group": "WX",
  "announcement": false,
  "legacy": false
}
```

| Field          | JSON value / allowed values | Presence / default                      |
| -------------- | --------------------------- | --------------------------------------- |
| `type`         | `"bulletin"`                | required standalone; nested rules above |
| `identifier`   | string                      | **required**                            |
| `text`         | Latin-1 byte string         | **required**                            |
| `group`        | string or null              | optional; default `null`                |
| `announcement` | boolean                     | optional; default `false`               |
| `legacy`       | boolean                     | optional; default `false`               |

### NWSBulletin

Standalone tag: `nws_bulletin`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nws_bulletin",
  "addressee": "NWS-WARN",
  "text": "Storm",
  "reference_id": "S9JbA"
}
```

| Field          | JSON value / allowed values | Presence / default                      |
| -------------- | --------------------------- | --------------------------------------- |
| `type`         | `"nws_bulletin"`            | required standalone; nested rules above |
| `addressee`    | string                      | **required**                            |
| `text`         | Latin-1 byte string         | **required**                            |
| `reference_id` | string or null              | optional; default `null`                |

### NTSMessage

Standalone tag: `nts_message`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nts_message",
  "addressee": "W1AW",
  "record": {
    "type": "nts_text",
    "line": 1,
    "text": "Hello"
  },
  "message_id": "001"
}
```

| Field        | JSON value / allowed values                                                                                                                                        | Presence / default                      |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------- |
| `type`       | `"nts_message"`                                                                                                                                                    | required standalone; nested rules above |
| `addressee`  | string                                                                                                                                                             | **required**                            |
| `record`     | [NTSHeader](#ntsheader) or [NTSAddress](#ntsaddress) or [NTSPhone](#ntsphone) or [NTSText](#ntstext) or [NTSSignature](#ntssignature) or [NTSRouting](#ntsrouting) | **required**                            |
| `message_id` | string or null                                                                                                                                                     | optional; default `null`                |

### Query

Standalone tag: `query`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "query",
  "name": "APRS",
  "addressee": null,
  "footprint": {
    "center": {
      "latitude_deg": 49,
      "longitude_deg": -72
    },
    "radius_miles": 20
  },
  "heard_station": null,
  "arguments": "",
  "message_id": null
}
```

| Field           | JSON value / allowed values               | Presence / default                      |
| --------------- | ----------------------------------------- | --------------------------------------- |
| `type`          | `"query"`                                 | required standalone; nested rules above |
| `name`          | string                                    | **required**                            |
| `addressee`     | string or null                            | optional; default `null`                |
| `footprint`     | [QueryFootprint](#queryfootprint) or null | optional; default `null`                |
| `heard_station` | string or null                            | optional; default `null`                |
| `arguments`     | Latin-1 byte string                       | optional; default `""`                  |
| `message_id`    | string or null                            | optional; default `null`                |

### DirectStations

Standalone tag: `direct_stations`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "direct_stations",
  "stations": ["W1AW"]
}
```

| Field      | JSON value / allowed values | Presence / default                      |
| ---------- | --------------------------- | --------------------------------------- |
| `type`     | `"direct_stations"`         | required standalone; nested rules above |
| `stations` | array of string             | **required**                            |

### HeardStation

Standalone tag: `heard_station`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "heard_station",
  "station": "W1AW",
  "counts": [1, null, 3]
}
```

| Field     | JSON value / allowed values | Presence / default                      |
| --------- | --------------------------- | --------------------------------------- |
| `type`    | `"heard_station"`           | required standalone; nested rules above |
| `station` | string                      | **required**                            |
| `counts`  | array of integer or null    | **required**                            |

### TraceRoute

Standalone tag: `trace_route`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "trace_route",
  "header": {
    "source": "N0CALL",
    "destination": "APRS",
    "path": []
  }
}
```

| Field    | JSON value / allowed values | Presence / default                      |
| -------- | --------------------------- | --------------------------------------- |
| `type`   | `"trace_route"`             | required standalone; nested rules above |
| `header` | [Header](#header)           | **required**                            |

### QueryResponse

Standalone tag: `query_response`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "query_response",
  "addressee": "W1AW",
  "response": {
    "type": "direct_stations",
    "stations": ["N0CALL"]
  }
}
```

| Field       | JSON value / allowed values                                                                     | Presence / default                      |
| ----------- | ----------------------------------------------------------------------------------------------- | --------------------------------------- |
| `type`      | `"query_response"`                                                                              | required standalone; nested rules above |
| `addressee` | string                                                                                          | **required**                            |
| `response`  | [DirectStations](#directstations) or [HeardStation](#heardstation) or [TraceRoute](#traceroute) | **required**                            |

### Capabilities

Standalone tag: `capabilities`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "capabilities",
  "tokens": [
    {
      "name": "IGATE",
      "value": null
    }
  ]
}
```

| Field    | JSON value / allowed values                  | Presence / default                      |
| -------- | -------------------------------------------- | --------------------------------------- |
| `type`   | `"capabilities"`                             | required standalone; nested rules above |
| `tokens` | array of [CapabilityToken](#capabilitytoken) | **required**                            |

### NMEAReport

Standalone tag: `nmea`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nmea",
  "sentence": {
    "type": "gll",
    "coordinates": {
      "latitude_deg": 49,
      "longitude_deg": -72
    },
    "time_utc": "123000",
    "fix_status": "A"
  },
  "metadata": {
    "talker": "GP",
    "checksum_supplied": null,
    "checksum_valid": null,
    "fields_raw": []
  },
  "position_usable": null,
  "symbol": null,
  "comment": ""
}
```

| Field             | JSON value / allowed values                                             | Presence / default                                                |
| ----------------- | ----------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `type`            | `"nmea"`                                                                | required standalone; nested rules above                           |
| `sentence`        | [GGA](#gga) or [GLL](#gll) or [RMC](#rmc) or [VTG](#vtg) or [WPL](#wpl) | **required**                                                      |
| `metadata`        | [NMEAMetadata](#nmeametadata)                                           | optional; default [NMEAMetadata](#nmeametadata) with its defaults |
| `position_usable` | boolean or null                                                         | optional; default `null`                                          |
| `symbol`          | [Symbol](#symbol) or null                                               | optional; default `null`                                          |
| `comment`         | Latin-1 byte string                                                     | optional; default `""`                                            |

### ThirdParty

Standalone tag: `third_party`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "third_party",
  "packet": {
    "header": {
      "source": "W1AW",
      "destination": "APRS",
      "path": []
    },
    "payload": {
      "type": "status",
      "text": "Ready",
      "timestamp": null,
      "grid": null,
      "symbol": null,
      "beam": null
    },
    "original_wire": null,
    "header_semantics": null
  }
}
```

| Field    | JSON value / allowed values | Presence / default                      |
| -------- | --------------------------- | --------------------------------------- |
| `type`   | `"third_party"`             | required standalone; nested rules above |
| `packet` | [Packet](#packet)           | **required**                            |

### UserDefined

Standalone tag: `user_defined`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "user_defined",
  "user_id": "Q",
  "user_type": "1",
  "data": "Hello\u0000\u00ff"
}
```

| Field       | JSON value / allowed values | Presence / default                      |
| ----------- | --------------------------- | --------------------------------------- |
| `type`      | `"user_defined"`            | required standalone; nested rules above |
| `user_id`   | Latin-1 byte string         | **required**                            |
| `user_type` | Latin-1 byte string         | **required**                            |
| `data`      | Latin-1 byte string         | **required**                            |

### RawWeather

Standalone tag: `raw_weather`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "raw_weather",
  "format": "ultw",
  "information": "$ULTW0000",
  "weather": null
}
```

| Field         | JSON value / allowed values                                      | Presence / default                      |
| ------------- | ---------------------------------------------------------------- | --------------------------------------- |
| `type`        | `"raw_weather"`                                                  | required standalone; nested rules above |
| `format`      | `'ultimeter_ii'`, `'ultimeter_2000'`, `'ultw'`, `'peet_logging'` | **required**                            |
| `information` | Latin-1 byte string                                              | **required**                            |
| `weather`     | [Weather](#weather) or null                                      | optional; default `null`                |

### Agrelo

Standalone tag: `agrelo`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "agrelo",
  "bearing_deg": 123,
  "quality_code": 4,
  "raw": null
}
```

| Field          | JSON value / allowed values | Presence / default                      |
| -------------- | --------------------------- | --------------------------------------- |
| `type`         | `"agrelo"`                  | required standalone; nested rules above |
| `bearing_deg`  | integer                     | **required**                            |
| `quality_code` | integer                     | **required**                            |
| `raw`          | Latin-1 byte string or null | optional; default `null`                |

### MaidenheadBeacon

Standalone tag: `maidenhead_beacon`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "maidenhead_beacon",
  "grid": {
    "locator": "IO91SX",
    "bounds": null,
    "center": null
  },
  "symbol": null,
  "comment": ""
}
```

| Field     | JSON value / allowed values | Presence / default                      |
| --------- | --------------------------- | --------------------------------------- |
| `type`    | `"maidenhead_beacon"`       | required standalone; nested rules above |
| `grid`    | [GridLocator](#gridlocator) | **required**                            |
| `symbol`  | [Symbol](#symbol) or null   | optional; default `null`                |
| `comment` | Latin-1 byte string         | optional; default `""`                  |

### LegacyPosition

Standalone tag: `legacy_position`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "legacy_position",
  "prefix": "X1J ",
  "position": {
    "type": "position",
    "latitude_deg": 49,
    "longitude_deg": -72,
    "symbol": {
      "table_id": "/",
      "code": "-"
    },
    "messaging": false,
    "timestamp": null,
    "tail": "",
    "encoding": "uncompressed",
    "ambiguity": null,
    "compression": null,
    "extensions": {
      "motion": null,
      "altitude": null,
      "phg": null,
      "radio_range": null,
      "df_signal": null,
      "df_bearing": null,
      "dao": null,
      "area": null,
      "signpost": null,
      "weather": null,
      "storm": null,
      "telemetry": null
    },
    "comment": ""
  }
}
```

| Field      | JSON value / allowed values | Presence / default                      |
| ---------- | --------------------------- | --------------------------------------- |
| `type`     | `"legacy_position"`         | required standalone; nested rules above |
| `prefix`   | Latin-1 byte string         | **required**                            |
| `position` | [Position](#position)       | **required**                            |

### NonAPRSBeacon

Standalone tag: `non_aprs_beacon`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "non_aprs_beacon",
  "text": "UIDIGI ready"
}
```

| Field  | JSON value / allowed values | Presence / default                      |
| ------ | --------------------------- | --------------------------------------- |
| `type` | `"non_aprs_beacon"`         | required standalone; nested rules above |
| `text` | Latin-1 byte string         | **required**                            |

### InvalidTest

Standalone tag: `invalid_test`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "invalid_test",
  "data": "invalid fix"
}
```

| Field  | JSON value / allowed values | Presence / default                      |
| ------ | --------------------------- | --------------------------------------- |
| `type` | `"invalid_test"`            | required standalone; nested rules above |
| `data` | Latin-1 byte string         | **required**                            |

### Reserved

Standalone tag: `reserved`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "reserved",
  "dti": 126,
  "data": "data"
}
```

| Field  | JSON value / allowed values | Presence / default                      |
| ------ | --------------------------- | --------------------------------------- |
| `type` | `"reserved"`                | required standalone; nested rules above |
| `dti`  | integer                     | **required**                            |
| `data` | Latin-1 byte string         | **required**                            |

### ExternalExtension

Standalone tag: `external_extension`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "external_extension",
  "name": "polygon_line",
  "information": "raw",
  "specification_url": null
}
```

| Field               | JSON value / allowed values             | Presence / default                      |
| ------------------- | --------------------------------------- | --------------------------------------- |
| `type`              | `"external_extension"`                  | required standalone; nested rules above |
| `name`              | `'polygon_line'`, `'vendor'`, `'other'` | **required**                            |
| `information`       | Latin-1 byte string                     | **required**                            |
| `specification_url` | string or null                          | optional; default `null`                |

### Diagnostic

Standalone tag: `diagnostic`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "diagnostic",
  "code": "unsupported",
  "message": "codec pending"
}
```

| Field     | JSON value / allowed values    | Presence / default                      |
| --------- | ------------------------------ | --------------------------------------- |
| `type`    | `"diagnostic"`                 | required standalone; nested rules above |
| `code`    | `'unsupported'`, `'malformed'` | **required**                            |
| `message` | string                         | **required**                            |

### Opaque

Standalone tag: `opaque`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "opaque",
  "information": "~\u00ff\r\n",
  "reason": "unsupported data type",
  "diagnostic": null
}
```

| Field         | JSON value / allowed values       | Presence / default                          |
| ------------- | --------------------------------- | ------------------------------------------- |
| `type`        | `"opaque"`                        | required standalone; nested rules above     |
| `information` | Latin-1 byte string               | **required**                                |
| `reason`      | string                            | optional; default `'unsupported data type'` |
| `diagnostic`  | [Diagnostic](#diagnostic) or null | optional; default `null`                    |

### Packet

Standalone tag: `packet`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS",
    "path": []
  },
  "payload": {
    "type": "position",
    "latitude_deg": 49.05833333333333,
    "longitude_deg": -72.02916666666667,
    "symbol": {
      "table_id": "/",
      "code": ">"
    },
    "messaging": false,
    "timestamp": null,
    "tail": "",
    "encoding": "uncompressed",
    "ambiguity": null,
    "compression": null,
    "extensions": {
      "motion": null,
      "altitude": null,
      "phg": null,
      "radio_range": null,
      "df_signal": null,
      "df_bearing": null,
      "dao": null,
      "area": null,
      "signpost": null,
      "weather": null,
      "storm": null,
      "telemetry": null
    },
    "comment": ""
  },
  "original_wire": "N0CALL>APRS:!4903.50N/07201.75W>",
  "header_semantics": null
}
```

| Field              | JSON value / allowed values                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Presence / default                      |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `type`             | `"packet"`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | required standalone; nested rules above |
| `header`           | [Header](#header)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | **required**                            |
| `payload`          | [Position](#position) or [MicE](#mice) or [ObjectReport](#objectreport) or [ItemReport](#itemreport) or [WeatherReport](#weatherreport) or [Telemetry](#telemetry) or [TelemetryDefinition](#telemetrydefinition) or [Status](#status) or [Message](#message) or [Acknowledgment](#acknowledgment) or [AutoAnswer](#autoanswer) or [Bulletin](#bulletin) or [NWSBulletin](#nwsbulletin) or [NTSMessage](#ntsmessage) or [Query](#query) or [QueryResponse](#queryresponse) or [Capabilities](#capabilities) or [NMEAReport](#nmeareport) or [ThirdParty](#thirdparty) or [UserDefined](#userdefined) or [RawWeather](#rawweather) or [Agrelo](#agrelo) or [MaidenheadBeacon](#maidenheadbeacon) or [LegacyPosition](#legacyposition) or [NonAPRSBeacon](#nonaprsbeacon) or [InvalidTest](#invalidtest) or [Reserved](#reserved) or [ExternalExtension](#externalextension) or [Opaque](#opaque) | **required**                            |
| `original_wire`    | Latin-1 byte string or null                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | optional; default `null`                |
| `header_semantics` | [HeaderSemantics](#headersemantics) or null                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | optional; default `null`                |

### EncodedPacketFields

Standalone tag: `encoded_packet_fields`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "encoded_packet_fields",
  "header": {
    "source": "N0CALL",
    "destination": "APRS",
    "path": []
  },
  "information": ">Ready"
}
```

| Field         | JSON value / allowed values | Presence / default                      |
| ------------- | --------------------------- | --------------------------------------- |
| `type`        | `"encoded_packet_fields"`   | required standalone; nested rules above |
| `header`      | [Header](#header)           | **required**                            |
| `information` | Latin-1 byte string         | **required**                            |

## Nested union examples

Each allowed member is shown in its actual container. Fixed nested fields remain untagged.

### TelemetryDefinition with TelemetryParameters

```json
{
  "type": "telemetry_definition",
  "addressee": "N0CALL",
  "definition": {
    "type": "telemetry_parameters",
    "channels": ["Temperature", null, "Voltage"]
  },
  "values_raw": []
}
```

### TelemetryDefinition with TelemetryUnits

```json
{
  "type": "telemetry_definition",
  "addressee": "N0CALL",
  "definition": {
    "type": "telemetry_units",
    "channels": ["deg.C", null, "V"]
  },
  "values_raw": []
}
```

### TelemetryDefinition with TelemetryEquations

```json
{
  "type": "telemetry_definition",
  "addressee": "N0CALL",
  "definition": {
    "type": "telemetry_equations",
    "coefficients": [
      {
        "a": 0,
        "b": 1,
        "c": 0
      },
      null
    ]
  },
  "values_raw": []
}
```

### TelemetryDefinition with TelemetryBits

```json
{
  "type": "telemetry_definition",
  "addressee": "N0CALL",
  "definition": {
    "type": "telemetry_bits",
    "sense": [true, true, true, true, true, true, true, true],
    "project_title": "Project"
  },
  "values_raw": []
}
```

### NMEAReport with GGA

```json
{
  "type": "nmea",
  "sentence": {
    "type": "gga",
    "time_utc": "123000",
    "coordinates": {
      "latitude_deg": 49,
      "longitude_deg": -72
    },
    "fix_quality": 0,
    "satellites": null,
    "hdop": null,
    "altitude_msl_m": 12,
    "geoid_separation_m": 3,
    "dgps_age": null,
    "dgps_station": null
  },
  "metadata": {
    "talker": "GP",
    "checksum_supplied": null,
    "checksum_valid": null,
    "fields_raw": []
  },
  "position_usable": null,
  "symbol": null,
  "comment": ""
}
```

### NMEAReport with GLL

```json
{
  "type": "nmea",
  "sentence": {
    "type": "gll",
    "coordinates": {
      "latitude_deg": 49,
      "longitude_deg": -72
    },
    "time_utc": "123000",
    "fix_status": "V"
  },
  "metadata": {
    "talker": "GP",
    "checksum_supplied": null,
    "checksum_valid": null,
    "fields_raw": []
  },
  "position_usable": null,
  "symbol": null,
  "comment": ""
}
```

### NMEAReport with RMC

```json
{
  "type": "nmea",
  "sentence": {
    "type": "rmc",
    "time_utc": "123000",
    "date_ddmmyy": "171026",
    "fix_status": "A",
    "coordinates": {
      "latitude_deg": 49,
      "longitude_deg": -72
    },
    "speed_knots": 12,
    "course_deg": 90,
    "magnetic_variation": null,
    "magnetic_variation_direction": null
  },
  "metadata": {
    "talker": "GP",
    "checksum_supplied": null,
    "checksum_valid": null,
    "fields_raw": []
  },
  "position_usable": null,
  "symbol": null,
  "comment": ""
}
```

### NMEAReport with VTG

```json
{
  "type": "nmea",
  "sentence": {
    "type": "vtg",
    "course_true_deg": 90,
    "course_magnetic_deg": 89,
    "speed_knots": 10,
    "speed_kmh_reported": 18.52
  },
  "metadata": {
    "talker": "GP",
    "checksum_supplied": null,
    "checksum_valid": null,
    "fields_raw": []
  },
  "position_usable": null,
  "symbol": null,
  "comment": ""
}
```

### NMEAReport with WPL

```json
{
  "type": "nmea",
  "sentence": {
    "type": "wpl",
    "coordinates": {
      "latitude_deg": 49,
      "longitude_deg": -72
    },
    "name": "HOME"
  },
  "metadata": {
    "talker": "GP",
    "checksum_supplied": null,
    "checksum_valid": null,
    "fields_raw": []
  },
  "position_usable": null,
  "symbol": null,
  "comment": ""
}
```

### NTSMessage with NTSHeader

```json
{
  "type": "nts_message",
  "addressee": "W1AW",
  "record": {
    "type": "nts_header",
    "number": "12",
    "precedence": "R",
    "handling": "HXA",
    "originator": "N0CALL",
    "check": "5",
    "place": "REDMOND WA",
    "time": "1800",
    "date": "OCT 15"
  },
  "message_id": null
}
```

### NTSMessage with NTSAddress

```json
{
  "type": "nts_message",
  "addressee": "W1AW",
  "record": {
    "type": "nts_address",
    "lines": ["ADAM", "123 MAIN ST", "REDMOND WA", "98052"]
  },
  "message_id": null
}
```

### NTSMessage with NTSPhone

```json
{
  "type": "nts_message",
  "addressee": "W1AW",
  "record": {
    "type": "nts_phone",
    "number": "5550100"
  },
  "message_id": null
}
```

### NTSMessage with NTSText

```json
{
  "type": "nts_message",
  "addressee": "W1AW",
  "record": {
    "type": "nts_text",
    "line": 1,
    "text": "Hello"
  },
  "message_id": null
}
```

### NTSMessage with NTSSignature

```json
{
  "type": "nts_message",
  "addressee": "W1AW",
  "record": {
    "type": "nts_signature",
    "text": "N0CALL"
  },
  "message_id": null
}
```

### NTSMessage with NTSRouting

```json
{
  "type": "nts_message",
  "addressee": "W1AW",
  "record": {
    "type": "nts_routing",
    "received_from": "W1AW",
    "received_at": "151800Z",
    "sent_to": "N0CALL",
    "sent_at": "151805Z"
  },
  "message_id": null
}
```

### QueryResponse with DirectStations

```json
{
  "type": "query_response",
  "addressee": "W1AW",
  "response": {
    "type": "direct_stations",
    "stations": ["W1AW"]
  }
}
```

### QueryResponse with HeardStation

```json
{
  "type": "query_response",
  "addressee": "W1AW",
  "response": {
    "type": "heard_station",
    "station": "W1AW",
    "counts": [1, null, 3]
  }
}
```

### QueryResponse with TraceRoute

```json
{
  "type": "query_response",
  "addressee": "W1AW",
  "response": {
    "type": "trace_route",
    "header": {
      "source": "N0CALL",
      "destination": "APRS",
      "path": []
    }
  }
}
```

## Complete weather packet

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS",
    "path": []
  },
  "payload": {
    "type": "weather",
    "wind_direction": {
      "value": 270,
      "unit": "degrees",
      "raw": null
    },
    "wind_speed": {
      "value": 12,
      "unit": "mph",
      "raw": null
    },
    "gust": null,
    "temperature": {
      "value": 68,
      "unit": "fahrenheit",
      "raw": null
    },
    "humidity": null,
    "pressure": {
      "value": 1013.2,
      "unit": "hPa",
      "raw": null
    },
    "rain_1h": null,
    "rain_24h": null,
    "rain_since_midnight": null,
    "snow_24h": null,
    "luminosity": null,
    "rain_counter": null,
    "water_height": null,
    "software_code": null,
    "device_code": null,
    "raw": null,
    "timestamp": {
      "kind": "mdhm_utc",
      "hour": 12,
      "minute": 30,
      "day": 17,
      "second": null,
      "month": 10,
      "raw": null
    },
    "comment": ""
  },
  "original_wire": null,
  "header_semantics": null
}
```

## Regeneration and validation

Run `python packages/aprs/tests/generate_json_reference.py` from the repository
root with the package installed, then run the repository formatting hooks.
`test_json_reference.py` checks every JSON example against the models, verifies
round trips including raw metadata, and checks catalog coverage against the full
public JSONModel union. This prevents examples from silently diverging from code.
Runtime capability metadata (`CodecCapability`) is not a JSON data model: its
Python class references belong to the codec registry, not a packet document.
