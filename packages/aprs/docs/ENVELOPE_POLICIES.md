# Packet policies

`EnvelopePolicy` is immutable configuration for outer-envelope constraints,
payload interpretation and conformance. The same `policy=` argument is accepted
by `parse_packet`, `parse_payload`, `parse_tnc2_line`, `check_packet`,
`validate_packet`, `serialize_packet`, `serialize_payload`, and
`serialize_tnc2_line`. Payload-only operations have no outer envelope to check.
`parse_payload` returns the payload; use `parse_packet` for receive diagnostics.

## Construction and factories

Direct construction is supported independently of factories:

```python
from hamkit import aprs

policy = aprs.EnvelopePolicy(
    source_pattern=r"src_[0-9]+",
    destination_pattern=r"dst_[A-Z]+",
    path_address_pattern=r"via_[a-z]+",
    max_path_entries=1,
    max_information_bytes=200,
    max_tnc2_line_bytes=None,
    extensions={"utf8_text", "dao"},
    legacy_positions=False,
    byte_fallback="latin-1",
)
```

Direct construction defaults to **no extensions**, no legacy position search,
Latin-1 receive fallback, and unlimited lengths. The three patterns are required.
Extension collections are normalized into an immutable tuple in catalog order.
Unknown identifiers and duplicates are rejected. Strings are not collections of
extension identifiers. Patterns must compile; limits must be nonnegative integers
or `None`. Zero is a real limit. Unknown factory overrides raise `TypeError`.

`RF()` and `APRS_IS()` are optional factories returning the **same type**. Both
default to `utf8_text`, `dao`, `base91_telemetry`, `mice_device_ids`,
`expanded_telemetry`, `phg_rate`, and `weather_extensions`. Neither enables
`mice_hex_as_device` or `water_height_tenths`.
The public codec defaults are the resolved result of `APRS_IS()`.
An explicit extension collection replaces the entire default set:

```python
baseline = aprs.RF(extensions=set())
custom = aprs.APRS_IS(max_tnc2_line_bytes=1024, source_pattern=r"[A-Z0-9]+")
hex_as_device = aprs.RF(extensions={*aprs.RF().extensions, "mice_hex_as_device"})
```

| Constraint                     | `RF()`                                                 | `APRS_IS()`                                                                                        |
| ------------------------------ | ------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| Source                         | 1–6 uppercase ASCII letters/digits; optional SSID 0–15 | 3+ ASCII letters/digits; optional 1–2 alphanumeric SSID characters except `-0`; 9 characters total |
| Destination / path             | Same as RF source                                      | 1+ ASCII letter/digit; same SSID and total-length limits                                           |
| Path entries                   | 8                                                      | Unlimited                                                                                          |
| Information bytes              | 256                                                    | Unlimited                                                                                          |
| TNC2 line bytes including CRLF | Unlimited                                              | 512                                                                                                |

Patterns use `fullmatch`; path patterns exclude the trailing repeated marker `*`.
APRS-IS permits mixed case (including `qAR`). These are address-format checks,
not q-construct ordering or routing validation. See the
[server address rules](https://www.aprs-is.net/ServerDesign.aspx) and
[connection specification](https://www.aprs-is.net/Connecting.aspx).

## Baseline and extension catalog

An empty extension set selects the implemented APRS101 plus APRS 1.1 baseline,
subject to the [documented codec limits](API_COVERAGE.md). This is not a claim of
complete conformance to every sentence in either specification. The live
[1.1 addendum](https://www.aprs.org/aprs11.html) links later proposals; those links
do not silently enable every [1.2 proposal](https://www.aprs.org/aprs12.html).

| Identifier            | Enabled behavior                                                                                                                                                          | Empty-set behavior                                                                                                                                                                  |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `utf8_text`           | UTF-8 in message/auto-answer/bulletin text, status text, position/object/item and Mic-E comments                                                                          | Those fields require ASCII for conformance; intelligible received Unicode is retained with diagnostics                                                                              |
| `dao`                 | Recognize DAO in position comments and apply precision offsets                                                                                                            | Preserve the complete matching text in the comment and the baseline coordinates                                                                                                     |
| `base91_telemetry`    | Extract supported base91 comment telemetry                                                                                                                                | Preserve the complete matching text in the comment                                                                                                                                  |
| `mice_device_ids`     | Read an apostrophe/backtick type byte where complete APRS101 hex telemetry is absent; break declared manufacturer/version suffixes out of the comment for every type byte | Read apostrophe/backtick selectors as legacy hexadecimal telemetry (incomplete hex is undecodable); original `>` and `]` markers remain supported, suffix text stays in the comment |
| `mice_hex_as_device`  | Also read complete hexadecimal telemetry after an apostrophe/backtick as device text (implies `mice_device_ids`)                                                          | Complete hexadecimal text after a selector is APRS101 telemetry                                                                                                                     |
| `expanded_telemetry`  | Classic analog integer values 0–999                                                                                                                                       | Classic analog integers 0–255; intelligible larger received values carry diagnostics                                                                                                |
| `phg_rate`            | PHGR rate and delimiter, optional PHG separator, documented PHG comment whitespace normalization                                                                          | Decode baseline PHG; preserve following rate-shaped text, separators and whitespace as comment                                                                                      |
| `weather_extensions`  | X radiation and V battery voltage                                                                                                                                         | Original weather fields; X/V are not sensor fields                                                                                                                                  |
| `water_height_tenths` | Interpret fixed-width F water height in tenths of a foot, including unavailable F....                                                                                     | Preserve the older decimal/whole F/f feet/meters interpretation                                                                                                                     |

The catalog is exported as `SUPPORTED_EXTENSIONS`, with `Extension` and
`ByteFallback` annotation aliases and typed `PolicyOverrides` factory keywords. Only implemented behavior has an identifier.
Extended high-speed interpretation, frequency/tone parsing, and a blanket
`aprs12` switch are not implemented; unknown identifiers are rejected.

These switches have different effects. Range expansion keeps old numeric values
unchanged. UTF-8 keeps ASCII unchanged and allows additional characters only in
designated free-text regions; tokens such as callsigns, names and IDs remain
ASCII. DAO, base91 and PHGR recognize structure in what could previously be
comment text. Disabling them preserves that text rather than discarding it or
declaring the whole packet family malformed.

Mic-E type codes are split by that rule. Where an apostrophe/backtick is not
followed by complete APRS101 hex telemetry, APRS 1.1 accepts no field there, so
`mice_device_ids` reads the type byte and is on by default; this is what
ordinary Yaesu, Byonics and Anytone packets use. Declared version suffixes, such
as the Kenwood `]…=`, were comment text in APRS 1.1 and are broken out by the
same switch. Reading complete hex telemetry as device text changes an accepted
APRS 1.1 field, so that is the separate opt-in `mice_hex_as_device`. Hex
telemetry cannot be sent with `mice_hex_as_device` enabled; modern device
identifiers cannot be sent with both switches disabled.
Water height is a separate opt-in reinterpretation: `F1234` is 123.4 feet with
`water_height_tenths`, but 1234 feet under the older whole-number reading. It is
therefore not accurate to describe every extension as purely additive. Weather
composition uses an explicit decimal point for numeric heights so either reader
recovers the same value. Unavailable `F....` requires the extension.

`EXTENSION_KINDS` is the immutable classification catalog, typed with
`ExtensionKind`. Every supported identifier must be classified explicitly.
Factories enable only `additive` and the approved `comment` category:

| Class            | Current identifiers                                      | Factory default |
| ---------------- | -------------------------------------------------------- | --------------- |
| `additive`       | `utf8_text`, `expanded_telemetry`, `weather_extensions`  | Enabled         |
| `comment`        | `dao`, `base91_telemetry`, `mice_device_ids`, `phg_rate` | Enabled         |
| `reinterpretive` | `mice_hex_as_device`, `water_height_tenths`              | Disabled        |

The consistent rule is that a convention changing the numeric or type meaning
of an existing encoded field requires explicit opt-in. Recognizing structured
content inside a previously free-text comment is the separately approved default
category; DAO can refine coordinates, but it does not redefine the original
coordinate digits. Expanded telemetry leaves 0–255 values unchanged. Radiation
and voltage add sensor tags. Reading complete Mic-E hex telemetry as device text
reuses an existing telemetry field; fixed-width water height rescales an
existing F field. Future high-speed
reinterpretation must be classified as `reinterpretive` if implemented; it has
no supported identifier today. Catalog/default tests require deliberate review
when any identifier is added.

Numeric water heights remain semantic values in feet/meters. Both policies
serialize them with a decimal point, so a decoded 123.4-foot reading is emitted
as `F123.4`, not obtained by replaying the original `F1234`. Defaults decode
`F1234` as 1234 feet; adding `water_height_tenths` decodes it as 123.4 feet.
Radiation/voltage can remain enabled independently of this choice.

Sources: [UTF-8 guidance](https://www.aprs.org/aprs12/utf-8.txt),
[Mic-E type conventions](https://www.aprs.org/aprs12/mic-e-types.txt),
[base91 telemetry](https://github.com/hessu/aprs-specs/blob/master/aprs-base91-comment-telemetry.txt),
[PHGR](https://www.aprs.org/aprs12/probes.txt), and
[weather proposals](https://www.aprs.org/aprs12/weather-new.txt).

## Receive, send and nesting

Intelligible nonconforming input returns a `Packet` with diagnostics. Truly
undecodable fields return `Malformed` (or raise with `malformed="raise"`).
Unsupported families retain their explicit raw representation. Disabling a
feature does not disable ordinary packets in its family.

`byte_fallback="latin-1"` retains undecodable UTF-8 bytes as one character per
byte and records a diagnostic. It does not assert the sender's character set.
`byte_fallback="reject"` makes that field undecodable. This receive option is
independent of `utf8_text`. `legacy_positions=True` enables the deprecated X1J
embedded-position search; it is also independent of the extension catalog.
The parser's optional `legacy_positions=` argument is an explicit override;
configuration-driven applications should put the setting in the policy.

Serialization rechecks the current model and selected policy, then constructs
fresh bytes. It never replays `original_wire`; clearing saved diagnostics cannot
bypass checking. Free text is encoded as UTF-8, and limits count bytes. Parse
limits measure received bytes; send limits measure the newly constructed bytes.
The line limit includes canonical CRLF even for an unframed or LF-only input.

Envelope patterns and limits apply only to the outer packet. Third-party inner
headers remain encapsulated text, so RF does not impose AX.25 address constraints
on an inner APRS-IS path. Basic token syntax still applies. Payload interpretation,
text rules and diagnostics propagate through every nesting level; the outer
information limit includes the entire encapsulated packet.

## Fully resolved JSON

```python
encoded = aprs.to_json(policy)
restored = aprs.from_json(encoded, expected_type=aprs.EnvelopePolicy)
assert restored == policy
```

Policy JSON contains `type: "policy"` and **all nine resolved fields**, including
all patterns, limits, extension identifiers, the legacy setting and byte fallback.
It contains no preset label. Even compact output includes empty/default/null
fields. Loading requires all resolved fields and rejects unknown keys, unknown
extensions, invalid values and conflicting type tags. An untagged mapping is
accepted with `expected_type=EnvelopePolicy`. `dataclasses.asdict` plus ordinary
JSON also works; the direct constructor accepts the resulting extension list.
Packet JSON remains a structural model representation, independent of wire policy.

Every corpus row uses this complete configuration (without the optional type
tag). Its separate `legacy_positions` field and source profile/options remain
provenance; runners use only `row["policy"]` to choose interpretation. See the
[vector runner](../tests/vectors/README.md#runner-configuration).
