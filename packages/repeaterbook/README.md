# hamkit.repeaterbook

[![PyPI - Version](https://img.shields.io/pypi/v/hamkit-repeaterbook.svg)](https://pypi.org/project/hamkit-repeaterbook)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/hamkit-repeaterbook.svg)](https://pypi.org/project/hamkit-repeaterbook)

---

> [!NOTE]  
> `hamkit.repeaterbook` is a _small standalone component_ of [`hamkit`](https://pypi.org/project/hamkit/). You can use it by itself (see below) if queries against the RepeaterBook database is all that you need. Alternatively, install the entire collection of HamKit modules with `pip install hamkit`.

> [!TIP]  
> Even if you do not use `RepeaterBook` instances directly (e.g, if you want to run your own database queries), `RepeaterBook.download()` is useful for downloading and parsing the data into sqlite for local queries.

### A simple library to work with a local copy of the RepeaterBook US & Canada database

```console
pip install hamkit-repeaterbook
```

#### Download the RepeaterBook data, and load it into a sqlite database

```python
import os
import logging
from hamkit.repeaterbook import RepeaterBook

logging.basicConfig(level=logging.DEBUG)

sources = [
    "https://www.repeaterbook.com/api/export.php?state=Washington",
    "https://www.repeaterbook.com/api/export.php?state=Washington&stype=gmrs",
]

# Download the database, if not already present
db_file = "repeaterbook.db"
if not os.path.isfile(db_file):
    RepeaterBook.download("repeaterbook.db", sources),

# Query information about a callsign
rb = RepeaterBook(db_file)
for r in rb.find_nearest(lat=47.658009, lon=-122.103288):
    print(f"{r}\n")
```

which will output the following:

```
Repeater(callsign='KC7IYE', downlink_freq=145.31, downlink_tone='', uplink_freq=144.71, uplink_tone='103.5', nearest_city='Redmond', landmark='', county='King', state='Washington', state_id='53', country='United States', latitude=47.67399979, longitude=-122.12200165, precise=0, use='OPEN', operational_status='On-air', fm_analog=1, ares=0, races=0, skywarn=0, canwarn=0, allstar_node='0', echoLink_node='', irlp_node='0', wires_node='', dmr=0, dmr_color_code='', dmr_id='', dstar=0, nxdn=0, apco_p25=0, p25_nac='', m17=0, m17_can='', tetra=0, tetra_mcc='', tetra_mnc='', system_fusion=0, ysf_dg_id_uplink='', ysf_dg_is_downlink='', ysf_dsc='', notes='', last_update='2021-07-06', distance=2.2639443534336845)

Repeater(callsign='KC7IYE', downlink_freq=53.07, downlink_tone='179.9', uplink_freq=51.37, uplink_tone='100.0', nearest_city='Redmond', landmark='', county='King', state='Washington', state_id='53', country='United States', latitude=47.6925, longitude=-122.1114, precise=0, use='OPEN', operational_status='On-air', fm_analog=1, ares=0, races=0, skywarn=0, canwarn=0, allstar_node='0', echoLink_node='0', irlp_node='0', wires_node='', dmr=0, dmr_color_code='', dmr_id='', dstar=0, nxdn=0, apco_p25=0, p25_nac='', m17=0, m17_can='', tetra=0, tetra_mcc='', tetra_mnc='', system_fusion=0, ysf_dg_id_uplink='', ysf_dg_is_downlink='', ysf_dsc='', notes='', last_update='2023-03-17', distance=3.8830227407299263)

Repeater(callsign='N7QT', downlink_freq=442.325, downlink_tone='103.5', uplink_freq=447.325, uplink_tone='103.5', nearest_city='Redmond', landmark='', county='King', state='Washington', state_id='53', country='United States', latitude=47.67459, longitude=-122.05393, precise=0, use='OPEN', operational_status='Unknown', fm_analog=1, ares=0, races=0, skywarn=0, canwarn=0, allstar_node='0', echoLink_node='0', irlp_node='0', wires_node='', dmr=1, dmr_color_code='2', dmr_id='311757', dstar=0, nxdn=0, apco_p25=0, p25_nac='', m17=0, m17_can='', tetra=0, tetra_mcc='', tetra_mnc='', system_fusion=0, ysf_dg_id_uplink='', ysf_dg_is_downlink='', ysf_dsc='', notes='', last_update='2023-12-15', distance=4.130456951733273)

...
```

In general, the operation is straightforward enough, but `RepeaterBook.download()` has numerous options, as per the following docstring:

```python
"""
Download the RepeaterBook data and load it into a local sqlite database for querying.

Parameters:
    db_filename:  The location of the sqlite database to create.
    sources:      A list of URIs to download, or local file paths. Each URI or file
                  must resolve to a json file that uses the RepeaterBook format.
                  E.g.,
                    ["https://www.repeaterbook.com/api/export.php?state=Washington"]
                  Or
                    ["./cache/Washington.json"]

		  Repeated calls to repeaterbook.com are internally rate-limited to
		  one per minute.

                  CAUTION: each call to RepeaterBook will return a limited number
                           of records (at this time 3500). It is best to gather only
                           what you need, such as one state.
                           DO NOT MAKE FREQUENT CALLS, or you will be rate-limited or
                           blocked.

                  For details see: https://www.repeaterbook.com/wiki/doku.php?id=api

    overwrite:    If true, overwrite any existing file (Default: False)
"""
```

## License

`hamkit-repeaterbook` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
