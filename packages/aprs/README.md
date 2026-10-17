# hamkit.aprs

Parse APRS packets, build them in Python, check them before sending, and move
them to and from JSON. Pure Python · MIT license · Python 3.10+ · no runtime
dependencies.

This is an **alpha API**. Basic status, position, message and acknowledgment
packets work today, along with the envelope/raw formats shown below. Other
families have usable Python and JSON models but **no wire codec yet**. Those
sections say **Model + JSON only** and print the constructed model's name;
they do not claim to produce a TNC2 line. Calling `serialize_packet` on those
models raises `CodecNotImplementedError`.

Install from a repository checkout with `python -m pip install -e packages/aprs`.
Construction examples run independently, including those that embed JSON
directly. After each parsing example, the JSON display block uses `packet` from
the block immediately above it, as does the repair example. Each block prints
one result, followed by its exact output; the examples are checked by tests.
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
- [Received packets](#received-packets) — out-of-spec, unsupported and malformed input
- [Checking before sending](#checking-before-sending)
- [Text, bytes, units and round trips](#text-bytes-units-and-round-trips)
- [Full reference](#full-reference)

## Parse a packet

Start with one status packet. `parse_packet` reads the whole TNC2 envelope and
returns a `Packet` with a `Header` and a typed payload.

```python
from hamkit import aprs

packet = aprs.parse_packet(b"N0CALL>APRS:>Ready")
print(packet)
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Status(text='Ready', timestamp=None, grid=None, symbol=None, beam=None), diagnostics=())
```

Show that same result as JSON:

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
bytes; it is separate from the structured fields and is never used when the
packet is serialized again. `diagnostics` lists anything about the received
bytes that broke APRS rules; it is empty here. JSON type tags identify models,
not Python class names.

## Build a status packet

**Wire encoding available** for basic status text. These two inputs build the
same packet and produce the same TNC2 line. `from_json` builds the Packet;
`serialize_packet` checks it and converts it to bytes. `.decode("utf-8")`
displays these examples without a Python bytes prefix.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(aprs.Header("N0CALL", "APRS"), aprs.Status("Ready"))
print(aprs.serialize_packet(packet).decode("utf-8"))
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
print(aprs.serialize_packet(packet).decode("utf-8"))
```

Output:

```text
N0CALL>APRS:>Ready
```

## Working wire examples

Each example uses the supported subset of its family. More elaborate fields can
still require an unimplemented codec; see the [coverage notes](docs/API_COVERAGE.md).
Serialization returns bytes. Optional fields are keyword-only.

### Position

**Wire encoding available for this example.** An uncompressed latitude/longitude
position with a car symbol and a comment.

Read one position packet:

```python
from hamkit import aprs

packet = aprs.parse_packet(b"N0CALL>APRS:!4903.50N/07201.75W>Hello")
print(packet)
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Position(latitude_deg=49.05833333333333, longitude_deg=-72.02916666666667, symbol=Symbol(table_id='/', code='>'), comment='Hello', messaging=False, timestamp=None, ambiguity=0, compression=None, extensions=Extensions(motion=None, altitude=None, phg=None, range=None, signal=None, bearing=None, dao=None, area=None, signpost=None, weather=None, storm=None, telemetry=None)), diagnostics=())
```

Show that same result as JSON:

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
      "table_id": "/",
      "code": ">"
    },
    "comment": "Hello"
  },
  "original_wire": "N0CALL>APRS:!4903.50N/07201.75W>Hello"
}
```

`comment` holds the free text after the position. Data extensions that this
version does not decode yet, such as course/speed or altitude, stay in
`comment` exactly as received.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Position(
        49.05833333333333, -72.02916666666667, aprs.Symbol("/", ">"), comment="Hello"
    ),
)
print(aprs.serialize_packet(packet).decode("utf-8"))
```

Output:

```text
N0CALL>APRS:!4903.50N/07201.75W>Hello
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
      "table_id": "/",
      "code": ">"
    },
    "comment": "Hello"
  }
}
"""
)
print(aprs.serialize_packet(packet).decode("utf-8"))
```

Output:

```text
N0CALL>APRS:!4903.50N/07201.75W>Hello
```

### Message

**Wire encoding available for this example.** A message addressed to W1AW with message ID 003.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.Message("W1AW", "Hello", message_id="003")
)
print(aprs.serialize_packet(packet).decode("utf-8"))
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
print(aprs.serialize_packet(packet).decode("utf-8"))
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
print(aprs.serialize_packet(packet).decode("utf-8"))
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
print(aprs.serialize_packet(packet).decode("utf-8"))
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
print(aprs.serialize_packet(packet).decode("utf-8"))
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
print(aprs.serialize_packet(packet).decode("utf-8"))
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
print(aprs.serialize_packet(packet).decode("utf-8"))
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
print(aprs.serialize_packet(packet).decode("utf-8"))
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
print(aprs.serialize_packet(packet).decode("utf-8"))
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
print(aprs.serialize_packet(packet).decode("utf-8"))
```

Output:

```text
N0CALL>APRS:,invalid fix
```

### Reserved data

**Wire encoding available for this example.** Build an information field with a data type identifier APRS101 lists as unused. Parsing it returns Opaque.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(aprs.Header("N0CALL", "APRS"), aprs.Reserved(ord("&"), b"data"))
print(aprs.serialize_packet(packet).decode("utf-8"))
```

Output:

```text
N0CALL>APRS:&data
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
    "dti": 38,
    "data": "data"
  }
}
"""
)
print(aprs.serialize_packet(packet).decode("utf-8"))
```

Output:

```text
N0CALL>APRS:&data
```

### Opaque data

**Wire encoding available for this example.** Keep unsupported information bytes without inventing a structured interpretation.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(aprs.Header("N0CALL", "APRS"), aprs.Opaque(b"~vendor data"))
print(aprs.serialize_packet(packet).decode("utf-8"))
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
print(aprs.serialize_packet(packet).decode("utf-8"))
```

Output:

```text
N0CALL>APRS:~vendor data
```

## Model and JSON examples

**Model + JSON only** means the values below can be built, inspected, checked,
saved and loaded now, but cannot yet be serialized to APRS wire bytes. Both
forms print the same payload class name to confirm the model they construct.
The JSON is the actual data shape, not a proposed wire encoding. No future wire
output is shown.

For example, this is what happens if you ask the current encoder to write a
weather report to the wire:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Weather(
        wind_direction=aprs.Measurement(270, "degrees"),
        wind_speed=aprs.Measurement(12, "mph"),
        gust=aprs.Measurement(15, "mph"),
        temperature=aprs.Measurement(68, "fahrenheit"),
        timestamp=aprs.Timestamp.mdhm(10, 17, 12, 30),
    ),
)
try:
    print(aprs.serialize_packet(packet).decode("utf-8"))
except aprs.CodecNotImplementedError as error:
    print(type(error).__name__)
```

Output:

```text
CodecNotImplementedError
```

The following examples build and load these models without asking for wire
encoding. They remain useful for storing or exchanging structured data.

### Places and weather

#### Mic-E

**Model + JSON only.** Compact position data with a Mic-E message type. A future encoder derives the destination address from the latitude and message.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.MicE(
        49,
        -72,
        aprs.Symbol("/", ">"),
        message="en_route",
        extensions=aprs.Extensions(motion=aprs.Motion(90, 10)),
    ),
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
    "latitude_deg": 49,
    "longitude_deg": -72,
    "symbol": {
      "table_id": "/",
      "code": ">"
    },
    "message": "en_route",
    "extensions": {
      "motion": {
        "course_deg": 90,
        "speed_knots": 10
      }
    }
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
        "AID #2",
        49,
        -72,
        aprs.Symbol("/", "-"),
        timestamp=aprs.Timestamp.dhm(17, 12, 30),
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
    aprs.Header("N0CALL", "APRS"), aprs.Item("WATER", 49, -72, aprs.Symbol("/", "-"))
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
    "latitude_deg": 49,
    "longitude_deg": -72,
    "symbol": {
      "table_id": "/",
      "code": "-"
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

**Model + JSON only.** A positionless report: wind, gust and temperature slots plus an MDHM timestamp. Measurements have explicit units. Use the same Weather model in `Extensions.weather` for located weather.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Weather(
        wind_direction=aprs.Measurement(270, "degrees"),
        wind_speed=aprs.Measurement(12, "mph"),
        gust=aprs.Measurement(None, "mph"),
        temperature=aprs.Measurement(68, "fahrenheit"),
        pressure=aprs.Measurement(1013.2, "hPa"),
        timestamp=aprs.Timestamp.mdhm(10, 17, 12, 30),
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
    "gust": {
      "value": null,
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

**Model + JSON only.** Five analog and eight digital channels. None represents an unavailable channel, not zero.

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

**Model + JSON only.** Channel names for N0CALL's telemetry. TelemetryUnits, TelemetryEquations and TelemetryBits are the other definition variants.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.TelemetryDefinition("N0CALL", aprs.TelemetryParameters(("Temp", "Volts"))),
)
print(type(packet.payload).__name__)
```

Output:

```text
TelemetryDefinition
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
    "type": "telemetry_definition",
    "addressee": "N0CALL",
    "definition": {
      "type": "telemetry_parameters",
      "channels": [
        "Temp",
        "Volts"
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
TelemetryDefinition
```

### Messages and queries

#### Automatic answer

**Model + JSON only.** An automatic reply addressed to W1AW.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.AutoAnswer("W1AW", "Away", previous_ack="02")
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

**Model + JSON only.** A bulletin identifier, text and optional group. A letter identifier makes it an announcement.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.Bulletin("1", "Meeting at 1900", group="CLUB")
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
    aprs.Header("N0CALL", "APRS"),
    aprs.NWSBulletin("NWS-WARN", "Storm", reference_id="S9JbA"),
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
    aprs.Header("N0CALL", "APRS"),
    aprs.Radiogram("W1AW", aprs.NTSText(1, "Hello"), message_id="001"),
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
      "type": "nts_text",
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
    aprs.NMEA(
        aprs.GLL(aprs.Coordinates(49, -72), "123000", "A"), aprs.NMEAMetadata("GP")
    ),
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
    },
    "metadata": {
      "talker": "GP"
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

**Model + JSON only.** The historical bracket-style grid beacon. `Grid.bounds` and `Grid.center` are computed from the locator.

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
    aprs.Header("N0CALL", "APRS"),
    aprs.LegacyPosition(b"X1J ", aprs.Position(49, -72, aprs.Symbol("/", "-"))),
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
      "latitude_deg": 49,
      "longitude_deg": -72,
      "symbol": {
        "table_id": "/",
        "code": "-"
      }
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

## Received packets

Real traffic is often slightly outside the specification. `parse_packet`
sorts what it receives into three outcomes:

- **Out of spec but usable** — a `Packet`, with each departure from APRS rules
  listed in `packet.diagnostics` as `"nonconforming"`.
- **No decoder yet** — a `Packet` whose payload is `Opaque`, keeping the bytes.
- **Undecodable fields** — one `Malformed` result for the whole input.

This status is longer than 62 bytes, and its `é` is a Latin-1 byte rather than
UTF-8. Both are recorded, and the text is still available:

```python
from hamkit import aprs

packet = aprs.parse_packet(
    b"N0CALL>APRS:>Caf\xe9 open until midnight, coffee and QSL cards at the front desk"
)
print(packet)
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Status(text='Café open until midnight, coffee and QSL cards at the front desk', timestamp=None, grid=None, symbol=None, beam=None), diagnostics=(Diagnostic(code='nonconforming', message='text is not valid UTF-8; decoded as Latin-1', path='$.payload.text'), Diagnostic(code='nonconforming', message='status exceeds 62 bytes', path='$.payload.text')))
```

Show that same result as JSON:

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
    "text": "Caf\u00e9 open until midnight, coffee and QSL cards at the front desk"
  },
  "original_wire": "N0CALL>APRS:>Caf\u00e9 open until midnight, coffee and QSL cards at the front desk",
  "diagnostics": [
    {
      "code": "nonconforming",
      "message": "text is not valid UTF-8; decoded as Latin-1",
      "path": "$.payload.text"
    },
    {
      "code": "nonconforming",
      "message": "status exceeds 62 bytes",
      "path": "$.payload.text"
    }
  ]
}
```

Text fields accept UTF-8, as the APRS 1.2 addendum allows for messages,
bulletins, status and comments. Bytes that are not valid UTF-8 are read as
Latin-1 with a diagnostic, never dropped or replaced. Pass `profile="rf"` to
also report AX.25 address and size limits.

Unsupported payloads are kept as `Opaque`. This weather packet's information
field is retained, not decoded into Weather measurements:

```python
from hamkit import aprs

packet = aprs.parse_packet(
    b"N0CALL>APRS:_10090556c220s004g005t077r001p025P012h50b09900WRSW"
)
print(packet)
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Opaque(information=b'_10090556c220s004g005t077r001p025P012h50b09900WRSW', diagnostic=Diagnostic(code='unsupported', message='unsupported information field family', path='$')), diagnostics=())
```

Show that same result as JSON:

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
    "diagnostic": {
      "code": "unsupported",
      "message": "unsupported information field family"
    }
  },
  "original_wire": "N0CALL>APRS:_10090556c220s004g005t077r001p025P012h50b09900WRSW"
}
```

Pass `unsupported="raise"` to require an implemented decoder.

When a field cannot be decoded at all, the result is a single `Malformed`. Its
`recovered` dictionary contains the reliable values in the ordinary packet JSON
shape, `header` returns the header when it was intact, and each diagnostic
names the field that needs attention. Here the latitude is valid, but the
longitude is out of range:

```python
from hamkit import aprs

packet = aprs.parse_packet(b"N0CALL>APRS:!4903.50N/19000.00W-")
print(packet)
```

Output:

```text
Malformed(original_wire=b'N0CALL>APRS:!4903.50N/19000.00W-', diagnostics=(Diagnostic(code='malformed', message='coordinate out of range', path='$.payload.longitude_deg'),), recovered={'type': 'packet', 'header': {'source': 'N0CALL', 'destination': 'APRS'}, 'payload': {'type': 'position', 'messaging': False, 'latitude_deg': 49.05833333333333, 'comment': '', 'symbol': {'table_id': '/', 'code': '-'}}})
```

Show that same result as JSON:

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
      "comment": "",
      "symbol": {
        "table_id": "/",
        "code": "-"
      }
    }
  }
}
```

Correct the recovered longitude from the result immediately above, then build
a Packet and reconstruct its wire bytes:

```python
import copy

recovered = copy.deepcopy(packet.recovered)
recovered["payload"]["longitude_deg"] = -72.0
packet = aprs.from_json_dict(recovered, expected_type=aprs.Packet)
print(aprs.serialize_packet(packet).decode("utf-8"))
```

Output:

```text
N0CALL>APRS:!4903.50N/07200.00W-
```

`malformed="raise"` requests exceptions instead of recovery. Context and
resource-limit failures always raise. `parse_packet` consumes unframed bytes;
`parse_tnc2_line` requires one LF/CRLF terminator, as read from APRS-IS or a
TNC. Do not strip arbitrary binary payload bytes.

## Checking before sending

Constructors reject only values that cannot exist on the wire, or that
contradict another field: an out-of-range latitude, a `{` inside message text,
an invalid timestamp. Limits a transmitter could still break are checked when
a packet is sent. `serialize_packet` refuses with `ConformanceError`, which
lists every finding; `check_packet` returns the same findings without
raising, and `validate_packet` raises exactly as `serialize_packet` would.

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Message(
        "W1AW",
        "This message is far too long to fit in a single APRS message frame, so it is refused.",
        message_id="7",
    ),
)
try:
    aprs.serialize_packet(packet)
except aprs.ConformanceError as error:
    print(error.diagnostics)
```

Output:

```text
(Diagnostic(code='nonconforming', message='exceeds 67 bytes', path='$.payload.text'),)
```

## Text, bytes, units and round trips

- Free text — messages, bulletins, status and comments — is any Python `str`
  and is sent as UTF-8. Protocol tokens such as callsigns, addressees, message
  IDs and object names are printable ASCII. Lengths are counted in UTF-8 bytes.
- Binary content (`UserDefined.data`, `Opaque.information`, raw evidence) uses
  `bytes`. JSON represents each byte as the same Latin-1 code point: `\u0000` is
  byte 0 and `\u00ff` is byte 255. `parse_packet` accepts bytes only; encode
  text lines first, for example `line.encode()`.
- Optional fields are keyword-only, so `Position(lat, lon, symbol, comment=...)`.
  Values that follow from other fields are properties: `Grid.bounds`,
  `PHG.range_miles`, `Compression.type_value`, `Bulletin.announcement`,
  `Position.ambiguity_extent` and similar.
- `raw` evidence fields, `original_wire` and `diagnostics` are kept and
  round-trip through JSON, but they are ignored by equality and never override
  the structured fields.
- A missing weather measurement differs from `Measurement(None, "mph")`, which
  means an unavailable reading. Zero is an actual measurement. Units are
  explicit; no automatic conversion is performed.
- `to_json_dict` and `from_json_dict` work with dictionaries. Use
  `to_json(packet, indent=2, include_defaults=True)` to show optional defaults.
  `from_json(text, expected_type=aprs.Packet)` checks the expected model.
  Unknown fields, duplicate keys, and missing or incompatible tags raise
  `JSONModelError`; invalid constructor values raise `ModelError`.
- JSON round trips preserve model values and evidence. They do not preserve
  whitespace, key order, or whether an optional null was originally omitted.
  `serialize_packet` encodes the model; it does not replay `original_wire`.

See [unresolved specification questions](docs/UNRESOLVED_SPEC.md) for NMEA
profile limits, conflicting extension descriptions and future encoding
decisions.

## Full reference

- [Illustrated JSON reference](docs/JSON_FORMAT.md): every model, expanded
  nested objects, every union variant, fields, defaults, tags, units and enums.
- [Wire support by family](docs/API_COVERAGE.md): implemented subsets and gaps.
- [Naming guide](docs/NAMING.md): public names and why some qualifiers remain.
- [Compliance vectors](docs/APRS_COMPLIANCE_VECTORS.md): specification references
  and the future packet/field test corpus. These examples are illustrations, not
  a claim that the complete corpus passes.

Run the examples and unit tests with
`python -m unittest discover -s packages/aprs/tests -v` from the repository root.
