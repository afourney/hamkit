# hamkit.aprs

Parse APRS packets, build them in Python, check them before sending, and move
them to and from JSON. Pure Python · MIT license · Python 3.11+ · no runtime
dependencies.

This is an **alpha API** with decoding and encoding for the packet families in
our [compliance corpus](docs/APRS_COMPLIANCE_VECTORS.md): positions (including
compressed, ambiguous and Mic-E), objects/items, weather, telemetry, messages,
queries/responses, status, NMEA and historical formats. Unknown or explicitly
raw formats preserve their bytes.
See [codec coverage and compatibility policies](docs/API_COVERAGE.md) for limits.

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
use their own wire layout; see the [coverage notes](docs/API_COVERAGE.md).
Serialization returns bytes. Optional fields are keyword-only.

### Position

**Wire encoding available for this example.** An uncompressed latitude/longitude
position with a car symbol, course and speed, and a comment.

Read one position packet:

```python
from hamkit import aprs

packet = aprs.parse_packet(b"N0CALL>APRS:!4903.50N/07201.75W>088/036 Hello")
print(packet)
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Position(latitude_deg=49.05833333333333, longitude_deg=-72.02916666666667, symbol=Symbol(table_id='/', code='>'), comment=' Hello', messaging=False, timestamp=None, ambiguity=0, compression=None, extensions=Extensions(motion=Motion(course_deg=88, speed_knots=36, zero_pair='unspecified'), altitude=None, phg=None, range=None, signal=None, bearing=None, dao=None, area=None, signpost=None, weather=None, storm=None, telemetry=None)), diagnostics=())
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
    "comment": " Hello",
    "extensions": {
      "motion": {
        "course_deg": 88,
        "speed_knots": 36,
        "course_code": 88,
        "speed_code": 36,
        "raw": "088/036"
      }
    }
  },
  "original_wire": "N0CALL>APRS:!4903.50N/07201.75W>088/036 Hello"
}
```

Course/speed (`088/036`) is decoded into `extensions.motion`, and `comment`
holds the text after it, including its leading space. PHG, RNG, DFS, DF
bearing and `/A=` altitude also decode into structured extensions. PHG comments
consume an optional `/` separator and trim surrounding ASCII whitespace. The
[PHGR extension](https://www.aprs.org/aprs12/probes.txt) requires a rate character
(`0`–`9`, `A`–`Z`, representing 0–35 reports per hour) followed by `/`; the public
codec consumes that delimiter and emits it on serialization. A rate without its
slash stays in the comment. These PHG conventions do not strip slashes or
whitespace from ordinary messages or other position comments. Extension-shaped text with
invalid values stays in `comment` with a diagnostic. DAO precision, base91
telemetry, weather, storm, area and signpost extensions also have structured
decoders and encoders.

When sending, measurements such as course, speed and altitude are rounded to
whole units, like coordinates. Values with no exact wire form (PHG power must
be n² watts) and values that would read back with a different meaning (a known
speed of zero with no course) raise `ConformanceError`. Modeled fields the wire
format cannot carry, such as an independent altitude reference, raise
a representability error instead of being dropped.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Position(
        49.05833333333333,
        -72.02916666666667,
        aprs.Symbol("/", ">"),
        comment=" Hello",
        extensions=aprs.Extensions(motion=aprs.Motion(88, 36)),
    ),
)
print(aprs.serialize_packet(packet).decode("utf-8"))
```

Output:

```text
N0CALL>APRS:!4903.50N/07201.75W>088/036 Hello
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
    "comment": " Hello",
    "extensions": {
      "motion": {
        "course_deg": 88,
        "speed_knots": 36
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
N0CALL>APRS:!4903.50N/07201.75W>088/036 Hello
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

These examples show equivalent Python and JSON construction, printing the
payload class name. They can also be serialized with `serialize_packet`.
Raw wrappers intentionally preserve their information bytes.

For example, encode a positionless weather report:

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
print(aprs.serialize_packet(packet).decode("utf-8"))
```

Output:

```text
N0CALL>APRS:_10171230c270s012g015t068
```

The following examples build and load these models without asking for wire
encoding. They remain useful for storing or exchanging structured data.

### Places and weather

#### Mic-E

**Wire encoding available.** Compact position data with a Mic-E message type. Omit the destination: the library packs latitude, message, ambiguity and
longitude flags into it. An explicit destination is checked against those fields. `device_code` holds the APRS 1.2 type code: the type byte that begins the status text plus any declared suffix that ends it, such as `` `_% `` (Yaesu FTM-400DR) or `]=` (Kenwood TM-D710).

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL"),
    aprs.MicE(
        47.75,
        -122.15,
        aprs.Symbol("/", ">"),
        message="en_route",
        extensions=aprs.Extensions(motion=aprs.Motion(90, 10)),
    ),
)
print(aprs.serialize_packet(packet))
```

Output:

```text
b'N0CALL>TW4UPP:`2a\x1c\x1d\x1cv>/'
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    """
{
  "type": "packet",
  "header": {
    "source": "N0CALL"
  },
  "payload": {
    "type": "mic_e",
    "latitude_deg": 47.75,
    "longitude_deg": -122.15,
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
print(aprs.serialize_packet(packet))
```

Output:

```text
b'N0CALL>TW4UPP:`2a\x1c\x1d\x1cv>/'
```

Read the resulting packet. Decoding keeps the explicit received destination:

```python
from hamkit import aprs

packet = aprs.parse_packet(b'N0CALL>TW4UPP:`2a\x1c\x1d\x1cv>/')
print(packet)
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='TW4UPP', path=()), payload=MicE(latitude_deg=47.75, longitude_deg=-122.15, symbol=Symbol(table_id='/', code='>'), message='en_route', comment='', fix='current', ambiguity=0, device_code=None, extensions=Extensions(motion=Motion(course_deg=90, speed_knots=10, zero_pair='unspecified'), altitude=None, phg=None, range=None, signal=None, bearing=None, dao=None, area=None, signpost=None, weather=None, storm=None, telemetry=None)), diagnostics=())
```

Show the same decoded packet as JSON:

```python
print(aprs.to_json(packet, indent=2))
```

Output:

```text
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "TW4UPP"
  },
  "payload": {
    "type": "mic_e",
    "latitude_deg": 47.75,
    "longitude_deg": -122.15,
    "symbol": {
      "table_id": "/",
      "code": ">"
    },
    "message": "en_route",
    "extensions": {
      "motion": {
        "course_deg": 90,
        "speed_knots": 10,
        "course_code": 90,
        "speed_code": 10
      }
    }
  },
  "original_wire": "N0CALL>TW4UPP:`2a\u001c\u001d\u001cv>/"
}
```

For a newly constructed packet, `header.destination` stays `None`; every send
recomputes it from the current payload without mutating your model. A parsed
packet instead retains its explicit address. If you change latitude, message,
ambiguity or longitude flags, clear the destination to request regeneration;
otherwise a conflicting explicit address is rejected. This example edits a
received packet and asks the library to repack it:

```python
from dataclasses import replace
from hamkit import aprs

received = aprs.parse_tnc2_line(b'N0CALL>TW4UPP:`2a\x1c\x1d\x1cv>/\r\n')
packet = aprs.Packet(
    replace(received.header, destination=None),
    replace(received.payload, latitude_deg=-47.75),
)
print(aprs.serialize_packet(packet))
```

Output:

```text
b'N0CALL>TW45PP:`2a\x1c\x1d\x1cv>/'
```

The generated destination has six characters and no SSID; path hops remain
caller-supplied. Explicit destination SSIDs are retained. The mixed wire state
`message="unknown"` cannot be uniquely generated: retain its explicit received
destination or choose a known standard/custom message. An omitted JSON
destination (or `null`) requests the same automatic behavior. Other packet types
still require a destination, and Mic-E payload JSON still requires its normal
semantic fields. Mic-E payload-only encoding can derive its packing, but
payload-only decoding still needs the actual received header.

#### Object

**Wire encoding available.** A named, timestamped object at a position.

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

**Wire encoding available.** A named item at a position, without an object timestamp.

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

**Wire encoding available.** A positionless report: wind, gust and temperature slots plus an MDHM timestamp. Measurements have explicit units. Use the same Weather model in `Extensions.weather` for located weather.

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

**Wire encoding available.** Five analog and eight digital channels. None represents an unavailable channel, not zero.

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

**Wire encoding available.** Channel names for N0CALL's telemetry. TelemetryUnits, TelemetryEquations and TelemetryBits are the other definition variants.

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

**Wire encoding available.** An automatic reply addressed to W1AW.

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

**Wire encoding available.** A bulletin identifier, text and optional group. A letter identifier makes it an announcement.

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

**Wire encoding available.** A National Weather Service product envelope, distinct from a general bulletin.

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

**Wire encoding available.** One NTS radiogram record in its delivery envelope. This example carries text line 1.

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

**Wire encoding available.** A query with a geographic footprint.

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

**Wire encoding available.** A query response listing directly heard stations. HeardStation and Trace are other response variants.

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

**Wire encoding available.** A station advertises a protocol capability token.

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

**Wire encoding available.** A GLL navigation sentence. GGA, RMC, VTG and WPL are also modeled.

A comment requires a checksum delimiter; serialization generates it automatically when needed, without changing the metadata.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.NMEA(
        aprs.GLL(aprs.Coordinates(49, -72), aprs.UTCTime(12, 30, 0), "A"), aprs.NMEAMetadata("GP"), comment="hello"
    ),
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:$GPGLL,4900,N,07200,W,123000,A*30hello
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
      "time_utc": {
        "hour": 12,
        "minute": 30,
        "second": 0
      },
      "fix_status": "A"
    },
    "metadata": {
      "talker": "GP"
    },
    "comment": "hello"
  }
}
"""
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:$GPGLL,4900,N,07200,W,123000,A*30hello
```

#### Area dimensions in degrees

Area offsets are nonnegative angular sizes, in degrees, using the corrected APRS 1.1 formula. Values from 0 through 6.534 degrees are converted to the nearest square-root code (ties to even). Classification and color remain protocol codes; no anchor or geographic transformation is inferred.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Position(
        49, -72, aprs.Symbol("\\", "l"),
        extensions=aprs.Extensions(area=aprs.Area(
            0, 1, latitude_offset_deg=0.096, longitude_offset_deg=0.096
        )),
    ),
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:!4900.00N\07200.00Wl012/112
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    r"""
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "position",
    "latitude_deg": 49,
    "longitude_deg": -72,
    "symbol": {
      "table_id": "\\",
      "code": "l"
    },
    "extensions": {
      "area": {
        "shape_code": 0,
        "color_code": 1,
        "latitude_offset_deg": 0.096,
        "longitude_offset_deg": 0.096
      }
    }
  }
}
"""
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:!4900.00N\07200.00Wl012/112
```

#### Direction-finding range in miles

`Bearing.range_miles` accepts 1–512 miles and is quantized to the nearest power-of-two exponent (ties to even). Hits and quality remain classification codes; the disputed quality-to-accuracy mapping is not inferred. `range_code` is a derived read-only property.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Position(
        49, -72, aprs.Symbol("/", "\\"),
        extensions=aprs.Extensions(
            motion=aprs.Motion(90, 10),
            bearing=aprs.Bearing(270, hits_code=7, range_miles=16, quality_code=9),
        ),
    ),
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:!4900.00N/07200.00W\090/010/270/749
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    r"""
{
  "type": "packet",
  "header": {
    "source": "N0CALL",
    "destination": "APRS"
  },
  "payload": {
    "type": "position",
    "latitude_deg": 49,
    "longitude_deg": -72,
    "symbol": {
      "table_id": "/",
      "code": "\\"
    },
    "extensions": {
      "motion": {
        "course_deg": 90,
        "speed_knots": 10
      },
      "bearing": {
        "bearing_deg": 270,
        "hits_code": 7,
        "range_miles": 16,
        "quality_code": 9
      }
    }
  }
}
"""
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:!4900.00N/07200.00W\090/010/270/749
```

#### Mic-E with PHG

Mic-E course and speed occupy the fixed body; PHG uses the comment extension slot. PHG rates still require `phg_rate`. A Mic-E DF bearing uses a course/speed prefix in the comment and cannot share that slot with PHG.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL"),
    aprs.MicE(
        49, -72, aprs.Symbol("/", ">"), message="off_duty",
        extensions=aprs.Extensions(motion=aprs.Motion(90, 10), phg=aprs.PHG(25, 20, 3)),
    ),
)
print(aprs.serialize_packet(packet))
```

Output:

```text
b'N0CALL>TYPP0P:`dX\x1c\x1d\x1cv>/PHG5130'
```

Build the same packet from JSON:

```python
from hamkit import aprs

packet = aprs.from_json(
    r"""
{
  "type": "packet",
  "header": {
    "source": "N0CALL"
  },
  "payload": {
    "type": "mic_e",
    "latitude_deg": 49,
    "longitude_deg": -72,
    "symbol": {
      "table_id": "/",
      "code": ">"
    },
    "message": "off_duty",
    "extensions": {
      "motion": {
        "course_deg": 90,
        "speed_knots": 10
      },
      "phg": {
        "power_w": 25,
        "height_haat_ft": 20,
        "gain_dbi": 3
      }
    }
  }
}
"""
)
print(aprs.serialize_packet(packet))
```

Output:

```text
b'N0CALL>TYPP0P:`dX\x1c\x1d\x1cv>/PHG5130'
```

#### DAO precision from coordinates

Choose `DAO(encoding="decimal")` for thousandths of a minute or `"base91"` for 1/91 of a hundredth-minute. `datum="W"` is WGS84; letter case is packed automatically. `encoding=None` sends datum only. Parsed coordinates already include supported DAO precision. Editing those coordinates recomputes the codes, without using the received `raw` evidence. Added precision with ambiguity or compressed positions is refused; received combinations retain their baseline coordinates and DAO evidence with diagnostics.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Position(
        49.05837, -72.029215, aprs.Symbol("/", ">"),
        extensions=aprs.Extensions(dao=aprs.DAO(encoding="decimal")),
    ),
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:!4903.50N/07201.75W>!W23!
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
    "latitude_deg": 49.05837,
    "longitude_deg": -72.029215,
    "symbol": {
      "table_id": "/",
      "code": ">"
    },
    "extensions": {
      "dao": {
        "encoding": "decimal"
      }
    }
  }
}
"""
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:!4903.50N/07201.75W>!W23!
```

#### Altitude in feet or meters

Every supported altitude encoder accepts `Measurement(value, "feet")` or `Measurement(value, "meters")`. Conversion precedes wire rounding: `/A=` and compressed altitude use feet, Mic-E uses meters, and GGA uses meters. GGA exposes `altitude_msl` and `geoid_separation` as separate measurements; conversion never changes their reference datum.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.Position(
        49, -72, aprs.Symbol("/", ">"),
        extensions=aprs.Extensions(
            altitude=aprs.Altitude(aprs.Measurement(100, "meters"), "feet_extension")
        ),
    ),
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:!4900.00N/07200.00W>/A=000328
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
    "latitude_deg": 49,
    "longitude_deg": -72,
    "symbol": {
      "table_id": "/",
      "code": ">"
    },
    "extensions": {
      "altitude": {
        "measurement": {
          "value": 100,
          "unit": "meters"
        },
        "encoding": "feet_extension"
      }
    }
  }
}
"""
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:!4900.00N/07200.00W>/A=000328
```

#### NMEA time and unresolved dates

`UTCTime` stores UTC clock components and fractional seconds. `NMEADate(day, month, year_mod_100)` retains the two-digit year without choosing a century. A missing time/date is `None`; a partial date or unknown seconds stays partial. Partial received fields remain inspectable with diagnostics, but cannot be serialized until the caller supplies the required components. Void fixes may omit time and date; active fixes require time and RMC also requires a date. The library never consults the host clock.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.NMEA(
        aprs.RMC(
            aprs.UTCTime(12, 35, 19.25), aprs.NMEADate(23, 3, 94),
            "A", aprs.Coordinates(49, -72),
        ),
        aprs.NMEAMetadata("GP"),
    ),
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:$GPRMC,123519.25,A,4900,N,07200,W,,,230394,,
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
      "type": "rmc",
      "time_utc": {
        "hour": 12,
        "minute": 35,
        "second": 19.25
      },
      "date": {
        "day": 23,
        "month": 3,
        "year_mod_100": 94
      },
      "fix_status": "A",
      "coordinates": {
        "latitude_deg": 49,
        "longitude_deg": -72
      }
    },
    "metadata": {
      "talker": "GP"
    }
  }
}
"""
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:$GPRMC,123519.25,A,4900,N,07200,W,,,230394,,
```

#### Raw vendor weather

**Wire encoding available.** Preserve vendor bytes and their declared format; this is not a decoded weather observation.

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

**Wire encoding available.** Direction-finding bearing and quality.

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

**Wire encoding available.** The historical `[Grid Locator]Comment` beacon includes both brackets. It has no separate symbol field. `Grid.bounds` and `Grid.center` are computed from the locator.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"), aprs.Maidenhead(aprs.Grid("IO91SX"))
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:[IO91SX]
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
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:[IO91SX]
```

#### Legacy position

**Wire encoding available.** A historical prefix around a position. APRS101
allowed a `!` position within the first 40 bytes of other text; the APRS 1.1
addendum deprecates that search, so parsing returns a `Beacon` unless you pass
`policy=aprs.APRS_IS(legacy_positions=True)`. Use that policy for sending too.

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

**Wire encoding available.** Plain beacon text with no APRS interpretation.

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

**Wire encoding available.** Preserve external-format data by name; its grammar has not been implemented.

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

Policies select envelope limits and payload interpretation. `RF()` and
`APRS_IS()` return the same immutable `EnvelopePolicy` type. Both enable the
supported comment, UTF-8, expanded telemetry and weather extensions by default;
modern Mic-E device identifiers and fixed-width water-height reinterpretation
require explicit opt-in. Use
`aprs.RF(extensions=set())` or `aprs.APRS_IS(extensions=set())` for the implemented
APRS 1.1 baseline. Unknown extension identifiers are rejected.

Direct construction supports custom patterns, limits and extensions. Factories
are optional. This example also saves and reloads the fully specified policy:

```python
from hamkit import aprs

policy = aprs.EnvelopePolicy(
    source_pattern=r"src_[0-9]+",
    destination_pattern=r"dst_[A-Z]+",
    path_address_pattern=r"via_[a-z]+",
    max_path_entries=1,
    max_information_bytes=200,
    max_tnc2_line_bytes=None,
    extensions={"utf8_text"},
    legacy_positions=False,
    byte_fallback="reject",
)
restored = aprs.from_json(aprs.to_json(policy), expected_type=aprs.EnvelopePolicy)
packet = aprs.Packet(aprs.Header("src_12", "dst_AB"), aprs.Status("Café"))
print(aprs.serialize_packet(packet, policy=restored).decode("utf-8"))
```

Output:

```text
src_12>dst_AB:>Café
```

Direct construction defaults to empty extensions; factory omission and an
explicit empty collection are different choices. Policies store all resolved
values in JSON, with no preset label. UTF-8 applies only to designated free-text
fields; protocol tokens stay ASCII. Byte fallback and legacy-position search
are separate settings. Disabled comment extensions preserve matching text.
See [packet policies](docs/ENVELOPE_POLICIES.md) for the catalog, defaults,
Mic-E conflicts, weather interpretation and third-party handling.

Positionless weather decodes into measurements with explicit units and a timestamp:

```python
from hamkit import aprs

packet = aprs.parse_packet(
    b"N0CALL>APRS:_10090556c220s004g005t077r001p025P012h50b09900WRSW"
)
print(packet)
```

Output:

```text
Packet(header=Header(source='N0CALL', destination='APRS', path=()), payload=Weather(wind_direction=Measurement(value=220.0, unit='degrees'), wind_speed=Measurement(value=4.0, unit='mph'), gust=Measurement(value=5.0, unit='mph'), temperature=Measurement(value=77.0, unit='fahrenheit'), humidity=Measurement(value=50.0, unit='percent'), pressure=Measurement(value=990.0, unit='hPa'), rain_1h=Measurement(value=0.01, unit='inches'), rain_24h=Measurement(value=0.25, unit='inches'), rain_since_midnight=Measurement(value=0.12, unit='inches'), snow_24h=None, luminosity=None, rain_counter=None, water_height=None, radiation=None, battery_voltage=None, software_code='W', device_code='RSW', timestamp=Timestamp(kind='mdhm_utc', hour=5, minute=56, day=9, second=None, month=10), comment=''), diagnostics=())
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
    "type": "weather",
    "wind_direction": {
      "value": 220.0,
      "unit": "degrees",
      "raw": "220"
    },
    "wind_speed": {
      "value": 4.0,
      "unit": "mph",
      "raw": "004"
    },
    "gust": {
      "value": 5.0,
      "unit": "mph",
      "raw": "005"
    },
    "temperature": {
      "value": 77.0,
      "unit": "fahrenheit",
      "raw": "077"
    },
    "humidity": {
      "value": 50.0,
      "unit": "percent",
      "raw": "50"
    },
    "pressure": {
      "value": 990.0,
      "unit": "hPa",
      "raw": "09900"
    },
    "rain_1h": {
      "value": 0.01,
      "unit": "inches",
      "raw": "001"
    },
    "rain_24h": {
      "value": 0.25,
      "unit": "inches",
      "raw": "025"
    },
    "rain_since_midnight": {
      "value": 0.12,
      "unit": "inches",
      "raw": "012"
    },
    "software_code": "W",
    "device_code": "RSW",
    "timestamp": {
      "kind": "mdhm_utc",
      "hour": 5,
      "minute": 56,
      "day": 9,
      "month": 10
    },
    "raw": "10090556c220s004g005t077r001p025P012h50b09900WRSW"
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
Malformed(original_wire=b'N0CALL>APRS:!4903.50N/19000.00W-', diagnostics=(Diagnostic(code='malformed', message='coordinate out of range', path='$.payload'), Diagnostic(code='malformed', message='coordinate out of range', path='$.payload.longitude_deg')), recovered={'type': 'packet', 'header': {'source': 'N0CALL', 'destination': 'APRS'}, 'payload': {'type': 'position', 'messaging': False, 'latitude_deg': 49.05833333333333, 'comment': '', 'symbol': {'table_id': '/', 'code': '-'}}})
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
      "path": "$.payload"
    },
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
  explicit. Encoders convert supported measurement units to the selected wire
  units and quantize to field precision; they reject overflow.
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
  and the complete packet/field test corpus. Every row is tested, including
  the individual packets from archived application sequences. Accumulated
  receiver-state assertions remain provenance only, outside this stateless codec.

Run the examples and unit tests with
`python -m pytest packages/aprs/tests -q` from the repository root.
