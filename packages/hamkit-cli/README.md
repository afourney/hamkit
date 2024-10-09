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

## Command-line Interface

`hamkit` provides a command-line interface to demonstrate HamKit functionality. Invoke it as follows:

```console
Syntax:
python -m hamkit COMMAND [ARGS..]

Available commands, and their arguments:

    help                   show *this* help message

    itu_prefixes [QUERY],  where QUERY is a call sign, prefix, or 2-letter
                           country code (e.g., itu_prefixes KK7CMT)
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

## License

`hamkit` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
