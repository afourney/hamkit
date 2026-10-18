#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Capture a bounded, receive-only APRS-IS sample without decoding its bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import socket
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_HOST = "noam.aprs2.net"
PNW_FILTER = "a/51/-130/41/-116"
MAX_LINE_BYTES = 65536


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def positive_int(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def positive_seconds(value: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return result


def callsign(value: str) -> str:
    if not re.fullmatch(
        r"(?=.{1,9}\Z)[A-Za-z0-9]{3,9}(?:-(?!0\Z)[A-Za-z0-9]{1,2})?", value
    ):
        raise argparse.ArgumentTypeError(
            "use an APRS-IS login of 3–9 characters, with an optional SSID (not -0)"
        )
    return value.upper()


def filter_text(value: str) -> str:
    if not value or any(not 32 <= ord(c) <= 126 for c in value) or not value.strip():
        raise argparse.ArgumentTypeError(
            "filter must be nonempty printable ASCII on one line"
        )
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--callsign",
        required=True,
        type=callsign,
        help="your unique sampling login, e.g. N0CALL-CS",
    )
    result.add_argument("--host", default=DEFAULT_HOST)
    result.add_argument("--port", type=positive_int, default=14580)
    result.add_argument(
        "--filter",
        type=filter_text,
        default=PNW_FILTER,
        help=f"server filter expression (default: {PNW_FILTER})",
    )
    result.add_argument(
        "--count",
        type=positive_int,
        default=10000,
        help="maximum packet lines (default: 10000)",
    )
    result.add_argument(
        "--seconds",
        type=positive_seconds,
        default=300,
        help="capture duration after login, even if idle (default: 300)",
    )
    result.add_argument(
        "--timeout",
        type=positive_seconds,
        default=15,
        help="connection and individual handshake-stage timeout (default: 15)",
    )
    result.add_argument(
        "--output",
        type=Path,
        default=None,
        help="new output directory; existing directories are never overwritten",
    )
    result.add_argument(
        "--dry-run",
        action="store_true",
        help="print connection settings without connecting or writing files",
    )
    return result


def login_line(args: argparse.Namespace) -> bytes:
    line = f"user {args.callsign} pass -1 vers hamkit-sampler 0.1 filter {args.filter}\r\n".encode(
        "ascii"
    )
    if len(line) > 512:
        raise ValueError(
            "login including filter exceeds the APRS-IS 512-byte line limit"
        )
    return line


class Lines:
    """Read arbitrary TCP chunks into bounded lines, preserving every byte."""

    def __init__(self, connection: socket.socket):
        self.connection = connection
        self.pending = bytearray()

    def read(self, deadline: float) -> bytes:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("deadline reached")
            end = self.pending.find(b"\n")
            if end >= 0:
                if end + 1 > MAX_LINE_BYTES:
                    raise ValueError("server line exceeds 64 KiB")
                line = bytes(self.pending[: end + 1])
                del self.pending[: end + 1]
                return line
            if len(self.pending) >= MAX_LINE_BYTES:
                raise ValueError("unterminated server line exceeds 64 KiB")
            self.connection.settimeout(min(remaining, 1.0))
            try:
                chunk = self.connection.recv(4096)
            except TimeoutError:
                continue
            if not chunk:
                raise EOFError("server closed the connection")
            self.pending.extend(chunk)


def capture(args: argparse.Namespace) -> dict:
    login = login_line(args)
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    summary = {
        "started_utc": utc_now(),
        "host": args.host,
        "port": args.port,
        "callsign": args.callsign,
        "filter": args.filter,
        "receive_only": True,
        "max_packets": args.count,
        "max_seconds": args.seconds,
        "packet_count": 0,
        "packet_bytes": 0,
        "server_line_count": 0,
        "stop_reason": "error",
        "stage": "connection",
    }
    digest = hashlib.sha256()
    reader = None
    with (output / "packets.tnc2").open("xb") as packets, (output / "server.log").open(
        "xb"
    ) as server:

        def server_line(line: bytes) -> None:
            server.write(line)
            summary["server_line_count"] += 1

        try:
            with socket.create_connection(
                (args.host, args.port), timeout=args.timeout
            ) as connection:
                summary["peer"] = list(connection.getpeername())
                reader = Lines(connection)
                summary["stage"] = "greeting"
                greeting = reader.read(time.monotonic() + args.timeout)
                if not greeting.startswith(b"#"):
                    raise ValueError(
                        "expected an APRS-IS server greeting starting with #"
                    )
                server_line(greeting)
                connection.settimeout(args.timeout)
                summary["stage"] = "login"
                # This is the only write to the network: no packets are transmitted.
                connection.sendall(login)
                deadline = time.monotonic() + args.timeout
                while True:
                    line = reader.read(deadline)
                    if not line.startswith(b"#"):
                        raise ValueError(
                            "received packet data before login acknowledgment"
                        )
                    server_line(line)
                    if line.lower().startswith(b"# logresp"):
                        match = re.fullmatch(
                            rb"# logresp (\S+) (unverified|verified)(?:,.*)?\r?\n",
                            line,
                            re.IGNORECASE,
                        )
                        if not match or match[1].upper() != args.callsign.encode():
                            raise ValueError(
                                "server rejected or did not recognize the requested login"
                            )
                        summary["login_response"] = line.decode("latin1").rstrip("\r\n")
                        break
                summary["capture_started_utc"] = utc_now()
                summary["stage"] = "capture"
                deadline = time.monotonic() + args.seconds
                while summary["packet_count"] < args.count:
                    try:
                        line = reader.read(deadline)
                    except TimeoutError:
                        summary["stop_reason"] = "duration_limit"
                        break
                    if line.startswith(b"#"):
                        server_line(line)
                        continue
                    if line in (b"\r\n", b"\n"):
                        continue
                    packets.write(line)
                    digest.update(line)
                    summary["packet_count"] += 1
                    summary["packet_bytes"] += len(line)
                else:
                    summary["stop_reason"] = "packet_limit"
        except KeyboardInterrupt:
            summary["stop_reason"] = "interrupted"
        except (OSError, EOFError, ValueError) as error:
            summary["error"] = str(error)
        finally:
            summary["finished_utc"] = utc_now()
            summary["sha256"] = digest.hexdigest()
            summary["buffered_bytes_not_captured"] = (
                len(reader.pending) if reader else 0
            )
            packets.flush()
            server.flush()
            (output / "metadata.json").write_text(
                json.dumps(summary, indent=2) + "\n", encoding="utf-8"
            )
    return summary


def main(argv: list[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    if args.port > 65535:
        cli.error("port must be at most 65535")
    if args.output is None:
        args.output = Path("downloads/aprs-is") / datetime.now(UTC).strftime(
            "%Y%m%dT%H%M%S.%fZ"
        )
    try:
        login = login_line(args)
    except ValueError as error:
        cli.error(str(error))
    if args.dry_run:
        print(
            json.dumps(
                {
                    "host": args.host,
                    "port": args.port,
                    "login": login.decode().rstrip("\r\n"),
                    "output": str(args.output),
                    "max_packets": args.count,
                    "max_seconds": args.seconds,
                },
                indent=2,
            )
        )
        return 0
    try:
        summary = capture(args)
    except OSError as error:
        print(f"Cannot create capture: {error}", file=sys.stderr)
        return 1
    print(
        f"Saved {summary['packet_count']} packet lines to {args.output} ({summary['stop_reason']})."
    )
    if "error" in summary:
        print(summary["error"], file=sys.stderr)
        return 1
    if summary["stop_reason"] == "interrupted":
        return 130
    if summary["packet_count"] == 0:
        print(
            "No packet lines received; inspect server.log and the filter.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
