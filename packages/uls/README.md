# ITU Prefixes

[![PyPI - Version](https://img.shields.io/pypi/v/itu-prefixes.svg)](https://pypi.org/project/itu-prefixes)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/itu-prefixes.svg)](https://pypi.org/project/itu-prefixes)

---

> [!NOTE]  
> `hamkit.uls` is a _small standalone component_ of [`hamkit`](https://pypi.org/project/hamkit/). You can use it by itself (see below) if queries against the FCC ULS database is all that you need. Alternatively, install the entire collection of HamKit modules with `pip install hamkit`.

### A simple library to work with a local copy of the FCC ULS database

```console
pip install hamkit-uls
```

#### Download the ULS data, and load it into a sqlite database

At present, the library is mainly only useful for downloading and parsing the FCC ULS database (from their weekly database dumps, provided as part of their public access program). The following code will download the database, and load it into the `uls.db` sqlite local copy.

```python
from hamkit import uls

import logging
logging.basicConfig(level=logging.DEBUG)

uls.ULS.download()
```

## License

`itu-prefixes` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
