# hamkit.aprs

A standalone component of HamKit for future Automatic Packet Reporting System
(APRS) packet parsing and composition.

This package is scaffolding only. Parsing and composition are not implemented;
there are no packet models, format choices, or public packet APIs yet.

## Development

From the repository root, install the package locally:

```console
python -m pip install -e packages/aprs
```

The package can then be imported with `import hamkit.aprs`. It has no runtime
dependencies.

Run the package smoke checks from the repository root after installation:

```console
python -m unittest discover -s packages/aprs/tests -v
```

Like the other HamKit modules, this package uses Hatchling, the `src/hamkit`
namespace layout, and version metadata in `__about__.py`. With Hatch installed,
run `hatch build` and `hatch run types:check` from `packages/aprs` to build the
package and check types.

## License

`hamkit-aprs` is distributed under the terms of the [MIT](LICENSE) license.
