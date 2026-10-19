# hamkit.aprs

[![PyPI - Version](https://img.shields.io/pypi/v/hamkit-uls.svg)](https://pypi.org/project/hamkit-uls)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/hamkit-uls.svg)](https://pypi.org/project/hamkit-uls)

---

> [!NOTE]  
> `hamkit.aprs` is a _small standalone component_ of [`hamkit`](https://pypi.org/project/hamkit/). You can use it by itself (see below) if APRS parsing and rendering is all that you need. Alternatively, install the entire collection of HamKit modules with `pip install hamkit`.

## Parse APRS packets and build them in Python.

Pure Python · MIT license · Python 3.11+ · no runtime dependencies.

```console
pip install hamkit-aprs
```

### Parse a packet

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

### Build a status packet

Build a packet with Python:

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

## Choose a policy

Every parse, check and serialize function takes `policy=`. The default is
`aprs.APRS_IS()`; pass `aprs.RF()` for AX.25 radio rules.

Consider the following example. This packet came from APRS-IS, where a
two-character SSID and the `qAR` construct are normal. Read under `RF()`, it
still decodes, and the diagnostics note what RF would not allow:

```python
from hamkit import aprs

packet = aprs.parse_packet(b"N0CALL-AB>APRS,qAR,W1AW:>Ready", policy=aprs.RF())
print(packet)
```

Output:

```text
Packet(header=Header(source='N0CALL-AB', destination='APRS', path=(Hop(address='qAR', repeated=False), Hop(address='W1AW', repeated=False))), payload=Status(text='Ready', timestamp=None, grid=None, symbol=None, beam=None), diagnostics=(Diagnostic(code='nonconforming', message='address does not match source_pattern', path='$.header.source'), Diagnostic(code='nonconforming', message='address does not match path_address_pattern', path='$.header.path[0].address')))
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
    "source": "N0CALL-AB",
    "destination": "APRS",
    "path": [
      {
        "address": "qAR"
      },
      {
        "address": "W1AW"
      }
    ]
  },
  "payload": {
    "type": "status",
    "text": "Ready"
  },
  "original_wire": "N0CALL-AB>APRS,qAR,W1AW:>Ready",
  "diagnostics": [
    {
      "code": "nonconforming",
      "message": "address does not match source_pattern",
      "path": "$.header.source"
    },
    {
      "code": "nonconforming",
      "message": "address does not match path_address_pattern",
      "path": "$.header.path[0].address"
    }
  ]
}
```

Sending is strict under the same policy. The packet is sent unchanged under the
default `APRS_IS()`, but `RF()` refuses the source address:

```python
from hamkit import aprs

packet = aprs.Packet(aprs.Header("N0CALL-AB", "APRS"), aprs.Status("Ready"))
try:
    aprs.serialize_packet(packet, policy=aprs.RF())
except aprs.ConformanceError as error:
    print(error.diagnostics)
```

Output:

```text
(Diagnostic(code='nonconforming', message='address does not match source_pattern', path='$.header.source'),)
```

## Design principles

**The developer never does the encoding.**

- The developer gives plain values in normal units, like degrees, knots, feet
  or watts, or a named choice.
- The library turns those into whatever the wire format needs: codes, packed
  destinations, unit conversions.
- The developer never has to work out a wire code or choose how something is
  encoded.

**Strict APRS 1.1 by default, with optional 1.2 proposals.**

- With nothing turned on, the library follows APRS 1.1 (defined as
  [APRS 1.0.1](http://www.aprs.org/doc/APRS101.PDF) plus the
  [APRS 1.1 addendum](http://www.aprs.org/aprs11.html)).
- Each [APRS 1.2](https://www.aprs.org/aprs12.html) proposal
  can be switched on or off in the policy. Many policies are on by default.
- On by default: 1.2 proposals that add rather than re-interpret structure.
  For example, extensions that find structure inside comment text are
  on by default.
- Off by default: proposals that change the interpretation of existing structured
  fields. For example, a proposal that adds a scaling factor to supersonic speeds,
  is off by default, as it changes how a speed of 799 should be interpreted.

**One policy object controls the rules, for receiving and for sending.**

- An `EnvelopePolicy` holds the envelope limits (address patterns, path length,
  information and line size) and the set of switched-on extensions.
- The same `policy=` argument is accepted by every parse, check and serialize
  function, so a packet is read and written under the same rules.
- `aprs.RF()` and `aprs.APRS_IS()` build the usual policies for radio and for
  APRS-IS; `APRS_IS()` is the default. Pass `extensions=set()` for the plain
  APRS 1.1 baseline, or construct an `EnvelopePolicy` directly for custom limits.
- Policies are immutable and round-trip through JSON. See
  [Packet policies](https://github.com/afourney/hamkit/blob/main/packages/aprs/docs/ENVELOPE_POLICIES.md).

**Lenient when receiving, strict when sending.**

- Parsing recovers as much as it can. A packet that breaks a rule but can still
  be understood is decoded anyway, and each departure from the specification is
  listed in `packet.diagnostics`.
- A payload type with no decoder yet comes back as `Opaque`, keeping its bytes.
  Input that cannot be decoded comes back as a `Malformed` result holding the
  fields that could be recovered, rather than raising (unless you pass
  `malformed="raise"`).
- Sending never repeats those mistakes: `serialize_packet` refuses anything that
  does not conform, and `check_packet` lists every problem first. See
  [Received packets](#received-packets) and
  [Checking before sending](#checking-before-sending).

## Find an example

- [Parse a packet](#parse-a-packet)
- [Build a status packet](#build-a-status-packet) — Python and JSON
- [Choose a policy](#choose-a-policy) — decoding and encoding under `RF()`
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

## Working wire examples

Each example builds a packet in Python and from JSON, and prints what is sent.
See [wire support by family](https://github.com/afourney/hamkit/blob/main/packages/aprs/docs/API_COVERAGE.md)
for every field each family supports.

### Position

A position with a car symbol, course and speed, and a comment.

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

The course and speed (`088/036`) are decoded into `extensions.motion`, and
`comment` holds the rest of the text. Other comment extensions, such as altitude
and PHG, decode the same way.

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

A message addressed to W1AW with message ID 003.

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

Acknowledge message 003.

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

A packet that carries another complete packet.

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

Application-defined data, tagged with a user ID and type.

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

A packet marked as invalid or test data.

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

Data under a type character that APRS reserves for future use.

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

Data the library has no decoder for, kept as bytes.

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

These examples build each remaining payload type in Python and from JSON, and
print the payload class name. Any of them can be sent with `serialize_packet`.

For example, encode a weather report:

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

### Places and weather

#### Mic-E

A compact position with a Mic-E message. Leave out the destination: Mic-E
packs part of the position into it, and the library fills it in when sending.

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

Read the resulting packet:

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

A parsed packet keeps the destination it was received with. After editing its
position, set the destination to `None` so the library computes it again.

#### Object

A named, timestamped object at a position.

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

A named item at a position, without an object timestamp.

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

A weather report with no position. Each measurement carries its unit. For
weather at a position, put the same `Weather` in `Extensions.weather`.

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

Five analog and eight digital channels.

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

Channel names for N0CALL's telemetry.

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

An automatic reply addressed to W1AW.

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

A bulletin to a group.

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

A National Weather Service bulletin.

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

One line of an NTS radiogram.

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

A query with a geographic footprint.

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

A response listing the stations heard directly.

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

A station advertises a protocol capability token.

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

A GPS sentence (GLL) with a comment. The library computes the checksum.

Build with Python:

```python
from hamkit import aprs

packet = aprs.Packet(
    aprs.Header("N0CALL", "APRS"),
    aprs.NMEA(
        aprs.GLL(aprs.Coordinates(49, -72), aprs.UTCTime(12, 30, 0), "active"), aprs.NMEAMetadata("GP"), comment="hello"
    ),
)
print(aprs.serialize_packet(packet).decode())
```

Output:

```text
N0CALL>APRS:$GPGLL,4900.00,N,07200.00,W,123000,A*30hello
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
      "fix_status": "active"
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
N0CALL>APRS:$GPGLL,4900.00,N,07200.00,W,123000,A*30hello
```

#### Raw vendor weather

Weather data in a vendor format, kept as bytes.

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

A direction-finding bearing.

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

An older beacon format that gives a grid locator instead of a position.

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

An older format with text before the position. It is deprecated, so reading
and sending it needs `policy=aprs.APRS_IS(legacy_positions=True)`.

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

Plain beacon text that is not APRS.

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

Data in a named external format the library does not decode, kept as bytes.

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

When a field cannot be decoded at all, the result is a `Malformed`. Its
`recovered` dictionary holds the fields that could be read, in the usual JSON
shape, and each diagnostic names the field that failed. Here the longitude is
out of range:

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

Fix the longitude, then build a `Packet` and send it:

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

Pass `malformed="raise"` or `unsupported="raise"` to get an exception instead.
For lines read from APRS-IS or a TNC, ending in CRLF or LF, use
`parse_tnc2_line`.

## Checking before sending

Constructors reject values that can never be valid, such as a latitude of 91.
Other rules, such as length limits, are checked when a packet is sent:
`serialize_packet` raises `ConformanceError` listing every problem, and
`check_packet` returns the same list without raising.

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

- Text fields such as messages, status and comments are Python `str`, sent as
  UTF-8. Callsigns and other protocol fields are ASCII.
- Binary data, such as `Opaque.information`, is `bytes`. `parse_packet` takes
  bytes, so encode a text line first, for example `line.encode()`.
- Optional fields are keyword-only: `Position(lat, lon, symbol, comment=...)`.
- Measurements carry their units, and the library converts them for the wire.
  `Measurement(None, "mph")` means a reading is unavailable; zero is a reading.
- A parsed packet keeps its received bytes (`original_wire`) and any
  `diagnostics`. Sending always encodes the model's current values.
- `to_json` and `from_json` work with strings, and `to_json_dict` and
  `from_json_dict` with dictionaries. Pass `expected_type=aprs.Packet` to check
  what is loaded.

## Full reference

- [JSON reference](https://github.com/afourney/hamkit/blob/main/packages/aprs/docs/JSON_FORMAT.md): every model, field, unit and named value.
- [Wire support by family](https://github.com/afourney/hamkit/blob/main/packages/aprs/docs/API_COVERAGE.md): what each family supports, with the finer encoding details.
- [Packet policies](https://github.com/afourney/hamkit/blob/main/packages/aprs/docs/ENVELOPE_POLICIES.md): limits, extensions and defaults.
- [Naming guide](https://github.com/afourney/hamkit/blob/main/packages/aprs/docs/NAMING.md): how public names are chosen.
- [Unresolved specification questions](https://github.com/afourney/hamkit/blob/main/packages/aprs/docs/UNRESOLVED_SPEC.md): where the specification is unclear.
- [Compliance vectors](https://github.com/afourney/hamkit/blob/main/packages/aprs/docs/APRS_COMPLIANCE_VECTORS.md): specification references and test packets.

Run the examples and unit tests with
`python -m pytest packages/aprs/tests -q` from the repository root.
