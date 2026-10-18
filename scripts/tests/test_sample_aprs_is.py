# SPDX-FileCopyrightText: 2026-present Adam Fourney <adam.fourney@gmail.com>
# SPDX-License-Identifier: MIT
"""Offline integration tests; never contact a public APRS-IS server."""

import contextlib
import hashlib
import io
import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from scripts import sample_aprs_is as sample


@contextlib.contextmanager
def server(handler):
    failures = []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(2)

        def serve():
            try:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(2)
                    handler(connection)
            except Exception as error:  # noqa: BLE001 -- re-raised in the test thread
                failures.append(error)

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        try:
            yield listener.getsockname()[1]
        finally:
            worker.join(timeout=3)
            if worker.is_alive():
                raise AssertionError("test server did not stop")
            if failures:
                raise failures[0]


def handshake(connection):
    connection.sendall(b"# test APRS-IS server\r\n")
    login = bytearray()
    while not login.endswith(b"\n"):
        chunk = connection.recv(1)
        if not chunk:
            raise AssertionError("client closed before login")
        login.extend(chunk)
    expected = (
        b"user N0CALL-CS pass -1 vers hamkit-sampler 0.1 filter a/51/-130/41/-116\r\n"
    )
    if login != expected:
        raise AssertionError(repr(login))
    return login


class SamplerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "capture"

    def args(self, port, *extra):
        return sample.parser().parse_args(
            [
                "--callsign",
                "n0call-cs",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--output",
                str(self.output),
                "--count",
                "2",
                "--seconds",
                "1",
                "--timeout",
                "0.5",
                *extra,
            ]
        )

    def test_fragmented_lines_preserve_bytes_and_send_only_login(self):
        packets = [
            b"N0CALL>S32UVT:`(_f\x1e\x1eOj/>Ready\xff\r\n",
            b"not a decodable packet\n",
        ]
        sent_after_login = []

        def handle(connection):
            handshake(connection)
            stream = (
                b"# logresp N0CALL-CS unverified, server TEST\r\n# heartbeat\r\n\r\n"
                + b"".join(packets)
            )
            for start in range(0, len(stream), 3):
                connection.sendall(stream[start : start + 3])
            sent_after_login.append(connection.recv(4096))

        with server(handle) as port:
            result = sample.capture(self.args(port))
        self.assertEqual(sent_after_login, [b""])
        self.assertEqual(result["stop_reason"], "packet_limit")
        self.assertEqual(result["packet_count"], 2)
        self.assertEqual(result["packet_bytes"], sum(map(len, packets)))
        self.assertEqual((self.output / "packets.tnc2").read_bytes(), b"".join(packets))
        self.assertEqual(
            result["sha256"], hashlib.sha256(b"".join(packets)).hexdigest()
        )
        self.assertEqual(
            json.loads((self.output / "metadata.json").read_text()), result
        )
        self.assertEqual(result["server_line_count"], 3)

    def test_duration_stops_an_idle_feed(self):
        def handle(connection):
            handshake(connection)
            connection.sendall(
                b"# logresp N0CALL-CS unverified, server TEST\r\nN0CALL>APRS:>Ready\r\n"
            )
            self.assertEqual(connection.recv(1), b"")

        before = time.monotonic()
        with server(handle) as port:
            result = sample.capture(self.args(port, "--seconds", "0.05"))
        self.assertEqual(result["stop_reason"], "duration_limit")
        self.assertEqual(result["packet_count"], 1)
        self.assertLess(time.monotonic() - before, 2)

    def test_login_timeout_does_not_count_prelogin_comments(self):
        def handle(connection):
            handshake(connection)
            connection.sendall(b"# still waiting\r\n")
            self.assertEqual(connection.recv(1), b"")

        with server(handle) as port:
            result = sample.capture(self.args(port, "--timeout", "0.05"))
        self.assertEqual(result["stop_reason"], "error")
        self.assertEqual(result["packet_count"], 0)
        self.assertIn("deadline", result["error"])

    def test_disconnect_keeps_complete_packets_without_inventing_a_partial_line(self):
        complete = b"N0CALL>APRS:>Ready\r\n"

        def handle(connection):
            handshake(connection)
            connection.sendall(
                b"# logresp N0CALL-CS unverified, server TEST\r\n"
                + complete
                + b"partial"
            )

        with server(handle) as port:
            result = sample.capture(self.args(port))
        self.assertEqual(result["stop_reason"], "error")
        self.assertEqual(result["buffered_bytes_not_captured"], 7)
        self.assertEqual((self.output / "packets.tnc2").read_bytes(), complete)

    def test_wrong_login_is_not_a_successful_capture(self):
        def handle(connection):
            handshake(connection)
            connection.sendall(b"# logresp OTHER unverified, server TEST\r\n")

        with server(handle) as port:
            result = sample.capture(self.args(port))
        self.assertEqual(result["stop_reason"], "error")
        self.assertIn("login", result["error"])
        self.assertEqual(result["packet_count"], 0)

    def test_count_limit_does_not_include_buffered_extra_packets(self):
        def handle(connection):
            handshake(connection)
            connection.sendall(
                b"# logresp N0CALL-CS unverified, server TEST\r\n"
                + b"N0CALL>APRS:>Ready\r\n" * 3
            )

        with server(handle) as port:
            result = sample.capture(self.args(port))
        self.assertEqual(result["packet_count"], 2)
        self.assertEqual(
            len((self.output / "packets.tnc2").read_bytes().splitlines()), 2
        )

    def test_overlong_server_line_is_rejected(self):
        class Connection:
            def settimeout(self, timeout):
                pass

            def recv(self, count):
                return b"x" * count

        reader = sample.Lines(Connection())
        with self.assertRaisesRegex(ValueError, "64 KiB"):
            reader.read(time.monotonic() + 1)

    def test_nonconforming_long_packet_is_preserved(self):
        line = b"N0CALL>APRS:>" + b"x" * 1024 + b"\r\n"

        def handle(connection):
            handshake(connection)
            connection.sendall(
                b"# logresp N0CALL-CS unverified, server TEST\r\n" + line
            )

        with server(handle) as port:
            result = sample.capture(self.args(port, "--count", "1"))
        self.assertEqual(result["stop_reason"], "packet_limit")
        self.assertEqual((self.output / "packets.tnc2").read_bytes(), line)

    def test_interrupt_preserves_completed_capture_and_metadata(self):
        line = b"N0CALL>APRS:>Ready\r\n"

        def handle(connection):
            handshake(connection)
            connection.sendall(
                b"# logresp N0CALL-CS unverified, server TEST\r\n" + line
            )
            self.assertEqual(connection.recv(1), b"")

        original = sample.Lines.read
        reads = 0

        def interrupted(reader, deadline):
            nonlocal reads
            reads += 1
            if reads == 4:
                raise KeyboardInterrupt
            return original(reader, deadline)

        with server(handle) as port, mock.patch.object(
            sample.Lines, "read", interrupted
        ):
            result = sample.capture(self.args(port))
        self.assertEqual(result["stop_reason"], "interrupted")
        self.assertEqual((self.output / "packets.tnc2").read_bytes(), line)
        self.assertEqual(
            json.loads((self.output / "metadata.json").read_text()), result
        )

    def test_existing_capture_is_never_overwritten(self):
        self.output.mkdir()
        original = self.output / "packets.tnc2"
        original.write_bytes(b"previous capture")
        with self.assertRaises(FileExistsError):
            sample.capture(self.args(1))
        self.assertEqual(original.read_bytes(), b"previous capture")

    def test_invalid_options_and_command_injection_are_rejected(self):
        for options in (
            ["--callsign", "N0CALL-0"],
            ["--callsign", "N0CALL\n"],
            ["--filter", "r/1/2/3\nINJECT"],
            ["--seconds", "nan"],
            ["--count", "0"],
            ["--timeout", "-1"],
        ):
            with self.subTest(options=options), contextlib.redirect_stderr(
                io.StringIO()
            ), self.assertRaises(SystemExit):
                self.args(14580, *options)

    def test_dry_run_has_no_files_or_connection(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = sample.main(
                ["--callsign", "N0CALL-CS", "--output", str(self.output), "--dry-run"]
            )
        self.assertEqual(status, 0)
        self.assertFalse(self.output.exists())
        planned = json.loads(stdout.getvalue())
        self.assertEqual(planned["host"], "noam.aprs2.net")
        self.assertIn(" pass -1 ", planned["login"])


if __name__ == "__main__":
    unittest.main()
