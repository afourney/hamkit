# JSON model format

The four public APIs in `hamkit.aprs` are `to_json`, `from_json`, `to_json_dict`
and `from_json_dict`. Public annotation aliases are `JSONModel` (84 concrete
APRS value classes), `JSONObject` and recursive `JSONValue`. Every payload in
`Payload`, complete/nested packets, header annotations, encoded packet fields,
codec options and all shared/NMEA field classes are supported. `CodecCapability`
is runtime introspection metadata containing a Python class reference, not a
packet/field value; it is deliberately excluded. Arbitrary dataclasses/classes
are not instantiated from input.

## Inference contract

There is no `type`, `__type__`, class name, or other synthetic model tag. The
schema uses domain field names. Most names match Python attributes; aliases
below distinguish fields with different roles that happened to share Python
names (for example, status text and non-APRS beacon text). Do not send both an
alias and the original spelling; unknown/conflicting fields are errors.

Inference is independent of JSON key order. At a root or a union-valued field:

1. Limit candidates to the registered domain classes (or the declared union).
2. Require all candidate signature keys below and reject any unknown keys.
3. Require exactly one candidate; then validate each value's declared type.
4. If the shape is ambiguous or incomplete, reject it. Do not choose by
   registration order, coerce strings to numbers, or try another class after
   validation fails.

The signatures are part of the JSON schema. They include Python required fields
plus a few meaningful default fields needed to make canonical output inferable.
For example, a bare latitude/longitude pair is `Coordinates`; a `Location` also
includes `symbol`; a station `Position` includes `messaging` even when false.
These are actual semantic fields, not redundant class labels. A bare `{"weather": {}}` is a `WeatherReport` in this schema; a standalone `Extensions` includes its
`motion` field. To read an intentionally sparse object of a specific class, pass
`expected_type=Location`, `expected_type=Extensions`, etc. A single, declared
nested type also supplies this context. Required constructor fields, aliases,
unknown-key rejection and value checks still apply in that mode.

`from_json(..., expected_type=Packet)` has return type `Packet`; without this
argument the return type is `JSONModel`. The expected type must be a supported
concrete class, not `Payload` or an arbitrary custom type. Unknown keys fail
rather than being retained in a catch-all dictionary.

## Values, defaults and bytes

- Dataclasses map to JSON objects; tuples map to arrays and recover as tuples.
  Fixed tuples require the exact length. Literal enum choices remain their JSON
  string/integer values and are validated with their exact scalar type.
- Booleans are not accepted as integers/numbers. Integers stay integers;
  float-annotated fields accept finite JSON integers or floats. No numeric
  strings, NaN, Infinity, or out-of-range floating-point values are accepted.
- Every bytes-annotated field uses a Latin-1 JSON string: one code point U+0000
  through U+00FF per byte. This is a reversible carrier, **not UTF-8 text**.
  `to_json` escapes all non-ASCII/control characters, including binary CR/LF.
  Unicode above U+00FF is rejected in byte fields; ordinary `str` fields retain
  Unicode. No tagged byte objects or heuristic base64 detection are used.
- Default compact output omits optional fields equal to their Python defaults,
  except signature fields. Required values (including required nulls) remain.
  `include_defaults=True` emits all fields. Empty bytes and tuples are `""` and
  `[]`, not null. Null is accepted only where the annotation allows it.
- Missing optional fields get their dataclass defaults. An explicit null for a
  nullable optional field normalizes to `None`. The models do not remember
  whether the original document omitted that field; JSON reserialization does
  not pretend to preserve that history. Missing required fields always fail,
  even if their annotation permits null.
- Weather field `None` means absent. A present `Measurement(value=None, unit=...)`
  means transmitted but unavailable. A zero-valued measurement remains distinct.
- `Packet.original_wire`, `header_semantics`, `Opaque.reason`/`diagnostic` and
  other raw evidence survive conversion even where dataclass equality ignores
  them. They are evidence, not authoritative overrides for edited fields.

These conversions validate the Python data shape and field types; they do not
invoke APRS encoders, quantize coordinates, resolve timestamps or validate all
wire ranges and mutually exclusive field combinations. A model with an
unimplemented wire codec is still fully JSON serializable. `validate_packet`
remains the separate wire-encodability check. JSON cannot convert invalid input
into a claim of a trusted position or transmission permission.

## Errors and limits

`JSONModelError` derives from `APRSError`/`ValueError`.
`AmbiguousJSONError` identifies insufficient evidence among multiple shapes.
Duplicate keys (including nested duplicates), malformed JSON, unknown fields,
conflicting family fields, incorrect nulls/types/enums and nonfinite numbers are
rejected. Wrong expected classes are rejected; there is no dynamic class loading.

`max_depth` defaults to 64, accepts 1–128, and bounds recursive object/array/value
conversion independently of the wire codec's third-party-wrapper limit. Cyclic
model graphs and excessive parser nesting raise clean errors. This is a depth
bound, not a byte-size limit; applications handling untrusted large documents
should enforce their own input-size budget.

## Complete shape table

Every other Python attribute keeps its name. The signature column lists keys
needed for untyped inference, not every allowed optional key. A declared nested
type or `expected_type` permits omission of defaulted signature fields. All
constructor-required fields still remain required.

| Python model          | Attribute → JSON aliases           | Inference signature                                                                                                                                 |
| --------------------- | ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Measurement`         | —                                  | `unit`, `value`                                                                                                                                     |
| `Timestamp`           | `kind` → `timestamp_format`        | `hour`, `minute`, `timestamp_format`                                                                                                                |
| `Coordinates`         | —                                  | `latitude_deg`, `longitude_deg`                                                                                                                     |
| `CellBounds`          | —                                  | `latitude`, `longitude`                                                                                                                             |
| `Ambiguity`           | `digits` → `ambiguity_digits`      | `ambiguity_digits`                                                                                                                                  |
| `Symbol`              | —                                  | `code`, `table_id`                                                                                                                                  |
| `GridLocator`         | —                                  | `locator`                                                                                                                                           |
| `Motion`              | —                                  | `course_deg`                                                                                                                                        |
| `Altitude`            | —                                  | `encoding`, `measurement`                                                                                                                           |
| `RadioRange`          | —                                  | `miles`                                                                                                                                             |
| `PHG`                 | —                                  | `gain_dbi`, `height_haat_ft`, `power_w`                                                                                                             |
| `DFSignal`            | —                                  | `gain_db`, `height_haat_ft`, `s_units`                                                                                                              |
| `DFBearing`           | —                                  | `bearing_deg`, `hits_code`, `quality_code`, `range_code`                                                                                            |
| `Compression`         | —                                  | `fix`, `nmea_source`, `origin_code`, `type_value`                                                                                                   |
| `DAO`                 | —                                  | `datum_byte`, `encoding`, `latitude_precision`, `longitude_precision`                                                                               |
| `Area`                | —                                  | `color_code`, `latitude_offset_code`, `longitude_offset_code`, `shape_code`                                                                         |
| `Signpost`            | —                                  | `label`                                                                                                                                             |
| `WaterHeight`         | —                                  | `measurement`                                                                                                                                       |
| `Weather`             | —                                  | `wind_speed`                                                                                                                                        |
| `Storm`               | `kind` → `storm_category`          | `central_pressure_hpa`, `hurricane_radius_nm`, `peak_gust_knots`, `predicted`, `storm_category`, `sustained_wind_knots`, `tropical_storm_radius_nm` |
| `TelemetryData`       | —                                  | `analog`, `digital`                                                                                                                                 |
| `Extensions`          | —                                  | `motion`                                                                                                                                            |
| `Location`            | —                                  | `latitude_deg`, `longitude_deg`, `symbol`                                                                                                           |
| `Beam`                | —                                  | `erp_w`, `heading_deg`                                                                                                                              |
| `ReplyAck`            | —                                  | `message_number`                                                                                                                                    |
| `TelemetryParameters` | `channels` → `channel_names`       | `channel_names`                                                                                                                                     |
| `TelemetryUnits`      | `channels` → `channel_units`       | `channel_units`                                                                                                                                     |
| `Calibration`         | —                                  | `a`, `b`, `c`                                                                                                                                       |
| `TelemetryEquations`  | —                                  | `coefficients`                                                                                                                                      |
| `TelemetryBits`       | `sense` → `sense_bits`             | `sense_bits`                                                                                                                                        |
| `NTSHeader`           | —                                  | `check`, `date`, `handling`, `number`, `originator`, `place`, `precedence`, `time`                                                                  |
| `NTSAddress`          | `lines` → `address_lines`          | `address_lines`                                                                                                                                     |
| `NTSPhone`            | `number` → `phone_number`          | `phone_number`                                                                                                                                      |
| `NTSText`             | `text` → `line_text`               | `line`, `line_text`                                                                                                                                 |
| `NTSSignature`        | `text` → `signature_text`          | `signature_text`                                                                                                                                    |
| `NTSRouting`          | —                                  | `received_at`, `received_from`, `sent_at`, `sent_to`                                                                                                |
| `QueryFootprint`      | —                                  | `center`, `radius_miles`                                                                                                                            |
| `CapabilityToken`     | `name` → `capability_name`         | `capability_name`                                                                                                                                   |
| `NMEAMetadata`        | —                                  | `talker`                                                                                                                                            |
| `GGA`                 | —                                  | `coordinates`, `fix_quality`, `time_utc`                                                                                                            |
| `GLL`                 | —                                  | `coordinates`, `fix_status`, `time_utc`                                                                                                             |
| `RMC`                 | —                                  | `coordinates`, `date_ddmmyy`, `fix_status`, `time_utc`                                                                                              |
| `VTG`                 | —                                  | `course_true_deg`                                                                                                                                   |
| `WPL`                 | —                                  | `coordinates`, `name`                                                                                                                               |
| `DecodeOptions`       | —                                  | `unsupported`                                                                                                                                       |
| `EncodeOptions`       | —                                  | `destination`                                                                                                                                       |
| `PathHop`             | —                                  | `address`                                                                                                                                           |
| `Header`              | —                                  | `destination`, `source`                                                                                                                             |
| `HeaderSemantics`     | —                                  | `q_construct`                                                                                                                                       |
| `Position`            | —                                  | `latitude_deg`, `longitude_deg`, `messaging`                                                                                                        |
| `MicE`                | —                                  | `comment_bits`, `position`                                                                                                                          |
| `ObjectReport`        | `name` → `object_name`             | `object_name`, `position`, `timestamp`                                                                                                              |
| `ItemReport`          | `name` → `item_name`               | `item_name`, `position`                                                                                                                             |
| `WeatherReport`       | —                                  | `weather`                                                                                                                                           |
| `Telemetry`           | `data` → `telemetry`               | `telemetry`                                                                                                                                         |
| `TelemetryDefinition` | —                                  | `addressee`, `definition`                                                                                                                           |
| `Status`              | `text` → `status_text`             | `status_text`                                                                                                                                       |
| `Message`             | `text` → `message_text`            | `addressee`, `message_text`                                                                                                                         |
| `Acknowledgment`      | `message_id` → `acknowledgment_id` | `acknowledgment_id`, `addressee`                                                                                                                    |
| `AutoAnswer`          | `text` → `auto_answer_text`        | `addressee`, `auto_answer_text`                                                                                                                     |
| `Bulletin`            | `identifier` → `bulletin_id`       | `bulletin_id`, `text`                                                                                                                               |
| `NWSBulletin`         | `text` → `nws_text`                | `addressee`, `nws_text`                                                                                                                             |
| `NTSMessage`          | —                                  | `addressee`, `record`                                                                                                                               |
| `Query`               | `name` → `query_name`              | `query_name`                                                                                                                                        |
| `DirectStations`      | —                                  | `stations`                                                                                                                                          |
| `HeardStation`        | —                                  | `counts`, `station`                                                                                                                                 |
| `TraceRoute`          | —                                  | `header`                                                                                                                                            |
| `QueryResponse`       | —                                  | `addressee`, `response`                                                                                                                             |
| `Capabilities`        | `tokens` → `capability_tokens`     | `capability_tokens`                                                                                                                                 |
| `NMEAReport`          | —                                  | `sentence`                                                                                                                                          |
| `ThirdParty`          | `packet` → `third_party_packet`    | `third_party_packet`                                                                                                                                |
| `UserDefined`         | —                                  | `data`, `user_id`, `user_type`                                                                                                                      |
| `RawWeather`          | `format` → `weather_format`        | `information`, `weather_format`                                                                                                                     |
| `Agrelo`              | —                                  | `bearing_deg`, `quality_code`                                                                                                                       |
| `MaidenheadBeacon`    | —                                  | `grid`                                                                                                                                              |
| `LegacyPosition`      | —                                  | `position`, `prefix`                                                                                                                                |
| `NonAPRSBeacon`       | `text` → `beacon_text`             | `beacon_text`                                                                                                                                       |
| `InvalidTest`         | `data` → `test_data`               | `test_data`                                                                                                                                         |
| `Reserved`            | —                                  | `data`, `dti`                                                                                                                                       |
| `ExternalExtension`   | `name` → `extension_name`          | `extension_name`, `information`                                                                                                                     |
| `Diagnostic`          | —                                  | `code`, `message`                                                                                                                                   |
| `Opaque`              | —                                  | `information`                                                                                                                                       |
| `Packet`              | —                                  | `header`, `payload`                                                                                                                                 |
| `EncodedPacketFields` | —                                  | `header`, `information`                                                                                                                             |

## Overlap decisions

- `Status`, `Message`, `AutoAnswer`, `NWSBulletin`, `NonAPRSBeacon` and
  `NTSSignature` have distinct semantic text keys. An object mixing these keys
  is rejected, not prioritized. Ack IDs have their own acknowledgment role.
- Objects/items use `object_name`/`item_name`. Queries and capability tokens
  similarly use `query_name`/`capability_name`. User-defined `user_type`, reserved
  `dti`, compression `type_value` and format enum fields are actual protocol
  data; they are not Python-model discriminator fields.
- Telemetry parameter names and units are different array-valued domains:
  `channel_names` and `channel_units`. They are never inferred from the strings'
  contents. NTS address/phone/text/signature record roles are likewise explicit.
- Empty `Weather`, `Motion`, `Extensions`, status, NMEA metadata and option values
  cannot all be inferred from `{}`. Canonical output retains semantic defaults
  listed above; callers can also use `expected_type` for sparse input.
- Coordinates, locations and position reports have overlapping Python fields.
  Their required JSON signatures are deliberately distinct as described above;
  an explicitly expected class never silently accepts another family's keys.

Tests cover compact/full-default round trips for all 84 models, every payload in
full packets, every nested union variant, all 256 byte values, metadata ignored
by dataclass equality, default-only models, shape conflicts, invalid scalar
values, duplicate keys, cycles and nesting limits. These are JSON contract tests,
not additional claims about APRS wire codec support.
