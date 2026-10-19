# HamKit

[![PyPI - Version](https://img.shields.io/pypi/v/hamkit.svg)](https://pypi.org/project/hamkit)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/hamkit.svg)](https://pypi.org/project/hamkit)

---

The `hamkit` package installs ALL `HamKit` submodules, and provides a command-line interface to demonstrate HamKit functionality.

```console
pip install hamkit
```

At present, HamKit includes the following submodules:

| Package                                                              | Version                                                                  | Description                                                                                                             |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| [hamkit-itu](https://pypi.org/project/hamkit-itu/)                   | ![PyPI - Version](https://img.shields.io/pypi/v/hamkit-itu.svg)          | Tools for working with ITU call sign prefixes (e.g., to look up country of origin)                                      |
| [hamkit-uls](https://pypi.org/project/hamkit-uls/)                   | ![PyPI - Version](https://img.shields.io/pypi/v/hamkit-uls.svg)          | Tools for working with local copies of the FCC Universal Licensing System database, (e.g., to look up call signs, etc.) |
| [hamkit-repeaterbook](https://pypi.org/project/hamkit-repeaterbook/) | ![PyPI - Version](https://img.shields.io/pypi/v/hamkit-repeaterbook.svg) | Tools for working with data exported from RepeaterBook (e.g., to save a database of local repeaters, etc.)              |
| [hamkit-aprs](https://pypi.org/project/hamkit-aprs/)                 | ![PyPI - Version](https://img.shields.io/pypi/v/hamkit-aprs.svg)         | Tools for working with (encoding/decoding) APRS packets.                                                                |

## Command-line Interface

`hamkit` provides a command-line interface to demonstrate HamKit functionality. Invoke it as follows:

```console
Syntax:
python -m hamkit COMMAND [ARGS..]

Available commands, and their arguments:

    help                   show *this* help message

    itu [QUERY],           where QUERY is a call sign, prefix, or 2-letter
                           country code (e.g., itu_prefixes KK7CMT)

    uls [CALLSIGN],        where CALLSIGN is the callsign to look up

    repeateroook           return a list of nearby repeaters

    aprs decode [PACKET..] decode APRS packets in TNC2 format (e.g.,
                           "N0CALL>APRS:>Ready") to pretty-printed JSON.
                           With no PACKET, or "-", packets are read from
                           stdin, one per line. Use "-f FILE" to read them
                           from a file instead.

    aprs encode [JSON]     encode APRS packets from JSON (an object, an
                           array of objects, or one object per line) to
                           TNC2 format. With no JSON, or "-", it is read
                           from stdin. Use "-f FILE" to read it from a file.

    aprs message [-p PATH] SENDER RECIPIENT TEXT
                           encode an APRS message

    aprs position [-p PATH] SENDER LAT LON [COMMENT]
                           encode an APRS position report, where LAT and
                           LON are in decimal degrees (negative for south
                           and west)

                           For message and position, PATH is a comma-
                           separated digipeater path (default:
                           "WIDE1-1,WIDE2-1"). Use -p "" for no path.
```

For example:

```
user@HOST:~$ python -m hamkit itu_prefixes KK7CMT

SUBROUTINE: call_sign_to_country('KK7CMT'):
If KK7CM is a call sign, then it was likely issued by:

  ITU Prefix: K
  Country Name: United States
  Country Code: US
```

Or:

```
user@HOST:~$ python -m hamkit aprs decode 'KK7CMT>APRS,WIDE1-1,WIDE2-1::N0CALL   :Hello world'

SUBROUTINE: to_json_dict(parse_packet(b'KK7CMT>APRS,WIDE1-1,WIDE2-1::N0CALL   :Hello world')):
The packet decodes to:

{
  "type": "packet",
  "header": {
    "source": "KK7CMT",
    "destination": "APRS",
    "path": [
      {
        "address": "WIDE1-1"
      },
      {
        "address": "WIDE2-1"
      }
    ]
  },
  "payload": {
    "type": "message",
    "addressee": "N0CALL",
    "text": "Hello world"
  },
  "original_wire": "KK7CMT>APRS,WIDE1-1,WIDE2-1::N0CALL   :Hello world"
}
```

## License

`hamkit` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
