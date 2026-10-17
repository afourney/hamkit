# hamkit.aprs

Parse APRS packets, build them in Python, and move them to and from JSON.
Pure Python · MIT license · Python 3.10+ · no runtime dependencies.

This is an **alpha API**. Basic status, position, message and acknowledgment
packets work today, along with the envelope/raw formats shown below. Other
families have usable Python and JSON models but **no wire codec yet**. Those
sections say **Model + JSON only** and print the constructed model's name;
they do not claim to produce a TNC2 line. Calling `serialize_packet` on those
models raises `CodecNotImplemented`.

Install from a repository checkout with `python -m pip install -e packages/aprs`.
Each Python block below runs independently. Each JSON block is one complete
input: copy it into a string named `json_text` and run the one-line call directly
beneath it. Every example is followed by its exact output and checked by tests.
Nothing here sends packets over a network or radio.

## Find an example

- [Parse a packet](#parse-a-packet)
- [Build a status packet](#build-a-status-packet) — Python and JSON
- [Working wire examples](#working-wire-examples)
  - [Position](#position)
  - [Message](#message)
  - [Acknowledgment](#acknowledgment)
  - [Third-party packet](#third-party-packet)
  - [User-defined data](#user-defined-data)
  - [Invalid/test packet](#invalidtest-packet)
  - [Reserved data](#reserved-data)
  - [Opaque data](#opaque-data)
- [Model and JSON examples](#model-and-json-examples)
  - [Places and weather](#places-and-weather) — [Mic-E](#mic-e), [Object](#object), [Item](#item), [Weather](#weather)
  - [Telemetry](#telemetry) — [Telemetry readings](#telemetry-readings), [Telemetry definition](#telemetry-definition)
  - [Messages and queries](#messages-and-queries) — [Automatic answer](#automatic-answer), [Bulletin](#bulletin), [NWS bulletin](#nws-bulletin), [Radiogram](#radiogram), [Query](#query), [Response](#response), [Capabilities](#capabilities)
  - [Other formats](#other-formats) — [NMEA](#nmea), [Raw vendor weather](#raw-vendor-weather), [Agrelo](#agrelo), [Maidenhead beacon](#maidenhead-beacon), [Legacy position](#legacy-position), [Non-APRS beacon](#non-aprs-beacon), [External extension](#external-extension)
- [Unsupported and malformed input](#unsupported-and-malformed-input)
- [Bytes, units and round trips](#bytes-units-and-round-trips)
- [Full reference](#full-reference)

## Parse a packet

Start with one status packet. `parse_packet` reads the whole TNC2 envelope and
returns a Packet with a Header and a typed payload. `to_json` is a module function.

```python
import hamkit.aprs as a

packet = a.parse_packet(b"N0CALL>APRS:>Ready")
print(packet)
print(a.to_json(packet, indent=2))
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Status(text=b'Ready', timestamp=None, grid=None, symbol=None, beam=None), header_semantics=None)
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "status",
    "text": "Ready"
  },
  "original_wire": "N0CALL>APRS:>Ready"
}
```

The text is `packet.payload.text`. `original_wire` in JSON records the received
bytes; it is separate from the structured fields and does not change when those
fields are edited. JSON type tags identify models, not Python class names.

## Build a status packet

**Wire encoding available** for basic status text. These two inputs build the
same packet and produce the same TNC2 line.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.Status(b"Ready"))
print(a.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:>Ready
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "status",
    "text": "Ready"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(a.serialize_packet(a.from_json(json_text)).decode("ascii"))`

Output:

```text
N0CALL>APRS:>Ready
```

## Working wire examples

Each example uses the supported subset of its family. More elaborate fields can
still require an unimplemented codec; see the [coverage notes](docs/API_COVERAGE.md).
Serialization returns bytes. Here `.decode("ascii")` makes these printable
examples easy to read; keep the bytes when handling binary payloads.

### Position

**Wire encoding available for this example.** An uncompressed latitude/longitude position with a car symbol.

Read one position packet:

```python
import hamkit.aprs as a

packet = a.parse_packet(b"N0CALL>APRS:!4903.50N/07201.75W>")
print(packet)
print(a.to_json(packet, indent=2))
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Position(latitude_deg=49.05833333333333, longitude_deg=-72.02916666666667, symbol=Symbol(table_id='/', code='>'), messaging=False, timestamp=None, tail=b'', encoding='uncompressed', ambiguity=None, compression=None, extensions=Extensions(motion=None, altitude=None, phg=None, range=None, signal=None, bearing=None, dao=None, area=None, signpost=None, weather=None, storm=None, telemetry=None), comment=b''), header_semantics=None)
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "position",
    "latitude_deg": 49.05833333333333,
    "longitude_deg": -72.02916666666667,
    "symbol": {
      "code": ">"
    }
  },
  "original_wire": "N0CALL>APRS:!4903.50N/07201.75W>"
}
```

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"),
    a.Position(49.05833333333333, -72.02916666666667, symbol=a.Symbol("/", ">")),
)
print(a.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:!4903.50N/07201.75W>
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "position",
    "latitude_deg": 49.05833333333333,
    "longitude_deg": -72.02916666666667,
    "symbol": {
      "code": ">"
    }
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(a.serialize_packet(a.from_json(json_text)).decode("ascii"))`

Output:

```text
N0CALL>APRS:!4903.50N/07201.75W>
```

### Message

**Wire encoding available for this example.** A message addressed to W1AW with message ID 003.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.Message("W1AW", b"Hello", "003"))
print(a.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS::W1AW     :Hello{003
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "message",
    "addressee": "W1AW",
    "text": "Hello",
    "message_id": "003"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(a.serialize_packet(a.from_json(json_text)).decode("ascii"))`

Output:

```text
N0CALL>APRS::W1AW     :Hello{003
```

### Acknowledgment

**Wire encoding available for this example.** Acknowledge message 003. This is a separate payload from the original message.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.Acknowledgment("W1AW", "003"))
print(a.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS::W1AW     :ack003
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "acknowledgment",
    "addressee": "W1AW",
    "message_id": "003"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(a.serialize_packet(a.from_json(json_text)).decode("ascii"))`

Output:

```text
N0CALL>APRS::W1AW     :ack003
```

### Third-party packet

**Wire encoding available for this example.** An outer packet carries a complete inner packet. The inner codec must also be available.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"),
    a.ThirdParty(a.Packet(a.Header("W1AW", "APRS"), a.Status(b"Ready"))),
)
print(a.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:}W1AW>APRS:>Ready
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "third_party",
    "packet": {
      "header": {
        "source": "W1AW",
        "destination": "APRS"
      },
      "payload": {
        "type": "status",
        "text": "Ready"
      }
    }
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(a.serialize_packet(a.from_json(json_text)).decode("ascii"))`

Output:

```text
N0CALL>APRS:}W1AW>APRS:>Ready
```

### User-defined data

**Wire encoding available for this example.** User ID Q, user type 1, and uninterpreted data. Binary data is allowed too.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.UserDefined(b"Q", b"1", b"Hello"))
print(a.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:{Q1Hello
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "user_defined",
    "user_id": "Q",
    "user_type": "1",
    "data": "Hello"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(a.serialize_packet(a.from_json(json_text)).decode("ascii"))`

Output:

```text
N0CALL>APRS:{Q1Hello
```

### Invalid/test packet

**Wire encoding available for this example.** An explicitly invalid/test packet; it does not represent a trusted position.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.Invalid(b"invalid fix"))
print(a.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:,invalid fix
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "invalid",
    "data": "invalid fix"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(a.serialize_packet(a.from_json(json_text)).decode("ascii"))`

Output:

```text
N0CALL>APRS:,invalid fix
```

### Reserved data

**Wire encoding available for this example.** Build a reserved information field explicitly. Parsing it currently returns Opaque.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.Reserved(ord("~"), b"data"))
print(a.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:~data
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "reserved",
    "dti": 126,
    "data": "data"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(a.serialize_packet(a.from_json(json_text)).decode("ascii"))`

Output:

```text
N0CALL>APRS:~data
```

### Opaque data

**Wire encoding available for this example.** Keep unsupported information bytes without inventing a structured interpretation.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.Opaque(b"~vendor data"))
print(a.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:~vendor data
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "opaque",
    "information": "~vendor data"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(a.serialize_packet(a.from_json(json_text)).decode("ascii"))`

Output:

```text
N0CALL>APRS:~vendor data
```

## Model and JSON examples

**Model + JSON only** means the values below can be built, inspected, saved and
loaded now, but cannot yet be serialized to APRS wire bytes. Both forms print the
same payload class name to confirm the model they construct. The JSON is the
actual data shape, not a proposed wire encoding. No future wire output is shown.

For example, this is what happens if you ask the current encoder to write a
weather model to the wire:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"),
    a.Weather(temperature=a.Measurement(68, "fahrenheit")),
)
try:
    print(a.serialize_packet(packet).decode("ascii"))
except a.CodecNotImplemented as error:
    print(type(error).__name__)
```

Output:

```text
CodecNotImplemented
```

The following examples build and load these models without asking for wire
encoding. They remain useful for storing or exchanging structured data.

### Places and weather

#### Mic-E

**Model + JSON only.** Compact Mic-E position data. A future encoder must coordinate the destination address and payload.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"), a.MicE(a.Location(49, -72), (True, False, True))
)
print(type(packet.payload).__name__)
```

Output:

```text
MicE
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "mic_e",
    "position": {
      "latitude_deg": 49,
      "longitude_deg": -72
    },
    "comment_bits": [true, false, true]
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
MicE
```

#### Object

**Model + JSON only.** A named, timestamped object at a position.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"),
    a.Object("AID #2", a.Location(49, -72), a.Timestamp("dhm_utc", 12, 30, day=17)),
)
print(type(packet.payload).__name__)
```

Output:

```text
Object
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "object",
    "name": "AID #2",
    "position": {
      "latitude_deg": 49,
      "longitude_deg": -72
    },
    "timestamp": {
      "kind": "dhm_utc",
      "hour": 12,
      "minute": 30,
      "day": 17
    }
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Object
```

#### Item

**Model + JSON only.** A named item at a position, without an object timestamp.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.Item("WATER", a.Location(49, -72)))
print(type(packet.payload).__name__)
```

Output:

```text
Item
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "item",
    "name": "WATER",
    "position": {
      "latitude_deg": 49,
      "longitude_deg": -72
    }
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Item
```

#### Weather

**Model + JSON only.** Weather measurements have explicit units. Use the same Weather model in Extensions.weather for located weather.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"),
    a.Weather(
        wind_direction=a.Measurement(270, "degrees"),
        wind_speed=a.Measurement(12, "mph"),
        temperature=a.Measurement(68, "fahrenheit"),
        pressure=a.Measurement(1013.2, "hPa"),
    ),
)
print(type(packet.payload).__name__)
```

Output:

```text
Weather
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "weather",
    "wind_direction": {
      "value": 270,
      "unit": "degrees"
    },
    "wind_speed": {
      "value": 12,
      "unit": "mph"
    },
    "temperature": {
      "value": 68,
      "unit": "fahrenheit"
    },
    "pressure": {
      "value": 1013.2,
      "unit": "hPa"
    }
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Weather
```

### Telemetry

#### Telemetry readings

**Model + JSON only.** Ordered analog and digital channels. None represents an unavailable channel, not zero.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"), a.Telemetry((199, 0, 255), (False, True), sequence=1)
)
print(type(packet.payload).__name__)
```

Output:

```text
Telemetry
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "telemetry",
    "analog": [199, 0, 255],
    "digital": [false, true],
    "sequence": 1
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Telemetry
```

#### Telemetry definition

**Model + JSON only.** Channel names sent to N0CALL. Units, Equations and Bits are the other definition variants.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"),
    a.Definition("N0CALL", a.Parameters(("Temperature", "Voltage"))),
)
print(type(packet.payload).__name__)
```

Output:

```text
Definition
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "definition",
    "addressee": "N0CALL",
    "definition": {
      "type": "parameters",
      "channels": ["Temperature", "Voltage"]
    }
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Definition
```

### Messages and queries

#### Automatic answer

**Model + JSON only.** An automatic reply addressed to W1AW.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.AutoAnswer("W1AW", b"Away", "02"))
print(type(packet.payload).__name__)
```

Output:

```text
AutoAnswer
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "auto_answer",
    "addressee": "W1AW",
    "text": "Away",
    "previous_ack": "02"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
AutoAnswer
```

#### Bulletin

**Model + JSON only.** A bulletin identifier, text and optional group.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"), a.Bulletin("1", b"Meeting at 1900", "CLUB")
)
print(type(packet.payload).__name__)
```

Output:

```text
Bulletin
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "bulletin",
    "identifier": "1",
    "text": "Meeting at 1900",
    "group": "CLUB"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Bulletin
```

#### NWS bulletin

**Model + JSON only.** A National Weather Service product envelope, distinct from a general bulletin.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"), a.NWSBulletin("NWS-WARN", b"Storm", "S9JbA")
)
print(type(packet.payload).__name__)
```

Output:

```text
NWSBulletin
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "nws_bulletin",
    "addressee": "NWS-WARN",
    "text": "Storm",
    "reference_id": "S9JbA"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
NWSBulletin
```

#### Radiogram

**Model + JSON only.** One NTS radiogram record in its delivery envelope. This example carries text line 1.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"), a.Radiogram("W1AW", a.Text(1, b"Hello"), "001")
)
print(type(packet.payload).__name__)
```

Output:

```text
Radiogram
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "radiogram",
    "addressee": "W1AW",
    "record": {
      "type": "text",
      "line": 1,
      "text": "Hello"
    },
    "message_id": "001"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Radiogram
```

#### Query

**Model + JSON only.** A query with a geographic footprint.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"),
    a.Query("APRS", footprint=a.Footprint(a.Coordinates(49, -72), 20)),
)
print(type(packet.payload).__name__)
```

Output:

```text
Query
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "query",
    "name": "APRS",
    "footprint": {
      "center": {
        "latitude_deg": 49,
        "longitude_deg": -72
      },
      "radius_miles": 20
    }
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Query
```

#### Response

**Model + JSON only.** A query response listing directly heard stations. HeardStation and Trace are other response variants.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"), a.Response("W1AW", a.DirectStations(("N0CALL",)))
)
print(type(packet.payload).__name__)
```

Output:

```text
Response
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "response",
    "addressee": "W1AW",
    "response": {
      "type": "direct_stations",
      "stations": ["N0CALL"]
    }
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Response
```

#### Capabilities

**Model + JSON only.** A station advertises a protocol capability token.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.Capabilities((a.Capability("IGATE"),)))
print(type(packet.payload).__name__)
```

Output:

```text
Capabilities
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "capabilities",
    "tokens": [
      {
        "name": "IGATE"
      }
    ]
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Capabilities
```

### Other formats

#### NMEA

**Model + JSON only.** A GLL navigation sentence. GGA, RMC, VTG and WPL are also modeled.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"), a.NMEA(a.GLL(a.Coordinates(49, -72), b"123000", "A"))
)
print(type(packet.payload).__name__)
```

Output:

```text
NMEA
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "nmea",
    "sentence": {
      "type": "gll",
      "coordinates": {
        "latitude_deg": 49,
        "longitude_deg": -72
      },
      "time_utc": "123000",
      "fix_status": "A"
    }
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
NMEA
```

#### Raw vendor weather

**Model + JSON only.** Preserve vendor bytes and their declared format; this is not a decoded weather observation.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.RawWeather("ultw", b"$ULTW0000"))
print(type(packet.payload).__name__)
```

Output:

```text
RawWeather
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "raw_weather",
    "format": "ultw",
    "information": "$ULTW0000"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
RawWeather
```

#### Agrelo

**Model + JSON only.** Direction-finding bearing and quality.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.Agrelo(123, 4))
print(type(packet.payload).__name__)
```

Output:

```text
Agrelo
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "agrelo",
    "bearing_deg": 123,
    "quality_code": 4
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Agrelo
```

#### Maidenhead beacon

**Model + JSON only.** The historical bracket-style grid beacon. Grid bounds and center can be supplied separately.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.Maidenhead(a.Grid("IO91SX")))
print(type(packet.payload).__name__)
```

Output:

```text
Maidenhead
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "maidenhead",
    "grid": {
      "locator": "IO91SX"
    }
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Maidenhead
```

#### Legacy position

**Model + JSON only.** A historical prefix around a position.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"), a.LegacyPosition(b"X1J ", a.Position(49, -72))
)
print(type(packet.payload).__name__)
```

Output:

```text
LegacyPosition
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "legacy_position",
    "prefix": "X1J ",
    "position": {
      "type": "position",
      "latitude_deg": 49,
      "longitude_deg": -72
    }
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
LegacyPosition
```

#### Non-APRS beacon

**Model + JSON only.** Plain beacon text with no APRS interpretation.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(a.Header("N0CALL", "APRS"), a.Beacon(b"UIDIGI ready"))
print(type(packet.payload).__name__)
```

Output:

```text
Beacon
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "beacon",
    "text": "UIDIGI ready"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
Beacon
```

#### External extension

**Model + JSON only.** Preserve external-format data by name; its grammar has not been implemented.

Build with Python:

```python
import hamkit.aprs as a

packet = a.Packet(
    a.Header("N0CALL", "APRS"), a.ExternalExtension("polygon_line", b"raw")
)
print(type(packet.payload).__name__)
```

Output:

```text
ExternalExtension
```

Build the same packet from JSON:

```json
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "external_extension",
    "name": "polygon_line",
    "information": "raw"
  }
}
```

Run with the JSON above as `json_text`: `import hamkit.aprs as a; print(type(a.from_json(json_text).payload).__name__)`

Output:

```text
ExternalExtension
```

## Unsupported and malformed input

Unsupported payloads are preserved as Opaque by default. This weather packet's
information field is retained, not decoded into Weather measurements:

```python
import hamkit.aprs as a

packet = a.parse_packet(
    b"N0CALL>APRS:_10090556c220s004g005t077r001p025P012h50b09900WRSW"
)
print(packet)
print(a.to_json(packet, indent=2))
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Opaque(information=b'_10090556c220s004g005t077r001p025P012h50b09900WRSW', reason='unsupported information field family', diagnostic=Diagnostic(code='unsupported', message='unsupported information field family')), header_semantics=None)
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "opaque",
    "information": "_10090556c220s004g005t077r001p025P012h50b09900WRSW",
    "reason": "unsupported information field family",
    "diagnostic": {
      "code": "unsupported",
      "message": "unsupported information field family"
    }
  },
  "original_wire": "N0CALL>APRS:_10090556c220s004g005t077r001p025P012h50b09900WRSW"
}
```

To require an implemented decoder, pass `DecodeOptions(unsupported="raise")`.
Malformed supported payloads raise an error by default. This single input has an
invalid position; the example prints the exception class:

```python
import hamkit.aprs as a

try:
    packet = a.parse_packet(b"N0CALL>APRS:!not a position")
except a.APRSError as error:
    print(type(error).__name__)
```

Output:

```text
FieldError
```

Use `DecodeOptions(malformed="opaque")` to retain a malformed payload with a
diagnostic. Invalid outer headers and resource-limit violations still raise.
`parse_packet` consumes unframed bytes; use `parse_tnc2_line` for a transport line
with a trailing newline. Do not strip arbitrary binary payload bytes.

## Bytes, units and round trips

- Python text fields that represent packet bytes use `b"..."`. JSON represents
  those bytes as Latin-1 strings: `\u0000` is byte 0 and `\u00ff` is byte 255.
- A missing weather measurement differs from `Measurement(None, "mph")`, which
  means an unavailable reading. Zero is an actual measurement. Units are explicit;
  no automatic conversion is performed.
- `to_json_dict` and `from_json_dict` work with dictionaries. Use
  `to_json(packet, indent=2, include_defaults=True)` to show optional defaults.
- `from_json(json_text, expected_type=a.Packet)` checks the expected model.
  Unknown fields, duplicate keys, and missing or incompatible tags raise
  `JSONModelError`.
- JSON round trips preserve model values and raw evidence. They do not preserve
  whitespace, key order, or whether an optional null was originally omitted.
  `serialize_packet` encodes the model; it does not replay `original_wire`.

## Full reference

- [Illustrated JSON reference](docs/JSON_FORMAT.md): all 82 models, expanded nested
  objects, every union variant, fields, defaults, tags, units and enums.
- [Wire support by family](docs/API_COVERAGE.md): implemented subsets and gaps.
- [Naming guide](docs/NAMING.md): short public names and why some qualifiers remain.
- [Compliance vectors](docs/APRS_COMPLIANCE_VECTORS.md): specification references
  and the future packet/field test corpus. These examples are illustrations, not
  a claim that the complete corpus passes.

Run the examples and unit tests with
`python -m unittest discover -s packages/aprs/tests -v` from the repository root.
