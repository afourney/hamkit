# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT
import sys
import os
from hamkit import itu
from hamkit.uls import ULS

# from hamkit.repeaterbook import RepeaterBook
from .__about__ import __version__

import logging

logging.basicConfig(level=logging.INFO)


def main():
    # Right now, only one command is supported
    if len(sys.argv) < 3 or sys.argv[1].lower() not in ["itu", "uls"]:
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


def _format_prefix_record(r):
    return f"""  ITU Prefix: {r.prefix}
  Country Name: {r.country_name}
  Country Code: {r.country_code}
"""


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


main()
