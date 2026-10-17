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
Construction examples run independently, including those that embed JSON
directly. After each parsing example, the JSON display block uses `packet` from
the block immediately above it. The recovery example also uses the result immediately above it. Each block prints one result, followed by its
exact output; the examples are checked by tests.
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
from hamkit import aprs

packet = aprs.parse_packet(b"N0CALL>APRS:>Ready")
print(packet)
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Status(text='Ready', timestamp=None, grid=None, symbol=None, beam=None), header_semantics=None)
```

Show that same packet as JSON:

```python
print(aprs.to_json(packet, indent=2))
```

Output:

```text
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
same packet and produce the same TNC2 line. `from_json` builds the Packet;
`serialize_packet` converts it to bytes. `.decode("ascii")` displays these
printable examples without a Python bytes prefix.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(aprs.Header("N0CALL", "APRS"), aprs.Status("Ready"))
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:>Ready
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

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
from hamkit import aprs

packet = aprs.parse_packet(b"N0CALL>APRS:!4903.50N/07201.75W>")
print(packet)
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Position(latitude_deg=49.05833333333333, longitude_deg=-72.02916666666667, symbol=Symbol(table_id='/', code='>'), messaging=False, timestamp=None, tail=b'', encoding='uncompressed', ambiguity=None, compression=None, extensions=Extensions(motion=None, altitude=None, phg=None, range=None, signal=None, bearing=None, dao=None, area=None, signpost=None, weather=None, storm=None, telemetry=None), comment=''), header_semantics=None)
```

Show that same packet as JSON:

```python
print(aprs.to_json(packet, indent=2))
```

Output:

```text
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
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Position(49.05833333333333, -72.02916666666667, symbol=aprs.Symbol("/", ">")),
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:!4903.50N/07201.75W>
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:!4903.50N/07201.75W>
```

### Message

**Wire encoding available for this example.** A message addressed to W1AW with message ID 003.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.Message("W1AW", "Hello", "003")
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS::W1AW     :Hello{003
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS::W1AW     :Hello{003
```

### Acknowledgment

**Wire encoding available for this example.** Acknowledge message 003. This is a separate payload from the original message.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(aprs.Header("N0CALL", "APRS"), aprs.Acknowledgment("W1AW", "003"))
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS::W1AW     :ack003
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS::W1AW     :ack003
```

### Third-party packet

**Wire encoding available for this example.** An outer packet carries a complete inner packet. The inner codec must also be available.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.ThirdParty(aprs.Packet(aprs.Header("W1AW", "APRS"), aprs.Status("Ready"))),
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:}W1AW>APRS:>Ready
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:}W1AW>APRS:>Ready
```

### User-defined data

**Wire encoding available for this example.** User ID Q, user type 1, and uninterpreted data. Binary data is allowed too.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.UserDefined(b"Q", b"1", b"Hello")
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:{Q1Hello
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:{Q1Hello
```

### Invalid/test packet

**Wire encoding available for this example.** An explicitly invalid/test packet; it does not represent a trusted position.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(aprs.Header("N0CALL", "APRS"), aprs.Invalid(b"invalid fix"))
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:,invalid fix
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:,invalid fix
```

### Reserved data

**Wire encoding available for this example.** Build a reserved information field explicitly. Parsing it currently returns Opaque.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(aprs.Header("N0CALL", "APRS"), aprs.Reserved(ord("~"), b"data"))
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:~data
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:~data
```

### Opaque data

**Wire encoding available for this example.** Keep unsupported information bytes without inventing a structured interpretation.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(aprs.Header("N0CALL", "APRS"), aprs.Opaque(b"~vendor data"))
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:~vendor data
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(aprs.serialize_packet(packet).decode("ascii"))
```

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
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Weather(
        temperature=aprs.Measurement(68, "fahrenheit"),
        timestamp=aprs.Timestamp("mdhm_utc", 12, 30, day=17, month=10),
    ),
)
try:
    print(aprs.serialize_packet(packet).decode("ascii"))
except aprs.CodecNotImplemented as error:
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
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.MicE(aprs.Location(49, -72), (True, False, True)),
)
print(type(packet.payload).__name__)
```

Output:

```text
MicE
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
    "comment_bits": [
      true,
      false,
      true
    ]
  }
}
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
MicE
```

#### Object

**Model + JSON only.** A named, timestamped object at a position.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Object(
        "AID #2", aprs.Location(49, -72), aprs.Timestamp("dhm_utc", 12, 30, day=17)
    ),
)
print(type(packet.payload).__name__)
```

Output:

```text
Object
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Object
```

#### Item

**Model + JSON only.** A named item at a position, without an object timestamp.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.Item("WATER", aprs.Location(49, -72))
)
print(type(packet.payload).__name__)
```

Output:

```text
Item
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Item
```

#### Weather

**Model + JSON only.** Weather measurements have explicit units. Use the same Weather model in Extensions.weather for located weather.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Weather(
        wind_direction=aprs.Measurement(270, "degrees"),
        wind_speed=aprs.Measurement(12, "mph"),
        temperature=aprs.Measurement(68, "fahrenheit"),
        pressure=aprs.Measurement(1013.2, "hPa"),
        timestamp=aprs.Timestamp("mdhm_utc", 12, 30, day=17, month=10),
    ),
)
print(type(packet.payload).__name__)
```

Output:

```text
Weather
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
    },
    "timestamp": {
      "kind": "mdhm_utc",
      "hour": 12,
      "minute": 30,
      "day": 17,
      "month": 10
    }
  }
}
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Weather
```

### Telemetry

#### Telemetry readings

**Model + JSON only.** Ordered analog and digital channels. None represents an unavailable channel, not zero.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Telemetry(
        (199, 0, 255, 73, 123),
        (False, True, True, False, True, False, False, True),
        sequence=1,
    ),
)
print(type(packet.payload).__name__)
```

Output:

```text
Telemetry
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "telemetry",
    "analog": [
      199,
      0,
      255,
      73,
      123
    ],
    "digital": [
      false,
      true,
      true,
      false,
      true,
      false,
      false,
      true
    ],
    "sequence": 1
  }
}
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Telemetry
```

#### Telemetry definition

**Model + JSON only.** Channel names sent to N0CALL. Units, Equations and Bits are the other definition variants.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Definition("N0CALL", aprs.Parameters(("Temperature", "Voltage"))),
)
print(type(packet.payload).__name__)
```

Output:

```text
Definition
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
      "channels": [
        "Temperature",
        "Voltage"
      ]
    }
  }
}
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Definition
```

### Messages and queries

#### Automatic answer

**Model + JSON only.** An automatic reply addressed to W1AW.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.AutoAnswer("W1AW", "Away", "02")
)
print(type(packet.payload).__name__)
```

Output:

```text
AutoAnswer
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
AutoAnswer
```

#### Bulletin

**Model + JSON only.** A bulletin identifier, text and optional group.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.Bulletin("1", "Meeting at 1900", "CLUB")
)
print(type(packet.payload).__name__)
```

Output:

```text
Bulletin
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Bulletin
```

#### NWS bulletin

**Model + JSON only.** A National Weather Service product envelope, distinct from a general bulletin.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.NWSBulletin("NWS-WARN", "Storm", "S9JbA")
)
print(type(packet.payload).__name__)
```

Output:

```text
NWSBulletin
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
NWSBulletin
```

#### Radiogram

**Model + JSON only.** One NTS radiogram record in its delivery envelope. This example carries text line 1.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.Radiogram("W1AW", aprs.Text(1, "Hello"), "001")
)
print(type(packet.payload).__name__)
```

Output:

```text
Radiogram
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Radiogram
```

#### Query

**Model + JSON only.** A query with a geographic footprint.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Query("APRS", footprint=aprs.Footprint(aprs.Coordinates(49, -72), 20)),
)
print(type(packet.payload).__name__)
```

Output:

```text
Query
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Query
```

#### Response

**Model + JSON only.** A query response listing directly heard stations. HeardStation and Trace are other response variants.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Response("W1AW", aprs.DirectStations(("N0CALL",))),
)
print(type(packet.payload).__name__)
```

Output:

```text
Response
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
      "stations": [
        "N0CALL"
      ]
    }
  }
}
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Response
```

#### Capabilities

**Model + JSON only.** A station advertises a protocol capability token.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.Capabilities((aprs.Capability("IGATE"),))
)
print(type(packet.payload).__name__)
```

Output:

```text
Capabilities
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Capabilities
```

### Other formats

#### NMEA

**Model + JSON only.** A GLL navigation sentence. GGA, RMC, VTG and WPL are also modeled.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.NMEA(aprs.GLL(aprs.Coordinates(49, -72), "123000", "A")),
)
print(type(packet.payload).__name__)
```

Output:

```text
NMEA
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
NMEA
```

#### Raw vendor weather

**Model + JSON only.** Preserve vendor bytes and their declared format; this is not a decoded weather observation.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.RawWeather("ultw", b"$ULTW0000")
)
print(type(packet.payload).__name__)
```

Output:

```text
RawWeather
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
RawWeather
```

#### Agrelo

**Model + JSON only.** Direction-finding bearing and quality.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(aprs.Header("N0CALL", "APRS"), aprs.Agrelo(123, 4))
print(type(packet.payload).__name__)
```

Output:

```text
Agrelo
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Agrelo
```

#### Maidenhead beacon

**Model + JSON only.** The historical bracket-style grid beacon. Grid bounds and center can be supplied separately.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.Maidenhead(aprs.Grid("IO91SX"))
)
print(type(packet.payload).__name__)
```

Output:

```text
Maidenhead
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Maidenhead
```

#### Legacy position

**Model + JSON only.** A historical prefix around a position.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.LegacyPosition(b"X1J ", aprs.Position(49, -72))
)
print(type(packet.payload).__name__)
```

Output:

```text
LegacyPosition
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
LegacyPosition
```

#### Non-APRS beacon

**Model + JSON only.** Plain beacon text with no APRS interpretation.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(aprs.Header("N0CALL", "APRS"), aprs.Beacon("UIDIGI ready"))
print(type(packet.payload).__name__)
```

Output:

```text
Beacon
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
Beacon
```

#### External extension

**Model + JSON only.** Preserve external-format data by name; its grammar has not been implemented.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.ExternalExtension("polygon_line", b"raw")
)
print(type(packet.payload).__name__)
```

Output:

```text
ExternalExtension
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
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
"""
)
print(type(packet.payload).__name__)
```

Output:

```text
ExternalExtension
```

## Unsupported and malformed input

Unsupported payloads are preserved as Opaque by default. This weather packet's
information field is retained, not decoded into Weather measurements:

```python
from hamkit import aprs

packet = aprs.parse_packet(
    b"N0CALL>APRS:_10090556c220s004g005t077r001p025P012h50b09900WRSW"
)
print(packet)
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Opaque(information=b'_10090556c220s004g005t077r001p025P012h50b09900WRSW', reason='unsupported information field family', diagnostic=Diagnostic(code='unsupported', message='unsupported information field family', path='$')), header_semantics=None)
```

Show that same packet as JSON:

```python
print(aprs.to_json(packet, indent=2))
```

Output:

```text
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
Malformed headers or supported payload fields return a single `Malformed` for
the entire input. Its `recovered` dictionary contains reliable values in the
ordinary packet JSON shape; it is data, not a partially valid Packet. Diagnostics
identify the fields that need attention. Unimplemented codecs remain Opaque (or
raise when requested); unknown content is not assumed malformed.

Here the latitude is valid, but the longitude is out of range:

```python
from hamkit import aprs

packet = aprs.parse_packet(b"N0CALL>APRS:!4903.50N/19000.00W-")
print(packet)
```

Output:

```text
Malformed(original_wire=b'N0CALL>APRS:!4903.50N/19000.00W-', diagnostics=(Diagnostic(code='malformed', message='coordinate out of range', path='$.payload.longitude_deg'),), recovered={'type': 'packet', 'header': {'source': 'N0CALL', 'destination': 'APRS'}, 'payload': {'type': 'position', 'messaging': False, 'latitude_deg': 49.05833333333333, 'tail': '', 'symbol': {'table_id': '/', 'code': '-'}}})
```

Show that recovery result as JSON:

```python
print(aprs.to_json(packet, indent=2))
```

Output:

```text
{
  "type": "malformed",
  "original_wire": "N0CALL>APRS:!4903.50N/19000.00W-",
  "diagnostics": [
    {
      "code": "malformed",
      "message": "coordinate out of range",
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
      "messaging": false,
      "latitude_deg": 49.05833333333333,
      "tail": "",
      "symbol": {
        "table_id": "/",
        "code": "-"
      }
    }
  }
}
```

Correct the recovered longitude from the result immediately above, then build a
strict Packet and reconstruct its wire bytes:

```python
import copy

recovered = copy.deepcopy(packet.recovered)
recovered["payload"]["longitude_deg"] = -72.0
packet = aprs.from_json_dict(recovered, expected_type=aprs.Packet)
print(aprs.serialize_packet(packet).decode("ascii"))
```

Output:

```text
N0CALL>APRS:!4903.50N/07200.00W-
```

`serialize_packet` rejects Malformed. Constructors and JSON import reject missing
mandatory values, invalid types and modeled domain constraints; raw evidence
cannot make an invalid model valid. `DecodeOptions(malformed="raise")` requests
exceptions instead of recovery. Context and resource-limit failures still raise.

`parse_packet` consumes unframed bytes. `parse_tnc2_line` requires one LF/CRLF
terminator and returns Packet or Malformed; framing errors raise. Do not strip
arbitrary binary payload bytes.

## Bytes, units and round trips

- Human-readable protocol text and identifiers use Python `str` and printable
  ASCII. Encoding does not guess UTF-8 or replace undecodable characters. Invalid
  bytes in supported text fields yield Malformed with the exact original bytes.
- Raw/binary content (UserDefined.data, Opaque.information, unsliced position tails
  and archival evidence) uses bytes. JSON represents each raw byte as the same
  Latin-1 code point: `\u0000` is byte 0 and `\u00ff` is byte 255. Export escapes
  those bytes; no surrogateescape strings are used. A str supplied to parse_packet
  is explicitly a Latin-1 wire-byte carrier, not decoded protocol text.
- Constructors enforce types, finite values, coordinate/time bounds and modeled
  field constraints before a normal model exists. The serializer revalidates
  structured data. Original wire bytes and raw codes never override edits or
  provide a fallback; explicit raw portions are encoded as their own content.
- A missing weather measurement differs from `Measurement(None, "mph")`, which
  means an unavailable reading. Zero is an actual measurement. Units are explicit;
  no automatic conversion is performed.
- `to_json_dict` and `from_json_dict` work with dictionaries. Use
  `to_json(packet, indent=2, include_defaults=True)` to show optional defaults.
- `from_json(text, expected_type=aprs.Packet)` checks the expected model.
  Unknown fields, duplicate keys, and missing or incompatible tags raise
  `JSONModelError`. Direct invalid constructors raise `ModelError` (or TypeError
  for missing arguments).
- JSON round trips preserve model values and raw evidence. They do not preserve
  whitespace, key order, or whether an optional null was originally omitted.
  `serialize_packet` encodes the model; it does not replay `original_wire`.

## Full reference

- [Illustrated JSON reference](docs/JSON_FORMAT.md): all 83 models, expanded nested
  objects, every union variant, fields, defaults, tags, units and enums.
- [Wire support by family](docs/API_COVERAGE.md): implemented subsets and gaps.
- [Naming guide](docs/NAMING.md): short public names and why some qualifiers remain.
- [Compliance vectors](docs/APRS_COMPLIANCE_VECTORS.md): specification references
  and the future packet/field test corpus. These examples are illustrations, not
  a claim that the complete corpus passes.

Run the examples and unit tests with
`python -m unittest discover -s packages/aprs/tests -v` from the repository root.
