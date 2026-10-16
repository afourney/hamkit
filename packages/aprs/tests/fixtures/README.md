# Vector integration

`foundation.json` contains four specification-derived examples from
`docs/APRS_COMPLIANCE_VECTORS.md`, with explicit subsets of semantic assertions.
It is a focused smoke suite, not a compliance claim. No FAP implementation or
compatibility fixture has been copied into the implementation.

`tests/vector_adapter.py` loads either JSON fixtures or the document's JSON
blocks. Select a profile explicitly. Convert packet strings with Latin-1,
verify declared lengths/hex, and retain case IDs and source attribution.

Add packet fixtures here and field codec cases under `tests/fields`; packet
encoding, decoding, malformed inputs and round trips belong under
`tests/packets`. Encoding cases should specify structured inputs, expected wire
bytes, and separately the decoded quantized values. Never assert that an
arbitrary floating-point input survives wire quantization exactly.

Extend `semantic_fields` only for implemented semantics. Its unsupported model
error is intentional. Add explicit runners for error outcomes and stateful
sequences when those features exist. Do not mark unsupported formats as passing
`accept`, use blanket expected-failure tests, or combine FAP, historical,
strict-envelope and core expectations. Full document import is opt-in future
work; the current suite does not claim all 1,545 cases pass.
