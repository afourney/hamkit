# APRS-IS sampling

`sample_aprs_is.py` records a bounded live APRS-IS stream for inspecting real
packet bytes. It uses Python 3.11+ and the standard library; installing hamkit
is unnecessary. It does not parse or rewrite packets, transmit APRS packets,
request historical data, or generate expected decoder output.

## Capture Pacific Northwest traffic

From the repository root, substitute your callsign and a distinct sampling SSID:

```sh
python scripts/sample_aprs_is.py --callsign N0CALL-CS --dry-run
python scripts/sample_aprs_is.py --callsign N0CALL-CS --output downloads/aprs-is/pnw-sample
```

The defaults connect to `noam.aprs2.net:14580`, log in with `pass -1`
(receive-only), and request `filter a/51/-130/41/-116`. This is a practical
Pacific Northwest bounding box: 41–51° N, 130–116° W, covering Washington,
Oregon, adjacent southern British Columbia and parts of neighboring states.
It is not a formal regional boundary. The server pool selects a North American
server; the **filter**, not the server's location, selects traffic.

Collection stops at **10,000 packet lines or five minutes**, whichever comes
first. The duration starts after login and is enforced even if the feed is idle.
Ctrl-C preserves completed lines and metadata. Use a unique login to avoid
colliding with another APRS client using your callsign/SSID.

```sh
# Seattle and surrounding area, within 150 km; up to 2,000 lines or two minutes.
python scripts/sample_aprs_is.py --callsign N0CALL-CS \
  --filter 'r/47.6062/-122.3321/150' --count 2000 --seconds 120
```

`--host`, `--port`, and `--timeout` can be changed; `--help` lists all options.
An existing output directory is never overwritten. Without `--output`, a new
UTC timestamped directory is created under `downloads/aprs-is/`, which is
already excluded by the repository's `.gitignore`.

## Output and limitations

- `packets.tnc2`: complete nonempty, non-comment lines, in arrival order, with
  their original bytes and line endings. Non-UTF-8 and malformed packets are
  preserved. No trimming, decoding, normalization, deduplication, or checksum
  repair occurs. Open this file in **binary mode** when using the codec.
- `server.log`: original `#` server greeting, login response and keepalive lines.
  An `unverified` login response is normal for receive-only access.
- `metadata.json`: requested server, actual peer address, login, filter, UTC
  start/end times, limits, counts, SHA-256 of `packets.tnc2`, and stop/error reason.
  Buffered bytes not included at the stopping point are counted separately.
  Incomplete final lines are not promoted into packet records.

A geographic feed is a sample, not an exhaustive corpus or a balanced sample of
packet types. Geographical filtering depends on server position knowledge;
positionless traffic may be absent, and associated messages can involve stations
outside the box. APRS-IS itself also filters/deduplicates traffic before this
script sees it. Do not assume every packet was received on RF or has a known
position inside the box. Live messages and station positions are retained; raw
captures are not automatically committed or published.

The script waits for the server greeting and matching login acknowledgment before
recording packets. It sends only the receive-only login/filter line. Connection
failure, early disconnect, or an overlong server line returns a nonzero exit code
and preserves any completed packet lines. A duration-limited empty capture also
returns nonzero. There is no automatic reconnection, so gaps are explicit. The
64 KiB line guard prevents unbounded buffering without discarding ordinary
nonconforming lines just because they exceed APRS-IS's normal 512-byte limit.

## Network access

The client needs outbound **TCP port 14580** to the selected APRS-IS server.
This is not an HTTP download; setting `HTTPS_PROXY` does not tunnel the socket.
In a restricted cloud environment, the appropriate TCP access/forwarding must
be configured first, or run the command locally. For an existing approved TCP
forward, use `--host` and `--port` to target its local endpoint. No APRS transmit
passcode is needed, and the script does not accept one.

## Verification

Run the offline integration tests from the repository root:

```sh
python -m unittest discover -s scripts/tests -v
```

The tests use only a local fake server. They cover the receive-only handshake,
fragmented TCP reads, binary preservation, packet/time bounds, disconnects,
invalid logins/options, line bounds, and prevention of output overwrites.

Authoritative references:

- [APRS-IS connections and receive-only login](https://www.aprs-is.net/Connecting.aspx)
- [APRS-IS public server pools](https://www.aprs-is.net/aprsservers.aspx)
- [Server-side range and area filters](https://www.aprs-is.net/javAPRSFilter.aspx)
