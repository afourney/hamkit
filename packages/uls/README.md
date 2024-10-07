# hamkit.uls

[![PyPI - Version](https://img.shields.io/pypi/v/hamkit-uls.svg)](https://pypi.org/project/hamkit-uls)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/hamkit-uls.svg)](https://pypi.org/project/hamkit-uls)

---

> [!NOTE]  
> `hamkit.uls` is a _small standalone component_ of [`hamkit`](https://pypi.org/project/hamkit/). You can use it by itself (see below) if queries against the FCC ULS database is all that you need. Alternatively, install the entire collection of HamKit modules with `pip install hamkit`.

> [!TIP]  
> Even if you do not use `ULS` instances directly (e.g, if you want to run your own database queries), `ULS.download()` is useful for downloading and parsing the data into sqlite.

### A simple library to work with a local copy of the FCC ULS database

```console
pip install hamkit-uls
```

#### Download the ULS data, and load it into a sqlite database

At present, the library is mainly only useful for downloading and parsing the FCC ULS database (from their weekly database dumps), loading it into a sqlite database, and retrieving information about call signs. Here is an example, showing these operations:

```python
import os
import logging
from hamkit.uls import ULS

logging.basicConfig(level=logging.DEBUG)

# Download the database, if not already present
db_file = "uls.db"
if not os.path.isfile(db_file):
    ULS.download("uls.db")

# Query information about a callsign
uls = ULS(db_file)
print(uls.call_sign_lookup("kk7cmt"))
```

which will output the following:

```
UlsRecord(service='AMAT', unique_id='12345678', uls_file_number='', call_sign='KK7CMT', entity_type='L', entity_name='Fourney, Adam', first_name='Adam', middle_initial='', last_name='Fourney', street_address='1234 Streetname ST', city='Cityname', state='WA', zip_code='12345', status_code='', status_date='', linked_call_sign='', operator_class='T', group_code='D', region_code='7')
```

In general, the operation is straightforward enough, but `ULS.download()` has numerous options, as per the following docstring:

```python
"""
Download the amateur and/or GMRS license data from the FCC, and load
it into a local sqlite database.

Parameters:
    db_filename:  The location of the sqlite database to create.
    overwrite:    If true, overwrite any existing file (Default: False)
    amat_uri:     The URI from where to download amateur radio license data.
                  Set to None to skip downloading amateur radio data.
                  (Default: ULS_AMAT_URI)
    gmrs_uri:     The URI from where to download GMRS license data.
                  Set to None to skip downloading GMRS data.
                  (Default: ULS_GMRS_URI)
"""
```

## License

`hamkit-uls` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
