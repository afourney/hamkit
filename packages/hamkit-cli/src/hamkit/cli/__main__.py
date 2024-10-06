# SPDX-FileCopyrightText: 2024-present Adam Fourney <adam.fourney@gmail.com>
#
# SPDX-License-Identifier: MIT
import sys
from hamkit import itu_prefixes
from .__about__ import __version__

def main():

    # Right now, only one command is supported
    if len(sys.argv) < 3 or sys.argv[1].lower() not in ["itu_prefixes"]:
        sys.stderr.write(f"""HAMKIT CLI (v{__version__}):
A command-line interface to the python hamkit modules.

Syntax: 
python -m hamkit COMMAND [ARGS..]

Available commands, and their arguments:

    help                   show *this* help message

    itu_prefixes [QUERY],  where QUERY is a call sign, prefix, or 2-letter
                           country code (e.g., itu_prefixes KK7CMT) 
""")
        return

    query = sys.argv[2]

    # Query callsigns
    if len(query) > 3:
        r = itu_prefixes.call_sign_to_country(query)
        if r is not None:
            print(f"SUBROUTINE: call_sign_to_country('{query}'):\nIf {query} is a call sign, then it was likely issued by:\n\n{_format_prefix_record(r)}")  

    # And prefixes
    if len(query) <= 4:
        prefixes = itu_prefixes.prefix_to_countries(query)
        if len(prefixes) > 0:
            print(f"SUBROUTINE: prefix_to_countries('{query.upper()}'):\nThe following countries issue call signs that start with '{query.upper()}':\n")
            for r in prefixes:
                print(_format_prefix_record(r))

    if len(query) == 2:
        prefixes = itu_prefixes.country_to_prefixes(query)
        if len (prefixes) > 0:
            print(f"SUBROUTINE: country_to_prefixes('{prefixes[0].country_code}'):\n{prefixes[0].country_name} issues call signs with the following prefixes:\n")
            for r in prefixes:
                print(_format_prefix_record(r))


def _format_prefix_record(r):
    return f"""  ITU Prefix: {r.prefix}
  Country Name: {r.country_name}
  Country Code: {r.country_code}
"""


main()
