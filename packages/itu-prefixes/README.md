# ITU Prefixes

[![PyPI - Version](https://img.shields.io/pypi/v/itu-prefixes.svg)](https://pypi.org/project/itu-prefixes)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/itu-prefixes.svg)](https://pypi.org/project/itu-prefixes)

-----

```console
pip install itu-prefixes
```

A simple library to work with ITU call sign prefixes.

#### call\_sign\_to\_country
To determine which country likely issued a call sign, you can do:

```python
from hamkit import itu_prefixes

print(itu_prefixes.call_sign_to_country("KK7CMT"))
```

which will output:

```
ITU_Prefix(prefix='K', country_name='United States', country_code='US')
```

#### country\_to\_prefixes
Likewise, to determine which prefixes a country may use, you can do:

```python
from hamkit import itu_prefixes

print(itu_prefixes.country_to_prefixes("US"))
```

which will output:

```
[
    ITU_Prefix(prefix='AA', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='AB', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='AC', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='AD', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='AE', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='AF', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='AG', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='AH', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='AI', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='AJ', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='AK', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='AL', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='K', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='N', country_name='United States', country_code='US'),
    ITU_Prefix(prefix='W', country_name='United States', country_code='US')
]
```

#### prefix\_to\_countries
Likewise, to determine which countries might correspond to a given prefix, do:

```python
from hamkit import itu_prefixes

print(itu_prefixes.prefix_to_countries("HB"))
```

which will produce:

```
[
    ITU_Prefix(prefix='HB3Y', country_name='Liechtenstein', country_code='LI'),
    ITU_Prefix(prefix='HB0', country_name='Liechtenstein', country_code='LI'),
    ITU_Prefix(prefix='HBL', country_name='Liechtenstein', country_code='LI'),
    ITU_Prefix(prefix='HB', country_name='Switzerland', country_code='CH')
]
```


## License

`itu-prefixes` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
