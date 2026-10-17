# Envelope policies

`parse_packet`, `parse_tnc2_line`, `check_packet`, `validate_packet`,
`serialize_packet`, and `serialize_tnc2_line` accept `policy=`, defaulting to
`aprs.APRS_IS`. Policies are immutable data:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EnvelopePolicy:
    source_pattern: str
    destination_pattern: str
    path_address_pattern: str
    max_path_entries: int | None = None
    max_information_bytes: int | None = None
    max_tnc2_line_bytes: int | None = None
```

Each regular expression uses `fullmatch`. Path entries are checked individually,
without their trailing `*` repeated marker. `None` means no limit; zero means
zero entries or bytes. Invalid regular expressions, negative limits, and limits
that are not integers are rejected when constructing a policy.

| Constraint                      | `aprs.RF`                                                      | `aprs.APRS_IS`                                                                                         |
| ------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Source                          | 1–6 uppercase ASCII letters/digits, optional numeric SSID 0–15 | At least 3 ASCII letters/digits, optional 1–2 alphanumeric SSID characters, at most 9 characters total |
| Destination and path address    | Same format as RF source                                       | At least 1 ASCII letter/digit, optional 1–2 alphanumeric SSID characters, at most 9 characters total   |
| Path entries                    | 8                                                              | No separate limit                                                                                      |
| Information bytes               | 256                                                            | No separate limit                                                                                      |
| TNC2 line bytes, including CRLF | No separate limit                                              | 512                                                                                                    |

APRS-IS patterns permit mixed case, including `qAR` in paths. Patterns check
individual formats, not q-construct ordering or network routing rules. The
APRS-IS limits follow the [server address rules](https://www.aprs-is.net/ServerDesign.aspx)
and [connection specification](https://www.aprs-is.net/Connecting.aspx).

Information length counts every byte after the outer header's colon, including
third-party encapsulation. Line length includes the whole envelope plus a
canonical two-byte CRLF, even for unframed input or LF-terminated input.
These are byte limits, not character counts. Parsing measures received bytes;
validation and serialization measure newly encoded bytes, which can differ
after UTF-8 conversion or normalization.

The selected envelope policy applies only to the outer packet. Inner third-party
headers remain text within its information field; they are not subjected to the
outer transport's address patterns or limits. Basic TNC2 syntax and payload
conformance checks still apply throughout the packet tree.

```python
from dataclasses import replace
from hamkit import aprs

packet = aprs.parse_packet(b"N0CALL>APRS,WIDE1-1:>Ready", policy=aprs.RF)
assert isinstance(packet, aprs.Packet)
assert aprs.check_packet(packet, policy=aprs.RF) == ()
wire = aprs.serialize_packet(packet, policy=aprs.RF)

custom = replace(aprs.RF, max_path_entries=None, max_information_bytes=200)
```

Parsing preserves decoded fields and reports policy violations in diagnostics.
Serialization refuses current violations; clearing stored diagnostics does not
bypass validation. Policies are separate from packet models and their JSON
schema. For configuration JSON, use `dataclasses.asdict(policy)` with
`json.dumps`, and reconstruct with `aprs.EnvelopePolicy(**json.loads(text))`;
`None` becomes JSON `null`.

This replaces `EnvelopeProfile` and the `profile="rf"`/`profile="monitor"`
arguments. `policy=aprs.RF` replaces the RF profile. The new default `APRS_IS`
enforces address formats and the 512-byte line limit that `monitor` did not.
For explicit permissive envelope handling, use
`aprs.EnvelopePolicy(".*", ".*", ".*")`; basic syntax and payload checks still
apply. Payload-only APIs have no outer envelope and retain their existing
signatures.
