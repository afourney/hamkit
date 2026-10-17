# HamKit

A collection of useful submodules for HAM Radio. At present, HamKit includes the following submodules:

| Package                                                              | Version                                                                  | Description                                                                                                             |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| [hamkit](https://pypi.org/project/hamkit/)                           | ![PyPI - Version](https://img.shields.io/pypi/v/hamkit.svg)              | A wrapper that installs all HamKit submodules and includes a command-line interface.                                    |
| [hamkit-itu](https://pypi.org/project/hamkit-itu/)                   | ![PyPI - Version](https://img.shields.io/pypi/v/hamkit-itu.svg)          | Tools for working with ITU call sign prefixes (e.g., to look up country of origin)                                      |
| [hamkit-uls](https://pypi.org/project/hamkit-uls/)                   | ![PyPI - Version](https://img.shields.io/pypi/v/hamkit-uls.svg)          | Tools for working with local copies of the FCC Universal Licensing System database, (e.g., to look up call signs, etc.) |
| [hamkit-repeaterbook](https://pypi.org/project/hamkit-repeaterbook/) | ![PyPI - Version](https://img.shields.io/pypi/v/hamkit-repeaterbook.svg) | Tools for working with data exported from RepeaterBook (e.g., to save a database of local repeaters, etc.)              |

## In development

- [hamkit-aprs](packages/aprs/README.md): typed APRS parsing, validation and
  composition foundation, with byte-preserving handling of unsupported payloads.
  The [packet cookbook](packages/aprs/README.md#find-an-example) shows Python
  and JSON construction for every modeled family, with wire output where a
  codec exists; the [coverage matrix](packages/aprs/docs/API_COVERAGE.md)
  distinguishes models from implemented codecs.

## License

`hamkit` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
