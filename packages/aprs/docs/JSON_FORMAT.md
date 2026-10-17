# APRS JSON reference

This is the canonical JSON format for `hamkit-aprs`. Examples are
pretty-printed, executable data, with nested values expanded. They illustrate
values, not legal ranges or complete APRS wire support. The field tables are the
shape contract: every field, requiredness, default, allowed enum, unit and nested
model is listed. All 76 serializable models and all 29 payload families appear.

## Contents

- [Reading and writing](#reading-and-writing)
- [Tags](#tags)
- [Values, defaults and constraints](#values-defaults-and-constraints)
- [Type map and object catalog](#type-map-and-object-catalog)
- [Nested union examples](#nested-union-examples)
- [Complete weather packet](#complete-weather-packet)
- [Regeneration and validation](#regeneration-and-validation)

## Reading and writing

`to_json(model, indent=2)` returns text. `to_json_dict(model)` returns a JSON-safe
dictionary. `from_json(text)` and `from_json_dict(mapping)` return typed models.
Pass `expected_type=Weather` to check the class; typed overloads preserve the
concrete return annotation. `include_defaults=True` prints all fields, as in this
catalog. Compact output omits fields equal to their defaults, except policies,
which always contain every resolved field. Policy JSON loading requires all
fields; see [packet policies](ENVELOPE_POLICIES.md). Object property
order is not meaningful. JSON field names match Python attributes.

## Tags

One rule decides where `type` appears:

- The top-level object always has a `type`, such as `packet`, `measurement` or
  `header`, unless the reader passes `expected_type`.
- A field that can hold more than one model requires a `type`: `Packet.payload`,
  telemetry definitions, NMEA sentences, NTS records and query responses. The
  tags allowed there are exactly those of the linked models below.
- Every other nested object is untagged on output, because its field allows only
  one model. A `type` supplied there anyway must name that model.

Tags are explicitly registered protocol names, independent of Python class
names; classes are never loaded by name.

## Values, defaults and constraints

- Free text (messages, bulletins, status, comments) is any Unicode string, sent
  as UTF-8 per the adopted APRS 1.2 draft guidance; `to_json` escapes non-ASCII
  so output stays ASCII.
  Protocol tokens (callsigns, addressees, IDs, names, NMEA fields) are printable
  ASCII. Lone surrogates are never valid.
- Raw `bytes` are Latin-1 JSON strings: each U+0000–U+00FF code point represents
  one byte, so `\u0000` and `\u00ff` preserve arbitrary binary data. This is
  not base64 and not UTF-8.
- Tuples become arrays. Fixed tuples require the exact length in the table.
  Integers stay integers, even in number fields. Numbers are finite, booleans are not integers, numeric strings are not numbers,
  and enums match exactly, including case.
- Missing optional fields receive the listed defaults. Explicit null is accepted
  only where the type allows it. Missing required fields fail, even when their
  type permits null.
- An absent weather measurement (`null` or omitted) differs from a present
  measurement with `value: null` (unavailable reading), and both differ from zero.
- Units are the exhaustive `Measurement.unit` enum below; nothing is converted.
- `original_wire`, `diagnostics` and `raw`/`*_raw` evidence fields round-trip,
  although Python equality ignores them. They never override structured values.
- Values that follow from other fields (grid bounds and center, PHG range,
  compression type byte, area offsets, bulletin announcement flag, ambiguity
  cell) are Python properties, not JSON fields.
- Loading JSON runs the same constructor checks as Python: values that cannot
  exist on the wire or contradict another field raise `JSONModelError`. APRS
  limits a transmitter could still break (lengths, required report slots,
  symbol choices) are not load errors; `check_packet` reports them and
  `serialize_packet` refuses to send them. See
  [unresolved specification questions](UNRESOLVED_SPEC.md) and
  [wire coverage](API_COVERAGE.md).
- `parse_packet` returns a Packet, or one top-level Malformed when a field
  cannot be decoded. Malformed holds original_wire, diagnostics with field
  paths, and `recovered` data in the ordinary packet schema with unreadable
  fields omitted. Correct it, then load it with `from_json_dict`.
- Unknown fields, duplicate keys, unknown or incompatible tags and invalid
  values raise `JSONModelError` (an `APRSError` and `ValueError`).
- `max_depth` defaults to 64 and accepts integers 1–128. Cycles and excessive
  nesting fail. This is not an input-size bound. `include_defaults` must be bool;
  `indent` is null or a nonnegative integer.

## Type map and object catalog

Tags in this table are exhaustive. Every example includes optional fields and
defaults so its complete shape is visible; null optional nested objects link to
their own fully expanded examples in the field table.

| Model                                       | Stable type            | Role              |
| ------------------------------------------- | ---------------------- | ----------------- |
| [EnvelopePolicy](#envelopepolicy)           | `policy`               | field / container |
| [Measurement](#measurement)                 | `measurement`          | field / container |
| [Timestamp](#timestamp)                     | `timestamp`            | field / container |
| [Coordinates](#coordinates)                 | `coordinates`          | field / container |
| [Symbol](#symbol)                           | `symbol`               | field / container |
| [Grid](#grid)                               | `grid`                 | field / container |
| [Motion](#motion)                           | `motion`               | field / container |
| [Altitude](#altitude)                       | `altitude`             | field / container |
| [Range](#range)                             | `range`                | field / container |
| [PHG](#phg)                                 | `phg`                  | field / container |
| [Signal](#signal)                           | `signal`               | field / container |
| [Bearing](#bearing)                         | `bearing`              | field / container |
| [Compression](#compression)                 | `compression`          | field / container |
| [DAO](#dao)                                 | `dao`                  | field / container |
| [Area](#area)                               | `area`                 | field / container |
| [Signpost](#signpost)                       | `signpost`             | field / container |
| [WaterHeight](#waterheight)                 | `water_height`         | field / container |
| [Weather](#weather)                         | `weather`              | payload           |
| [Storm](#storm)                             | `storm`                | field / container |
| [Telemetry](#telemetry)                     | `telemetry`            | payload           |
| [Extensions](#extensions)                   | `extensions`           | field / container |
| [Beam](#beam)                               | `beam`                 | field / container |
| [TelemetryParameters](#telemetryparameters) | `telemetry_parameters` | field / container |
| [TelemetryUnits](#telemetryunits)           | `telemetry_units`      | field / container |
| [Calibration](#calibration)                 | `calibration`          | field / container |
| [TelemetryEquations](#telemetryequations)   | `telemetry_equations`  | field / container |
| [TelemetryBits](#telemetrybits)             | `telemetry_bits`       | field / container |
| [NTSHeader](#ntsheader)                     | `nts_header`           | field / container |
| [NTSAddress](#ntsaddress)                   | `nts_address`          | field / container |
| [NTSPhone](#ntsphone)                       | `nts_phone`            | field / container |
| [NTSText](#ntstext)                         | `nts_text`             | field / container |
| [NTSSignature](#ntssignature)               | `nts_signature`        | field / container |
| [NTSRouting](#ntsrouting)                   | `nts_routing`          | field / container |
| [Footprint](#footprint)                     | `footprint`            | field / container |
| [Capability](#capability)                   | `capability`           | field / container |
| [NMEAMetadata](#nmeametadata)               | `nmea_metadata`        | field / container |
| [GGA](#gga)                                 | `gga`                  | field / container |
| [GLL](#gll)                                 | `gll`                  | field / container |
| [RMC](#rmc)                                 | `rmc`                  | field / container |
| [VTG](#vtg)                                 | `vtg`                  | field / container |
| [WPL](#wpl)                                 | `wpl`                  | field / container |
| [Hop](#hop)                                 | `hop`                  | field / container |
| [Header](#header)                           | `header`               | field / container |
| [Position](#position)                       | `position`             | payload           |
| [MicE](#mice)                               | `mic_e`                | payload           |
| [Object](#object)                           | `object`               | payload           |
| [Item](#item)                               | `item`                 | payload           |
| [TelemetryDefinition](#telemetrydefinition) | `telemetry_definition` | payload           |
| [Status](#status)                           | `status`               | payload           |
| [Message](#message)                         | `message`              | payload           |
| [Acknowledgment](#acknowledgment)           | `acknowledgment`       | payload           |
| [AutoAnswer](#autoanswer)                   | `auto_answer`          | payload           |
| [Bulletin](#bulletin)                       | `bulletin`             | payload           |
| [NWSBulletin](#nwsbulletin)                 | `nws_bulletin`         | payload           |
| [Radiogram](#radiogram)                     | `radiogram`            | payload           |
| [Query](#query)                             | `query`                | payload           |
| [DirectStations](#directstations)           | `direct_stations`      | field / container |
| [HeardStation](#heardstation)               | `heard_station`        | field / container |
| [Trace](#trace)                             | `trace`                | field / container |
| [Response](#response)                       | `response`             | payload           |
| [Capabilities](#capabilities)               | `capabilities`         | payload           |
| [NMEA](#nmea)                               | `nmea`                 | payload           |
| [ThirdParty](#thirdparty)                   | `third_party`          | payload           |
| [UserDefined](#userdefined)                 | `user_defined`         | payload           |
| [RawWeather](#rawweather)                   | `raw_weather`          | payload           |
| [Agrelo](#agrelo)                           | `agrelo`               | payload           |
| [Maidenhead](#maidenhead)                   | `maidenhead`           | payload           |
| [LegacyPosition](#legacyposition)           | `legacy_position`      | payload           |
| [Beacon](#beacon)                           | `beacon`               | payload           |
| [Invalid](#invalid)                         | `invalid`              | payload           |
| [Reserved](#reserved)                       | `reserved`             | payload           |
| [ExternalExtension](#externalextension)     | `external_extension`   | payload           |
| [Diagnostic](#diagnostic)                   | `diagnostic`           | field / container |
| [Opaque](#opaque)                           | `opaque`               | payload           |
| [Packet](#packet)                           | `packet`               | field / container |
| [Malformed](#malformed)                     | `malformed`            | field / container |

### EnvelopePolicy

Standalone tag: `policy`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "policy",
  "source_pattern": "(?=.{1,9}\\Z)[A-Za-z0-9]{3,9}(?:-(?!0\\Z)[A-Za-z0-9]{1,2})?",
  "destination_pattern": "(?=.{1,9}\\Z)[A-Za-z0-9]{1,9}(?:-(?!0\\Z)[A-Za-z0-9]{1,2})?",
  "path_address_pattern": "(?=.{1,9}\\Z)[A-Za-z0-9]{1,9}(?:-(?!0\\Z)[A-Za-z0-9]{1,2})?",
  "max_path_entries": null,
  "max_information_bytes": null,
  "max_tnc2_line_bytes": 512,
  "extensions": [
    "utf8_text",
    "dao",
    "base91_telemetry",
    "expanded_telemetry",
    "phg_rate",
    "weather_extensions"
  ],
  "legacy_positions": false,
  "byte_fallback": "latin-1"
}
```

| Field                   | JSON value / allowed values                                                                                                                                       | Presence / default   |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| `type`                  | `"policy"`                                                                                                                                                        | see [Tags](#tags)    |
| `source_pattern`        | string                                                                                                                                                            | **required in JSON** |
| `destination_pattern`   | string                                                                                                                                                            | **required in JSON** |
| `path_address_pattern`  | string                                                                                                                                                            | **required in JSON** |
| `max_path_entries`      | integer or null                                                                                                                                                   | **required in JSON** |
| `max_information_bytes` | integer or null                                                                                                                                                   | **required in JSON** |
| `max_tnc2_line_bytes`   | integer or null                                                                                                                                                   | **required in JSON** |
| `extensions`            | array of `'utf8_text'`, `'dao'`, `'base91_telemetry'`, `'mice_device_ids'`, `'expanded_telemetry'`, `'phg_rate'`, `'weather_extensions'`, `'water_height_tenths'` | **required in JSON** |
| `legacy_positions`      | boolean                                                                                                                                                           | **required in JSON** |
| `byte_fallback`         | `'latin-1'`, `'reject'`                                                                                                                                           | **required in JSON** |

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

| Field   | JSON value / allowed values                                                                                                                                                                                                                                                                            | Presence / default       |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------ |
| `type`  | `"measurement"`                                                                                                                                                                                                                                                                                        | see [Tags](#tags)        |
| `value` | finite number or null                                                                                                                                                                                                                                                                                  | **required**             |
| `unit`  | `'degrees'`, `'knots'`, `'mph'`, `'m/s'`, `'km/h'`, `'feet'`, `'meters'`, `'miles'`, `'nautical_miles'`, `'fahrenheit'`, `'celsius'`, `'percent'`, `'hPa'`, `'inches'`, `'mm'`, `'W/m2'`, `'nSv/h'`, `'volts'`, `'watts'`, `'dBi'`, `'dB'`, `'S_units'`, `'count'`, `'raw'`, `'disputed_knots_or_mph'` | **required**             |
| `raw`   | Latin-1 byte string or null                                                                                                                                                                                                                                                                            | optional; default `null` |

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

| Field    | JSON value / allowed values                           | Presence / default       |
| -------- | ----------------------------------------------------- | ------------------------ |
| `type`   | `"timestamp"`                                         | see [Tags](#tags)        |
| `kind`   | `'dhm_utc'`, `'dhm_local'`, `'hms_utc'`, `'mdhm_utc'` | **required**             |
| `hour`   | integer                                               | **required**             |
| `minute` | integer                                               | **required**             |
| `day`    | integer or null                                       | optional; default `null` |
| `second` | integer or null                                       | optional; default `null` |
| `month`  | integer or null                                       | optional; default `null` |
| `raw`    | Latin-1 byte string or null                           | optional; default `null` |

### Coordinates

Standalone tag: `coordinates`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "coordinates",
  "latitude_deg": 49,
  "longitude_deg": -72
}
```

| Field           | JSON value / allowed values | Presence / default |
| --------------- | --------------------------- | ------------------ |
| `type`          | `"coordinates"`             | see [Tags](#tags)  |
| `latitude_deg`  | finite number               | **required**       |
| `longitude_deg` | finite number               | **required**       |

### Symbol

Standalone tag: `symbol`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "symbol",
  "table_id": "a",
  "code": ">"
}
```

| Field      | JSON value / allowed values | Presence / default |
| ---------- | --------------------------- | ------------------ |
| `type`     | `"symbol"`                  | see [Tags](#tags)  |
| `table_id` | string                      | **required**       |
| `code`     | string                      | **required**       |

### Grid

Standalone tag: `grid`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "grid",
  "locator": "IO91SX"
}
```

| Field     | JSON value / allowed values | Presence / default |
| --------- | --------------------------- | ------------------ |
| `type`    | `"grid"`                    | see [Tags](#tags)  |
| `locator` | string                      | **required**       |

### Motion

Standalone tag: `motion`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "motion",
  "course_deg": 360,
  "speed_knots": 12,
  "zero_pair": "unspecified",
  "course_code": 360,
  "speed_code": 12,
  "raw": "360/012"
}
```

| Field         | JSON value / allowed values                               | Presence / default                |
| ------------- | --------------------------------------------------------- | --------------------------------- |
| `type`        | `"motion"`                                                | see [Tags](#tags)                 |
| `course_deg`  | finite number or null                                     | optional; default `null`          |
| `speed_knots` | finite number or null                                     | optional; default `null`          |
| `zero_pair`   | `'unavailable'`, `'fixed'`, `'measured'`, `'unspecified'` | optional; default `'unspecified'` |
| `course_code` | integer or null                                           | optional; default `null`          |
| `speed_code`  | integer or null                                           | optional; default `null`          |
| `raw`         | Latin-1 byte string or null                               | optional; default `null`          |

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

| Field         | JSON value / allowed values                             | Presence / default                |
| ------------- | ------------------------------------------------------- | --------------------------------- |
| `type`        | `"altitude"`                                            | see [Tags](#tags)                 |
| `measurement` | [Measurement](#measurement)                             | **required**                      |
| `encoding`    | `'feet_extension'`, `'compressed'`, `'mic_e'`, `'nmea'` | **required**                      |
| `reference`   | `'unspecified'`, `'MSL'`, `'ellipsoid'`                 | optional; default `'unspecified'` |

### Range

Standalone tag: `range`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "range",
  "miles": 12,
  "raw": null
}
```

| Field   | JSON value / allowed values | Presence / default       |
| ------- | --------------------------- | ------------------------ |
| `type`  | `"range"`                   | see [Tags](#tags)        |
| `miles` | finite number               | **required**             |
| `raw`   | Latin-1 byte string or null | optional; default `null` |

### PHG

Standalone tag: `phg`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "phg",
  "power_w": 25,
  "height_haat_ft": 80,
  "gain_dbi": 3,
  "directivity_deg": null,
  "rate_per_hour": null,
  "raw": null
}
```

| Field             | JSON value / allowed values | Presence / default       |
| ----------------- | --------------------------- | ------------------------ |
| `type`            | `"phg"`                     | see [Tags](#tags)        |
| `power_w`         | finite number               | **required**             |
| `height_haat_ft`  | finite number               | **required**             |
| `gain_dbi`        | finite number               | **required**             |
| `directivity_deg` | finite number or null       | optional; default `null` |
| `rate_per_hour`   | integer or null             | optional; default `null` |
| `raw`             | Latin-1 byte string or null | optional; default `null` |

### Signal

Standalone tag: `signal`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "signal",
  "s_units": 5,
  "height_haat_ft": 80,
  "gain_db": 3,
  "directivity_deg": null,
  "raw": null
}
```

| Field             | JSON value / allowed values | Presence / default       |
| ----------------- | --------------------------- | ------------------------ |
| `type`            | `"signal"`                  | see [Tags](#tags)        |
| `s_units`         | integer                     | **required**             |
| `height_haat_ft`  | finite number               | **required**             |
| `gain_db`         | finite number               | **required**             |
| `directivity_deg` | finite number or null       | optional; default `null` |
| `raw`             | Latin-1 byte string or null | optional; default `null` |

### Bearing

Standalone tag: `bearing`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "bearing",
  "bearing_deg": 120,
  "hits_code": 3,
  "range_code": 2,
  "quality_code": 7,
  "usable": null,
  "accuracy_less_than_deg": null,
  "raw": null
}
```

| Field                    | JSON value / allowed values | Presence / default       |
| ------------------------ | --------------------------- | ------------------------ |
| `type`                   | `"bearing"`                 | see [Tags](#tags)        |
| `bearing_deg`            | finite number               | **required**             |
| `hits_code`              | integer                     | **required**             |
| `range_code`             | integer                     | **required**             |
| `quality_code`           | integer                     | **required**             |
| `usable`                 | boolean or null             | optional; default `null` |
| `accuracy_less_than_deg` | finite number or null       | optional; default `null` |
| `raw`                    | Latin-1 byte string or null | optional; default `null` |

### Compression

Standalone tag: `compression`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "compression",
  "fix": "old",
  "nmea_source": "other",
  "origin_code": 0,
  "ignored": false,
  "raw": null
}
```

| Field         | JSON value / allowed values                  | Presence / default        |
| ------------- | -------------------------------------------- | ------------------------- |
| `type`        | `"compression"`                              | see [Tags](#tags)         |
| `fix`         | `'old'`, `'current'` or null                 | optional; default `null`  |
| `nmea_source` | `'other'`, `'GLL'`, `'GGA'`, `'RMC'` or null | optional; default `null`  |
| `origin_code` | integer or null                              | optional; default `null`  |
| `ignored`     | boolean                                      | optional; default `false` |
| `raw`         | Latin-1 byte string or null                  | optional; default `null`  |

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

| Field                 | JSON value / allowed values     | Presence / default       |
| --------------------- | ------------------------------- | ------------------------ |
| `type`                | `"dao"`                         | see [Tags](#tags)        |
| `datum_byte`          | string                          | **required**             |
| `latitude_precision`  | integer or null                 | optional; default `null` |
| `longitude_precision` | integer or null                 | optional; default `null` |
| `encoding`            | `'decimal'`, `'base91'` or null | optional; default `null` |
| `raw`                 | Latin-1 byte string or null     | optional; default `null` |

### Area

Standalone tag: `area`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "area",
  "shape_code": 0,
  "color_code": 3,
  "latitude_offset_code": 10,
  "longitude_offset_code": 10,
  "corridor_half_width_miles": null
}
```

| Field                       | JSON value / allowed values | Presence / default       |
| --------------------------- | --------------------------- | ------------------------ |
| `type`                      | `"area"`                    | see [Tags](#tags)        |
| `shape_code`                | integer                     | **required**             |
| `color_code`                | integer                     | **required**             |
| `latitude_offset_code`      | integer                     | **required**             |
| `longitude_offset_code`     | integer                     | **required**             |
| `corridor_half_width_miles` | finite number or null       | optional; default `null` |

### Signpost

Standalone tag: `signpost`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "signpost",
  "label": "55"
}
```

| Field   | JSON value / allowed values | Presence / default |
| ------- | --------------------------- | ------------------ |
| `type`  | `"signpost"`                | see [Tags](#tags)  |
| `label` | string                      | **required**       |

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

| Field             | JSON value / allowed values | Presence / default       |
| ----------------- | --------------------------- | ------------------------ |
| `type`            | `"water_height"`            | see [Tags](#tags)        |
| `measurement`     | [Measurement](#measurement) | **required**             |
| `reference_datum` | string or null              | optional; default `null` |

### Weather

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
  "gust": {
    "value": 15,
    "unit": "mph",
    "raw": null
  },
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
  "radiation": null,
  "battery_voltage": null,
  "software_code": null,
  "device_code": null,
  "timestamp": {
    "kind": "mdhm_utc",
    "hour": 12,
    "minute": 30,
    "day": 17,
    "second": null,
    "month": 10,
    "raw": null
  },
  "comment": "",
  "raw": null
}
```

| Field                 | JSON value / allowed values         | Presence / default       |
| --------------------- | ----------------------------------- | ------------------------ |
| `type`                | `"weather"`                         | see [Tags](#tags)        |
| `wind_direction`      | [Measurement](#measurement) or null | optional; default `null` |
| `wind_speed`          | [Measurement](#measurement) or null | optional; default `null` |
| `gust`                | [Measurement](#measurement) or null | optional; default `null` |
| `temperature`         | [Measurement](#measurement) or null | optional; default `null` |
| `humidity`            | [Measurement](#measurement) or null | optional; default `null` |
| `pressure`            | [Measurement](#measurement) or null | optional; default `null` |
| `rain_1h`             | [Measurement](#measurement) or null | optional; default `null` |
| `rain_24h`            | [Measurement](#measurement) or null | optional; default `null` |
| `rain_since_midnight` | [Measurement](#measurement) or null | optional; default `null` |
| `snow_24h`            | [Measurement](#measurement) or null | optional; default `null` |
| `luminosity`          | [Measurement](#measurement) or null | optional; default `null` |
| `rain_counter`        | [Measurement](#measurement) or null | optional; default `null` |
| `water_height`        | [WaterHeight](#waterheight) or null | optional; default `null` |
| `radiation`           | [Measurement](#measurement) or null | optional; default `null` |
| `battery_voltage`     | [Measurement](#measurement) or null | optional; default `null` |
| `software_code`       | string or null                      | optional; default `null` |
| `device_code`         | string or null                      | optional; default `null` |
| `timestamp`           | [Timestamp](#timestamp) or null     | optional; default `null` |
| `comment`             | string                              | optional; default `""`   |
| `raw`                 | Latin-1 byte string or null         | optional; default `null` |

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

| Field                      | JSON value / allowed values | Presence / default       |
| -------------------------- | --------------------------- | ------------------------ |
| `type`                     | `"storm"`                   | see [Tags](#tags)        |
| `kind`                     | `'HC'`, `'TS'`, `'TD'`      | **required**             |
| `predicted`                | boolean                     | **required**             |
| `sustained_wind_knots`     | finite number               | **required**             |
| `peak_gust_knots`          | finite number               | **required**             |
| `central_pressure_hpa`     | finite number               | **required**             |
| `hurricane_radius_nm`      | finite number               | **required**             |
| `tropical_storm_radius_nm` | finite number               | **required**             |
| `whole_gale_radius_nm`     | finite number or null       | optional; default `null` |
| `raw`                      | Latin-1 byte string or null | optional; default `null` |

### Telemetry

Standalone tag: `telemetry`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "telemetry",
  "analog": [1, 2, 3, 4, 5],
  "digital": [true, true, true, true, true, true, true, true],
  "sequence": 1,
  "encoding": "classic",
  "comment": "",
  "sequence_raw": null,
  "raw": null
}
```

| Field          | JSON value / allowed values                                      | Presence / default            |
| -------------- | ---------------------------------------------------------------- | ----------------------------- |
| `type`         | `"telemetry"`                                                    | see [Tags](#tags)             |
| `analog`       | array of finite number or null                                   | optional; default `[]`        |
| `digital`      | array of boolean or null                                         | optional; default `[]`        |
| `sequence`     | integer or `'MIC'` or null                                       | optional; default `null`      |
| `encoding`     | `'classic'`, `'mic_e_hex'`, `'mic_e_binary'`, `'base91_comment'` | optional; default `'classic'` |
| `comment`      | string                                                           | optional; default `""`        |
| `sequence_raw` | Latin-1 byte string or null                                      | optional; default `null`      |
| `raw`          | Latin-1 byte string or null                                      | optional; default `null`      |

### Extensions

Standalone tag: `extensions`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "extensions",
  "motion": null,
  "altitude": null,
  "phg": null,
  "range": null,
  "signal": null,
  "bearing": null,
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
    "radiation": null,
    "battery_voltage": null,
    "software_code": null,
    "device_code": null,
    "timestamp": null,
    "comment": "",
    "raw": null
  },
  "storm": null,
  "telemetry": null
}
```

| Field       | JSON value / allowed values     | Presence / default       |
| ----------- | ------------------------------- | ------------------------ |
| `type`      | `"extensions"`                  | see [Tags](#tags)        |
| `motion`    | [Motion](#motion) or null       | optional; default `null` |
| `altitude`  | [Altitude](#altitude) or null   | optional; default `null` |
| `phg`       | [PHG](#phg) or null             | optional; default `null` |
| `range`     | [Range](#range) or null         | optional; default `null` |
| `signal`    | [Signal](#signal) or null       | optional; default `null` |
| `bearing`   | [Bearing](#bearing) or null     | optional; default `null` |
| `dao`       | [DAO](#dao) or null             | optional; default `null` |
| `area`      | [Area](#area) or null           | optional; default `null` |
| `signpost`  | [Signpost](#signpost) or null   | optional; default `null` |
| `weather`   | [Weather](#weather) or null     | optional; default `null` |
| `storm`     | [Storm](#storm) or null         | optional; default `null` |
| `telemetry` | [Telemetry](#telemetry) or null | optional; default `null` |

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

| Field         | JSON value / allowed values | Presence / default       |
| ------------- | --------------------------- | ------------------------ |
| `type`        | `"beam"`                    | see [Tags](#tags)        |
| `heading_deg` | finite number               | **required**             |
| `erp_w`       | finite number               | **required**             |
| `raw`         | Latin-1 byte string or null | optional; default `null` |

### TelemetryParameters

Standalone tag: `telemetry_parameters`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "telemetry_parameters",
  "channels": ["Temp", null, "Volts"]
}
```

| Field      | JSON value / allowed values | Presence / default |
| ---------- | --------------------------- | ------------------ |
| `type`     | `"telemetry_parameters"`    | see [Tags](#tags)  |
| `channels` | array of string or null     | **required**       |

### TelemetryUnits

Standalone tag: `telemetry_units`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "telemetry_units",
  "channels": ["deg.C", null, "V"]
}
```

| Field      | JSON value / allowed values | Presence / default |
| ---------- | --------------------------- | ------------------ |
| `type`     | `"telemetry_units"`         | see [Tags](#tags)  |
| `channels` | array of string or null     | **required**       |

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

| Field  | JSON value / allowed values | Presence / default |
| ------ | --------------------------- | ------------------ |
| `type` | `"calibration"`             | see [Tags](#tags)  |
| `a`    | finite number               | **required**       |
| `b`    | finite number               | **required**       |
| `c`    | finite number               | **required**       |

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

| Field          | JSON value / allowed values                  | Presence / default |
| -------------- | -------------------------------------------- | ------------------ |
| `type`         | `"telemetry_equations"`                      | see [Tags](#tags)  |
| `coefficients` | array of [Calibration](#calibration) or null | **required**       |

### TelemetryBits

Standalone tag: `telemetry_bits`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "telemetry_bits",
  "sense": [true, true, true, true, true, true, true, true],
  "project_title": "Project"
}
```

| Field           | JSON value / allowed values                                                                      | Presence / default     |
| --------------- | ------------------------------------------------------------------------------------------------ | ---------------------- |
| `type`          | `"telemetry_bits"`                                                                               | see [Tags](#tags)      |
| `sense`         | array of exactly 8 items: boolean, boolean, boolean, boolean, boolean, boolean, boolean, boolean | **required**           |
| `project_title` | string                                                                                           | optional; default `""` |

### NTSHeader

Standalone tag: `nts_header`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nts_header",
  "number": "12",
  "precedence": "R",
  "originator": "N0CALL",
  "check": "5",
  "place": "REDMOND WA",
  "date": "OCT 15",
  "handling": "HXA",
  "time": "1800"
}
```

| Field        | JSON value / allowed values | Presence / default       |
| ------------ | --------------------------- | ------------------------ |
| `type`       | `"nts_header"`              | see [Tags](#tags)        |
| `number`     | string                      | **required**             |
| `precedence` | string                      | **required**             |
| `originator` | string                      | **required**             |
| `check`      | string                      | **required**             |
| `place`      | string                      | **required**             |
| `date`       | string                      | **required**             |
| `handling`   | string or null              | optional; default `null` |
| `time`       | string or null              | optional; default `null` |

### NTSAddress

Standalone tag: `nts_address`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nts_address",
  "lines": ["ADAM", "123 MAIN ST", "REDMOND WA", "98052"]
}
```

| Field   | JSON value / allowed values                              | Presence / default |
| ------- | -------------------------------------------------------- | ------------------ |
| `type`  | `"nts_address"`                                          | see [Tags](#tags)  |
| `lines` | array of exactly 4 items: string, string, string, string | **required**       |

### NTSPhone

Standalone tag: `nts_phone`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nts_phone",
  "number": "5550100"
}
```

| Field    | JSON value / allowed values | Presence / default |
| -------- | --------------------------- | ------------------ |
| `type`   | `"nts_phone"`               | see [Tags](#tags)  |
| `number` | string                      | **required**       |

### NTSText

Standalone tag: `nts_text`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nts_text",
  "line": 1,
  "text": "Hello"
}
```

| Field  | JSON value / allowed values  | Presence / default |
| ------ | ---------------------------- | ------------------ |
| `type` | `"nts_text"`                 | see [Tags](#tags)  |
| `line` | `1`, `2`, `3`, `4`, `5`, `6` | **required**       |
| `text` | string                       | **required**       |

### NTSSignature

Standalone tag: `nts_signature`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "nts_signature",
  "text": "N0CALL"
}
```

| Field  | JSON value / allowed values | Presence / default |
| ------ | --------------------------- | ------------------ |
| `type` | `"nts_signature"`           | see [Tags](#tags)  |
| `text` | string                      | **required**       |

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

| Field           | JSON value / allowed values | Presence / default |
| --------------- | --------------------------- | ------------------ |
| `type`          | `"nts_routing"`             | see [Tags](#tags)  |
| `received_from` | string                      | **required**       |
| `received_at`   | string                      | **required**       |
| `sent_to`       | string                      | **required**       |
| `sent_at`       | string                      | **required**       |

### Footprint

Standalone tag: `footprint`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "footprint",
  "center": {
    "latitude_deg": 49,
    "longitude_deg": -72
  },
  "radius_miles": 20
}
```

| Field          | JSON value / allowed values | Presence / default |
| -------------- | --------------------------- | ------------------ |
| `type`         | `"footprint"`               | see [Tags](#tags)  |
| `center`       | [Coordinates](#coordinates) | **required**       |
| `radius_miles` | finite number               | **required**       |

### Capability

Standalone tag: `capability`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "capability",
  "name": "MSG_CNT",
  "value": "43"
}
```

| Field   | JSON value / allowed values | Presence / default       |
| ------- | --------------------------- | ------------------------ |
| `type`  | `"capability"`              | see [Tags](#tags)        |
| `name`  | string                      | **required**             |
| `value` | string or null              | optional; default `null` |

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

| Field               | JSON value / allowed values  | Presence / default       |
| ------------------- | ---------------------------- | ------------------------ |
| `type`              | `"nmea_metadata"`            | see [Tags](#tags)        |
| `talker`            | string                       | **required**             |
| `checksum_supplied` | string or null               | optional; default `null` |
| `checksum_valid`    | boolean or null              | optional; default `null` |
| `fields_raw`        | array of Latin-1 byte string | optional; default `[]`   |

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

| Field                | JSON value / allowed values         | Presence / default       |
| -------------------- | ----------------------------------- | ------------------------ |
| `type`               | `"gga"`                             | see [Tags](#tags)        |
| `time_utc`           | string                              | **required**             |
| `coordinates`        | [Coordinates](#coordinates) or null | **required**             |
| `fix_quality`        | integer                             | **required**             |
| `satellites`         | integer or null                     | optional; default `null` |
| `hdop`               | finite number or null               | optional; default `null` |
| `altitude_msl_m`     | finite number or null               | optional; default `null` |
| `geoid_separation_m` | finite number or null               | optional; default `null` |
| `dgps_age`           | string or null                      | optional; default `null` |
| `dgps_station`       | string or null                      | optional; default `null` |

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

| Field         | JSON value / allowed values         | Presence / default |
| ------------- | ----------------------------------- | ------------------ |
| `type`        | `"gll"`                             | see [Tags](#tags)  |
| `coordinates` | [Coordinates](#coordinates) or null | **required**       |
| `time_utc`    | string                              | **required**       |
| `fix_status`  | `'A'`, `'V'`                        | **required**       |

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

| Field                          | JSON value / allowed values         | Presence / default       |
| ------------------------------ | ----------------------------------- | ------------------------ |
| `type`                         | `"rmc"`                             | see [Tags](#tags)        |
| `time_utc`                     | string                              | **required**             |
| `date_ddmmyy`                  | string                              | **required**             |
| `fix_status`                   | `'A'`, `'V'`                        | **required**             |
| `coordinates`                  | [Coordinates](#coordinates) or null | **required**             |
| `speed_knots`                  | finite number or null               | optional; default `null` |
| `course_deg`                   | finite number or null               | optional; default `null` |
| `magnetic_variation`           | finite number or null               | optional; default `null` |
| `magnetic_variation_direction` | `'E'`, `'W'` or null                | optional; default `null` |

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

| Field                 | JSON value / allowed values | Presence / default       |
| --------------------- | --------------------------- | ------------------------ |
| `type`                | `"vtg"`                     | see [Tags](#tags)        |
| `course_true_deg`     | finite number or null       | optional; default `null` |
| `course_magnetic_deg` | finite number or null       | optional; default `null` |
| `speed_knots`         | finite number or null       | optional; default `null` |
| `speed_kmh_reported`  | finite number or null       | optional; default `null` |

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

| Field         | JSON value / allowed values | Presence / default |
| ------------- | --------------------------- | ------------------ |
| `type`        | `"wpl"`                     | see [Tags](#tags)  |
| `coordinates` | [Coordinates](#coordinates) | **required**       |
| `name`        | string                      | **required**       |

### Hop

Standalone tag: `hop`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "hop",
  "address": "WIDE1-1",
  "repeated": false
}
```

| Field      | JSON value / allowed values | Presence / default        |
| ---------- | --------------------------- | ------------------------- |
| `type`     | `"hop"`                     | see [Tags](#tags)         |
| `address`  | string                      | **required**              |
| `repeated` | boolean                     | optional; default `false` |

### Header

Standalone tag: `header`. [Back to type map](#type-map-and-object-catalog).

A missing/null destination is an automatic header template, valid in a Packet only for Mic-E. Other Packet payloads require a destination. Mic-E serialization derives it from semantic fields without mutating the template; explicit addresses are checked.

```json
{
  "type": "header",
  "source": "N0CALL",
  "destination": "APRS",
  "path": []
}
```

| Field         | JSON value / allowed values | Presence / default       |
| ------------- | --------------------------- | ------------------------ |
| `type`        | `"header"`                  | see [Tags](#tags)        |
| `source`      | string                      | **required**             |
| `destination` | string or null              | optional; default `null` |
| `path`        | array of [Hop](#hop)        | optional; default `[]`   |

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
  "comment": "",
  "messaging": false,
  "timestamp": null,
  "ambiguity": 0,
  "compression": null,
  "extensions": {
    "motion": null,
    "altitude": null,
    "phg": null,
    "range": null,
    "signal": null,
    "bearing": null,
    "dao": null,
    "area": null,
    "signpost": null,
    "weather": null,
    "storm": null,
    "telemetry": null
  }
}
```

| Field           | JSON value / allowed values         | Presence / default                                            |
| --------------- | ----------------------------------- | ------------------------------------------------------------- |
| `type`          | `"position"`                        | see [Tags](#tags)                                             |
| `latitude_deg`  | finite number                       | **required**                                                  |
| `longitude_deg` | finite number                       | **required**                                                  |
| `symbol`        | [Symbol](#symbol)                   | **required**                                                  |
| `comment`       | string                              | optional; default `""`                                        |
| `messaging`     | boolean                             | optional; default `false`                                     |
| `timestamp`     | [Timestamp](#timestamp) or null     | optional; default `null`                                      |
| `ambiguity`     | integer                             | optional; default `0`                                         |
| `compression`   | [Compression](#compression) or null | optional; default `null`                                      |
| `extensions`    | [Extensions](#extensions)           | optional; default [Extensions](#extensions) with its defaults |

### MicE

Standalone tag: `mic_e`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "mic_e",
  "latitude_deg": 49,
  "longitude_deg": -72,
  "symbol": {
    "table_id": "/",
    "code": ">"
  },
  "message": "en_route",
  "comment": "",
  "fix": "current",
  "ambiguity": 0,
  "device_code": null,
  "extensions": {
    "motion": {
      "course_deg": 90,
      "speed_knots": 10,
      "zero_pair": "unspecified",
      "course_code": null,
      "speed_code": null,
      "raw": null
    },
    "altitude": null,
    "phg": null,
    "range": null,
    "signal": null,
    "bearing": null,
    "dao": null,
    "area": null,
    "signpost": null,
    "weather": null,
    "storm": null,
    "telemetry": null
  }
}
```

| Field           | JSON value / allowed values                                                                                                                                                                                                       | Presence / default                                            |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `type`          | `"mic_e"`                                                                                                                                                                                                                         | see [Tags](#tags)                                             |
| `latitude_deg`  | finite number                                                                                                                                                                                                                     | **required**                                                  |
| `longitude_deg` | finite number                                                                                                                                                                                                                     | **required**                                                  |
| `symbol`        | [Symbol](#symbol)                                                                                                                                                                                                                 | **required**                                                  |
| `message`       | `'off_duty'`, `'en_route'`, `'in_service'`, `'returning'`, `'committed'`, `'special'`, `'priority'`, `'custom_0'`, `'custom_1'`, `'custom_2'`, `'custom_3'`, `'custom_4'`, `'custom_5'`, `'custom_6'`, `'emergency'`, `'unknown'` | **required**                                                  |
| `comment`       | string                                                                                                                                                                                                                            | optional; default `""`                                        |
| `fix`           | `'current'`, `'old'`                                                                                                                                                                                                              | optional; default `'current'`                                 |
| `ambiguity`     | integer                                                                                                                                                                                                                           | optional; default `0`                                         |
| `device_code`   | string or null                                                                                                                                                                                                                    | optional; default `null`                                      |
| `extensions`    | [Extensions](#extensions)                                                                                                                                                                                                         | optional; default [Extensions](#extensions) with its defaults |

### Object

Standalone tag: `object`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "object",
  "name": "AID #2",
  "latitude_deg": 49,
  "longitude_deg": -72,
  "symbol": {
    "table_id": "/",
    "code": "-"
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
  "comment": "",
  "alive": false,
  "ambiguity": 0,
  "compression": null,
  "extensions": {
    "motion": null,
    "altitude": null,
    "phg": null,
    "range": null,
    "signal": null,
    "bearing": null,
    "dao": null,
    "area": null,
    "signpost": null,
    "weather": null,
    "storm": null,
    "telemetry": null
  }
}
```

| Field           | JSON value / allowed values         | Presence / default                                            |
| --------------- | ----------------------------------- | ------------------------------------------------------------- |
| `type`          | `"object"`                          | see [Tags](#tags)                                             |
| `name`          | string                              | **required**                                                  |
| `latitude_deg`  | finite number                       | **required**                                                  |
| `longitude_deg` | finite number                       | **required**                                                  |
| `symbol`        | [Symbol](#symbol)                   | **required**                                                  |
| `timestamp`     | [Timestamp](#timestamp)             | **required**                                                  |
| `comment`       | string                              | optional; default `""`                                        |
| `alive`         | boolean                             | optional; default `true`                                      |
| `ambiguity`     | integer                             | optional; default `0`                                         |
| `compression`   | [Compression](#compression) or null | optional; default `null`                                      |
| `extensions`    | [Extensions](#extensions)           | optional; default [Extensions](#extensions) with its defaults |

### Item

Standalone tag: `item`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "item",
  "name": "abc",
  "latitude_deg": 49,
  "longitude_deg": -72,
  "symbol": {
    "table_id": "/",
    "code": "-"
  },
  "comment": "",
  "alive": false,
  "ambiguity": 0,
  "compression": null,
  "extensions": {
    "motion": null,
    "altitude": null,
    "phg": null,
    "range": null,
    "signal": null,
    "bearing": null,
    "dao": null,
    "area": null,
    "signpost": null,
    "weather": null,
    "storm": null,
    "telemetry": null
  }
}
```

| Field           | JSON value / allowed values         | Presence / default                                            |
| --------------- | ----------------------------------- | ------------------------------------------------------------- |
| `type`          | `"item"`                            | see [Tags](#tags)                                             |
| `name`          | string                              | **required**                                                  |
| `latitude_deg`  | finite number                       | **required**                                                  |
| `longitude_deg` | finite number                       | **required**                                                  |
| `symbol`        | [Symbol](#symbol)                   | **required**                                                  |
| `comment`       | string                              | optional; default `""`                                        |
| `alive`         | boolean                             | optional; default `true`                                      |
| `ambiguity`     | integer                             | optional; default `0`                                         |
| `compression`   | [Compression](#compression) or null | optional; default `null`                                      |
| `extensions`    | [Extensions](#extensions)           | optional; default [Extensions](#extensions) with its defaults |

### TelemetryDefinition

Standalone tag: `telemetry_definition`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "telemetry_definition",
  "addressee": "N0CALL",
  "definition": {
    "type": "telemetry_parameters",
    "channels": ["Temp"]
  }
}
```

| Field        | JSON value / allowed values                                                                                                                                      | Presence / default |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| `type`       | `"telemetry_definition"`                                                                                                                                         | see [Tags](#tags)  |
| `addressee`  | string                                                                                                                                                           | **required**       |
| `definition` | [TelemetryParameters](#telemetryparameters) or [TelemetryUnits](#telemetryunits) or [TelemetryEquations](#telemetryequations) or [TelemetryBits](#telemetrybits) | **required**       |

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

| Field       | JSON value / allowed values     | Presence / default       |
| ----------- | ------------------------------- | ------------------------ |
| `type`      | `"status"`                      | see [Tags](#tags)        |
| `text`      | string                          | **required**             |
| `timestamp` | [Timestamp](#timestamp) or null | optional; default `null` |
| `grid`      | [Grid](#grid) or null           | optional; default `null` |
| `symbol`    | [Symbol](#symbol) or null       | optional; default `null` |
| `beam`      | [Beam](#beam) or null           | optional; default `null` |

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

| Field        | JSON value / allowed values | Presence / default       |
| ------------ | --------------------------- | ------------------------ |
| `type`       | `"message"`                 | see [Tags](#tags)        |
| `addressee`  | string                      | **required**             |
| `text`       | string                      | **required**             |
| `message_id` | string or null              | optional; default `null` |
| `reply_ack`  | string or null              | optional; default `null` |

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

| Field        | JSON value / allowed values | Presence / default        |
| ------------ | --------------------------- | ------------------------- |
| `type`       | `"acknowledgment"`          | see [Tags](#tags)         |
| `addressee`  | string                      | **required**              |
| `message_id` | string                      | **required**              |
| `rejected`   | boolean                     | optional; default `false` |
| `reply_ack`  | string or null              | optional; default `null`  |

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

| Field          | JSON value / allowed values | Presence / default       |
| -------------- | --------------------------- | ------------------------ |
| `type`         | `"auto_answer"`             | see [Tags](#tags)        |
| `addressee`    | string                      | **required**             |
| `text`         | string                      | **required**             |
| `previous_ack` | string or null              | optional; default `null` |

### Bulletin

Standalone tag: `bulletin`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "bulletin",
  "identifier": "1",
  "text": "Notice",
  "group": "WX"
}
```

| Field        | JSON value / allowed values | Presence / default       |
| ------------ | --------------------------- | ------------------------ |
| `type`       | `"bulletin"`                | see [Tags](#tags)        |
| `identifier` | string                      | **required**             |
| `text`       | string                      | **required**             |
| `group`      | string or null              | optional; default `null` |

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

| Field          | JSON value / allowed values | Presence / default       |
| -------------- | --------------------------- | ------------------------ |
| `type`         | `"nws_bulletin"`            | see [Tags](#tags)        |
| `addressee`    | string                      | **required**             |
| `text`         | string                      | **required**             |
| `reference_id` | string or null              | optional; default `null` |

### Radiogram

Standalone tag: `radiogram`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "radiogram",
  "addressee": "W1AW",
  "record": {
    "type": "nts_text",
    "line": 1,
    "text": "Hello"
  },
  "message_id": "001"
}
```

| Field        | JSON value / allowed values                                                                                                                                        | Presence / default       |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------ |
| `type`       | `"radiogram"`                                                                                                                                                      | see [Tags](#tags)        |
| `addressee`  | string                                                                                                                                                             | **required**             |
| `record`     | [NTSHeader](#ntsheader) or [NTSAddress](#ntsaddress) or [NTSPhone](#ntsphone) or [NTSText](#ntstext) or [NTSSignature](#ntssignature) or [NTSRouting](#ntsrouting) | **required**             |
| `message_id` | string or null                                                                                                                                                     | optional; default `null` |

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
  "arguments": ""
}
```

| Field           | JSON value / allowed values     | Presence / default       |
| --------------- | ------------------------------- | ------------------------ |
| `type`          | `"query"`                       | see [Tags](#tags)        |
| `name`          | string                          | **required**             |
| `addressee`     | string or null                  | optional; default `null` |
| `footprint`     | [Footprint](#footprint) or null | optional; default `null` |
| `heard_station` | string or null                  | optional; default `null` |
| `arguments`     | Latin-1 byte string             | optional; default `""`   |

### DirectStations

Standalone tag: `direct_stations`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "direct_stations",
  "stations": ["W1AW"]
}
```

| Field      | JSON value / allowed values | Presence / default |
| ---------- | --------------------------- | ------------------ |
| `type`     | `"direct_stations"`         | see [Tags](#tags)  |
| `stations` | array of string             | **required**       |

### HeardStation

Standalone tag: `heard_station`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "heard_station",
  "station": "W1AW",
  "counts": [1, null, 3, 0, 0, 0, 0, 0]
}
```

| Field     | JSON value / allowed values | Presence / default |
| --------- | --------------------------- | ------------------ |
| `type`    | `"heard_station"`           | see [Tags](#tags)  |
| `station` | string                      | **required**       |
| `counts`  | array of integer or null    | **required**       |

### Trace

Standalone tag: `trace`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "trace",
  "header": {
    "source": "N0CALL",
    "destination": "APRS",
    "path": []
  }
}
```

| Field    | JSON value / allowed values | Presence / default |
| -------- | --------------------------- | ------------------ |
| `type`   | `"trace"`                   | see [Tags](#tags)  |
| `header` | [Header](#header)           | **required**       |

### Response

Standalone tag: `response`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "response",
  "addressee": "W1AW",
  "response": {
    "type": "direct_stations",
    "stations": ["N0CALL"]
  }
}
```

| Field       | JSON value / allowed values                                                           | Presence / default |
| ----------- | ------------------------------------------------------------------------------------- | ------------------ |
| `type`      | `"response"`                                                                          | see [Tags](#tags)  |
| `addressee` | string                                                                                | **required**       |
| `response`  | [DirectStations](#directstations) or [HeardStation](#heardstation) or [Trace](#trace) | **required**       |

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

| Field    | JSON value / allowed values        | Presence / default |
| -------- | ---------------------------------- | ------------------ |
| `type`   | `"capabilities"`                   | see [Tags](#tags)  |
| `tokens` | array of [Capability](#capability) | **required**       |

### NMEA

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

| Field             | JSON value / allowed values                                             | Presence / default       |
| ----------------- | ----------------------------------------------------------------------- | ------------------------ |
| `type`            | `"nmea"`                                                                | see [Tags](#tags)        |
| `sentence`        | [GGA](#gga) or [GLL](#gll) or [RMC](#rmc) or [VTG](#vtg) or [WPL](#wpl) | **required**             |
| `metadata`        | [NMEAMetadata](#nmeametadata)                                           | **required**             |
| `position_usable` | boolean or null                                                         | optional; default `null` |
| `symbol`          | [Symbol](#symbol) or null                                               | optional; default `null` |
| `comment`         | string                                                                  | optional; default `""`   |

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
    "diagnostics": []
  }
}
```

| Field    | JSON value / allowed values | Presence / default |
| -------- | --------------------------- | ------------------ |
| `type`   | `"third_party"`             | see [Tags](#tags)  |
| `packet` | [Packet](#packet)           | **required**       |

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

| Field       | JSON value / allowed values | Presence / default |
| ----------- | --------------------------- | ------------------ |
| `type`      | `"user_defined"`            | see [Tags](#tags)  |
| `user_id`   | Latin-1 byte string         | **required**       |
| `user_type` | Latin-1 byte string         | **required**       |
| `data`      | Latin-1 byte string         | **required**       |

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

| Field         | JSON value / allowed values                                      | Presence / default       |
| ------------- | ---------------------------------------------------------------- | ------------------------ |
| `type`        | `"raw_weather"`                                                  | see [Tags](#tags)        |
| `format`      | `'ultimeter_ii'`, `'ultimeter_2000'`, `'ultw'`, `'peet_logging'` | **required**             |
| `information` | Latin-1 byte string                                              | **required**             |
| `weather`     | [Weather](#weather) or null                                      | optional; default `null` |

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

| Field          | JSON value / allowed values | Presence / default       |
| -------------- | --------------------------- | ------------------------ |
| `type`         | `"agrelo"`                  | see [Tags](#tags)        |
| `bearing_deg`  | integer                     | **required**             |
| `quality_code` | integer                     | **required**             |
| `raw`          | Latin-1 byte string or null | optional; default `null` |

### Maidenhead

Standalone tag: `maidenhead`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "maidenhead",
  "grid": {
    "locator": "IO91SX"
  },
  "symbol": null,
  "comment": ""
}
```

| Field     | JSON value / allowed values | Presence / default       |
| --------- | --------------------------- | ------------------------ |
| `type`    | `"maidenhead"`              | see [Tags](#tags)        |
| `grid`    | [Grid](#grid)               | **required**             |
| `symbol`  | [Symbol](#symbol) or null   | optional; default `null` |
| `comment` | string                      | optional; default `""`   |

### LegacyPosition

Standalone tag: `legacy_position`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "legacy_position",
  "prefix": "X1J ",
  "position": {
    "latitude_deg": 49,
    "longitude_deg": -72,
    "symbol": {
      "table_id": "/",
      "code": "-"
    },
    "comment": "",
    "messaging": false,
    "timestamp": null,
    "ambiguity": 0,
    "compression": null,
    "extensions": {
      "motion": null,
      "altitude": null,
      "phg": null,
      "range": null,
      "signal": null,
      "bearing": null,
      "dao": null,
      "area": null,
      "signpost": null,
      "weather": null,
      "storm": null,
      "telemetry": null
    }
  }
}
```

| Field      | JSON value / allowed values | Presence / default |
| ---------- | --------------------------- | ------------------ |
| `type`     | `"legacy_position"`         | see [Tags](#tags)  |
| `prefix`   | Latin-1 byte string         | **required**       |
| `position` | [Position](#position)       | **required**       |

### Beacon

Standalone tag: `beacon`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "beacon",
  "text": "UIDIGI ready"
}
```

| Field  | JSON value / allowed values | Presence / default |
| ------ | --------------------------- | ------------------ |
| `type` | `"beacon"`                  | see [Tags](#tags)  |
| `text` | string                      | **required**       |

### Invalid

Standalone tag: `invalid`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "invalid",
  "data": "invalid fix"
}
```

| Field  | JSON value / allowed values | Presence / default |
| ------ | --------------------------- | ------------------ |
| `type` | `"invalid"`                 | see [Tags](#tags)  |
| `data` | Latin-1 byte string         | **required**       |

### Reserved

Standalone tag: `reserved`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "reserved",
  "dti": 38,
  "data": "data"
}
```

| Field  | JSON value / allowed values | Presence / default |
| ------ | --------------------------- | ------------------ |
| `type` | `"reserved"`                | see [Tags](#tags)  |
| `dti`  | integer                     | **required**       |
| `data` | Latin-1 byte string         | **required**       |

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

| Field               | JSON value / allowed values             | Presence / default       |
| ------------------- | --------------------------------------- | ------------------------ |
| `type`              | `"external_extension"`                  | see [Tags](#tags)        |
| `name`              | `'polygon_line'`, `'vendor'`, `'other'` | **required**             |
| `information`       | Latin-1 byte string                     | **required**             |
| `specification_url` | string or null                          | optional; default `null` |

### Diagnostic

Standalone tag: `diagnostic`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "diagnostic",
  "code": "unsupported",
  "message": "codec pending",
  "path": "$"
}
```

| Field     | JSON value / allowed values                       | Presence / default      |
| --------- | ------------------------------------------------- | ----------------------- |
| `type`    | `"diagnostic"`                                    | see [Tags](#tags)       |
| `code`    | `'unsupported'`, `'malformed'`, `'nonconforming'` | **required**            |
| `message` | string                                            | **required**            |
| `path`    | string                                            | optional; default `'$'` |

### Opaque

Standalone tag: `opaque`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "opaque",
  "information": "~\u00ff\r\n",
  "diagnostic": null
}
```

| Field         | JSON value / allowed values       | Presence / default       |
| ------------- | --------------------------------- | ------------------------ |
| `type`        | `"opaque"`                        | see [Tags](#tags)        |
| `information` | Latin-1 byte string               | **required**             |
| `diagnostic`  | [Diagnostic](#diagnostic) or null | optional; default `null` |

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
    "comment": "Hello",
    "messaging": false,
    "timestamp": null,
    "ambiguity": 0,
    "compression": null,
    "extensions": {
      "motion": null,
      "altitude": null,
      "phg": null,
      "range": null,
      "signal": null,
      "bearing": null,
      "dao": null,
      "area": null,
      "signpost": null,
      "weather": null,
      "storm": null,
      "telemetry": null
    }
  },
  "original_wire": "N0CALL>APRS:!4903.50N/07201.75W>Hello",
  "diagnostics": []
}
```

| Field           | JSON value / allowed values                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Presence / default       |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| `type`          | `"packet"`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | see [Tags](#tags)        |
| `header`        | [Header](#header)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | **required**             |
| `payload`       | [Position](#position) or [MicE](#mice) or [Object](#object) or [Item](#item) or [Weather](#weather) or [Telemetry](#telemetry) or [TelemetryDefinition](#telemetrydefinition) or [Status](#status) or [Message](#message) or [Acknowledgment](#acknowledgment) or [AutoAnswer](#autoanswer) or [Bulletin](#bulletin) or [NWSBulletin](#nwsbulletin) or [Radiogram](#radiogram) or [Query](#query) or [Response](#response) or [Capabilities](#capabilities) or [NMEA](#nmea) or [ThirdParty](#thirdparty) or [UserDefined](#userdefined) or [RawWeather](#rawweather) or [Agrelo](#agrelo) or [Maidenhead](#maidenhead) or [LegacyPosition](#legacyposition) or [Beacon](#beacon) or [Invalid](#invalid) or [Reserved](#reserved) or [ExternalExtension](#externalextension) or [Opaque](#opaque) | **required**             |
| `original_wire` | Latin-1 byte string or null                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | optional; default `null` |
| `diagnostics`   | array of [Diagnostic](#diagnostic)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | optional; default `[]`   |

### Malformed

Standalone tag: `malformed`. [Back to type map](#type-map-and-object-catalog).

```json
{
  "type": "malformed",
  "original_wire": "N0CALL>APRS:!4903.50N",
  "diagnostics": [
    {
      "code": "malformed",
      "message": "missing longitude",
      "path": "$.payload.longitude_deg"
    }
  ],
  "recovered": {
    "type": "packet",
    "header": {
      "source": "N0CALL",
      "destination": "APRS"
    },
    "payload": {
      "type": "position",
      "latitude_deg": 49.05833333333333
    }
  }
}
```

| Field           | JSON value / allowed values         | Presence / default |
| --------------- | ----------------------------------- | ------------------ |
| `type`          | `"malformed"`                       | see [Tags](#tags)  |
| `original_wire` | Latin-1 byte string                 | **required**       |
| `diagnostics`   | array of [Diagnostic](#diagnostic)  | **required**       |
| `recovered`     | `<class 'str'>`, `<class 'object'>` | **required**       |

## Nested union examples

Each allowed member is shown in its actual container, where it carries its tag.

### TelemetryDefinition with TelemetryParameters

```json
{
  "type": "telemetry_definition",
  "addressee": "N0CALL",
  "definition": {
    "type": "telemetry_parameters",
    "channels": ["Temp", null, "Volts"]
  }
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
  }
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
  }
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
  }
}
```

### NMEA with GGA

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

### NMEA with GLL

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

### NMEA with RMC

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

### NMEA with VTG

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

### NMEA with WPL

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

### Radiogram with NTSHeader

```json
{
  "type": "radiogram",
  "addressee": "W1AW",
  "record": {
    "type": "nts_header",
    "number": "12",
    "precedence": "R",
    "originator": "N0CALL",
    "check": "5",
    "place": "REDMOND WA",
    "date": "OCT 15",
    "handling": "HXA",
    "time": "1800"
  },
  "message_id": null
}
```

### Radiogram with NTSAddress

```json
{
  "type": "radiogram",
  "addressee": "W1AW",
  "record": {
    "type": "nts_address",
    "lines": ["ADAM", "123 MAIN ST", "REDMOND WA", "98052"]
  },
  "message_id": null
}
```

### Radiogram with NTSPhone

```json
{
  "type": "radiogram",
  "addressee": "W1AW",
  "record": {
    "type": "nts_phone",
    "number": "5550100"
  },
  "message_id": null
}
```

### Radiogram with NTSText

```json
{
  "type": "radiogram",
  "addressee": "W1AW",
  "record": {
    "type": "nts_text",
    "line": 1,
    "text": "Hello"
  },
  "message_id": null
}
```

### Radiogram with NTSSignature

```json
{
  "type": "radiogram",
  "addressee": "W1AW",
  "record": {
    "type": "nts_signature",
    "text": "N0CALL"
  },
  "message_id": null
}
```

### Radiogram with NTSRouting

```json
{
  "type": "radiogram",
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

### Response with DirectStations

```json
{
  "type": "response",
  "addressee": "W1AW",
  "response": {
    "type": "direct_stations",
    "stations": ["W1AW"]
  }
}
```

### Response with HeardStation

```json
{
  "type": "response",
  "addressee": "W1AW",
  "response": {
    "type": "heard_station",
    "station": "W1AW",
    "counts": [1, null, 3, 0, 0, 0, 0, 0]
  }
}
```

### Response with Trace

```json
{
  "type": "response",
  "addressee": "W1AW",
  "response": {
    "type": "trace",
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
    "gust": {
      "value": 15,
      "unit": "mph",
      "raw": null
    },
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
    "radiation": null,
    "battery_voltage": null,
    "software_code": null,
    "device_code": null,
    "timestamp": {
      "kind": "mdhm_utc",
      "hour": 12,
      "minute": 30,
      "day": 17,
      "second": null,
      "month": 10,
      "raw": null
    },
    "comment": "",
    "raw": null
  },
  "original_wire": null,
  "diagnostics": []
}
```

## Regeneration and validation

Run `python packages/aprs/tests/generate_json_reference.py` from the repository
root with the package installed, then run the repository formatting hooks.
`test_json_reference.py` checks every JSON example against the models, verifies
round trips including raw metadata, and checks catalog coverage against the full
public JSONModel union. This prevents examples from silently diverging from code.
Codec support metadata (`CodecSupport`) and `Extent`, which only properties
return, are not JSON data models.
