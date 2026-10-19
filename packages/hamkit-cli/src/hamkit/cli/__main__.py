# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT
import sys
import os
import requests
import json
import urllib
from hamkit import aprs, itu
from hamkit.uls import ULS
from hamkit.repeaterbook import RepeaterBook

# from hamkit.repeaterbook import RepeaterBook
from .__about__ import __version__

import logging

logging.basicConfig(level=logging.INFO)

APRS_DEFAULT_PATH = "WIDE1-1,WIDE2-1"


def main():
    # Right now, only one command is supported
    if len(sys.argv) < 2 or sys.argv[1].lower() not in [
        "itu",
        "uls",
        "repeaterbook",
        "aprs",
    ]:
        sys.stderr.write(
            f"""HAMKIT CLI (v{__version__}):
A command-line interface to the python hamkit modules.

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
"""
        )
        return

    if sys.argv[1].lower() == "itu":
        query = sys.argv[2]

        # Query callsigns
        if len(query) > 3:
            r = itu.call_sign_to_country(query)
            if r is not None:
                print(
                    f"SUBROUTINE: call_sign_to_country('{query}'):\nIf {query} is a call sign, then it was likely issued by:\n\n{_format_prefix_record(r)}"
                )

        # And prefixes
        if len(query) <= 4:
            prefixes = itu.prefix_to_countries(query)
            if len(prefixes) > 0:
                print(
                    f"SUBROUTINE: prefix_to_countries('{query.upper()}'):\nThe following countries issue call signs that start with '{query.upper()}':\n"
                )
                for r in prefixes:
                    print(_format_prefix_record(r))

        if len(query) == 2:
            prefixes = itu.country_to_prefixes(query)
            if len(prefixes) > 0:
                print(
                    f"SUBROUTINE: country_to_prefixes('{prefixes[0].country_code}'):\n{prefixes[0].country_name} issues call signs with the following prefixes:\n"
                )
                for r in prefixes:
                    print(_format_prefix_record(r))

    elif sys.argv[1].lower() == "uls":
        # Download the database, if not already present
        db_file = "uls.db"
        if not os.path.isfile(db_file):
            ULS.download("uls.db")
        uls = ULS(db_file)

        # Query information about a callsign
        callsign = sys.argv[2].strip().upper()
        print(
            f"SUBROUTINE: call_sign_lookup('{callsign}'):\nThe FCC Universal Licensing System lookup for '{callsign}' returned:\n"
        )
        print(_format_uls_record(uls.call_sign_lookup(callsign)))

    elif sys.argv[1].lower() == "repeaterbook":
        # We need the user's location
        geo = _ip_geolocate()
        if geo is None:
            sys.stderr.write("Unable to geolocate. Exiting.")
            sys.exit(1)

        # Download the database, if not already present
        db_file = "repeaterbook.db"
        if not os.path.isfile(db_file):
            if geo["country_code"] not in ["US", "CA"]:
                sys.stderr.write("RepeaterBook downloads work only for US and Canada")
                sys.exit(1)
            url = "https://www.repeaterbook.com/api/export.php?"
            params = {}
            if geo["country_code"] == "US":
                params["state"] = geo["region"]
            elif geo["country_code"] == "CA":
                params["country"] = geo["country"]
            RepeaterBook.download(
                "repeaterbook.db", sources=[url + urllib.parse.urlencode(params)]
            )
        rb = RepeaterBook(db_file)

        print(
            f"SUBROUTINE: find_nearest(lat={geo['latitude']}, lon={geo['longitude']}):\nThe nearest repeaters are:\n"
        )
        count = 0
        for r in rb.find_nearest(
            lat=geo["latitude"], lon=geo["longitude"], max_distance=30
        ):
            print(_format_repeater(r))
            count += 1
            if count == 10:
                break

    elif sys.argv[1].lower() == "aprs":
        _aprs(sys.argv[2:])


def _aprs(args):
    subcommand = args[0].lower() if len(args) > 0 else ""
    path = APRS_DEFAULT_PATH
    if subcommand in ["message", "position"] and len(args) > 2 and args[1] == "-p":
        path = args[2]
        args = args[:1] + args[3:]

    try:
        if subcommand == "decode":
            if len(args) > 1 and args[1] not in ["-", "-f"]:
                lines = [os.fsencode(a) for a in args[1:]]
            else:
                lines = _read_input(args[1:], binary=True).splitlines()
            packets = [aprs.parse_packet(line) for line in lines if line.strip()]
            records = [aprs.to_json_dict(p) for p in packets]
            if len(records) == 1:
                _subroutine(
                    f"to_json_dict(parse_packet({lines[0].strip()!r}))",
                    "The packet decodes to:",
                )
            print(json.dumps(records[0] if len(records) == 1 else records, indent=2))

        elif subcommand == "encode":
            if len(args) > 1 and args[1] not in ["-", "-f"]:
                text = " ".join(args[1:])
            else:
                text = _read_input(args[1:], binary=False)
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                # Fall back to JSON Lines (one object per line)
                data = [json.loads(line) for line in text.splitlines() if line.strip()]
            records = data if isinstance(data, list) else [data]
            if len(records) == 1:
                _subroutine(
                    f"serialize_packet(from_json_dict({records[0]!r}, expected_type=Packet))",
                    "The record encodes to:",
                )
            _write_packets(
                [aprs.from_json_dict(r, expected_type=aprs.Packet) for r in records]
            )

        elif subcommand == "message" and len(args) == 4:
            header = _aprs_header(args[1], path)
            addressee = args[2].upper()
            _subroutine(
                f"serialize_packet(Packet(Header.parse({header!r}), "
                f"Message({addressee!r}, {args[3]!r})))",
                "The message encodes to:",
            )
            _write_packets(
                [aprs.Packet(aprs.Header.parse(header), aprs.Message(addressee, args[3]))]
            )

        elif subcommand == "position" and len(args) in [4, 5]:
            header = _aprs_header(args[1], path)
            lat, lon = float(args[2]), float(args[3])
            comment = args[4] if len(args) == 5 else ""
            _subroutine(
                f"serialize_packet(Packet(Header.parse({header!r}), "
                f"Position({lat!r}, {lon!r}, Symbol('/', '-'), comment={comment!r})))",
                "The position report encodes to:",
            )
            position = aprs.Position(lat, lon, aprs.Symbol("/", "-"), comment=comment)
            _write_packets([aprs.Packet(aprs.Header.parse(header), position)])

        else:
            sys.stderr.write(
                "Usage: python -m hamkit aprs (decode|encode|message|position) [ARGS..]\n"
                "Run 'python -m hamkit help' for details.\n"
            )
            sys.exit(1)
    except (aprs.APRSError, aprs.JSONModelError, ValueError, OSError) as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)


def _aprs_header(sender, path):
    # Returns TNC2 header text, e.g., "N0CALL>APRS,WIDE1-1,WIDE2-1"
    route = ",".join(["APRS"] + [h for h in path.upper().split(",") if h])
    return f"{sender.upper()}>{route}"


def _subroutine(call, description):
    # Written to stderr so that stdout stays pipeable
    sys.stderr.write(f"SUBROUTINE: {call}:\n{description}\n\n")
    sys.stderr.flush()


def _read_input(args, binary):
    # Read from a file ("-f FILE"), or else from stdin
    mode = "rb" if binary else "rt"
    if len(args) == 2 and args[0] == "-f":
        with open(args[1], mode) as fh:
            return fh.read()
    elif args in [[], ["-"]]:
        return sys.stdin.buffer.read() if binary else sys.stdin.read()
    raise ValueError("expected '-f FILE', '-', or no arguments")


def _write_packets(packets):
    for packet in packets:
        sys.stdout.buffer.write(aprs.serialize_packet(packet) + b"\n")
    sys.stdout.flush()


def _ip_geolocate():
    perm = input(
        "This method requires your geolocation. Would you like to proceed by estimating your location via your external IP address? [yes|no]: "
    )
    if perm.lower() not in ["yes", "y"]:
        return None

    response = requests.get("https://ipwho.is/")
    response.raise_for_status()
    return json.loads(response.text)


def _format_prefix_record(r):
    return f"""  ITU Prefix: {r.prefix}
  Country Name: {r.country_name}
  Country Code: {r.country_code}
"""


def _format_repeater(r):
    repeater = r._asdict()
    result = ""
    for k in repeater:
        if repeater[k] in [0, ""]:
            continue
        result += "  " + k.replace("_", " ") + ": " + str(repeater[k]) + "\n"
    return result


def _format_uls_record(r):
    if r is None:
        return "  None\n"
    else:
        return f"""  Call Sign: {r.call_sign}
  Name: {r.first_name}{(" " + r.middle_initial).strip()} {r.last_name}
  Address: 

    {r.street_address}
    {r.city}
    {r.state}, {r.zip_code}
"""


if __name__ == "__main__":
    main()
