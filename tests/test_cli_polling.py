import contextlib
import io
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from boss_redfish_cli import main


class PollingFakeRedfishHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    session_count = 0
    sensor_count = 0

    def _send_json(self, status, payload, headers=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/redfish/v1/SessionService/Sessions":
            self._send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        PollingFakeRedfishHandler.session_count += 1
        self._send_json(
            201,
            {"Id": "session-1"},
            {"X-Auth-Token": "polling-token"},
        )

    def do_GET(self):
        if self.headers.get("X-Auth-Token") != "polling-token":
            self._send_json(401, {"error": "missing token"})
            return
        if self.path != "/redfish/v1/Chassis/C1/Sensors/Temp_ambiente_TpAmbiente":
            self._send_json(404, {"error": "not found"})
            return
        PollingFakeRedfishHandler.sensor_count += 1
        self._send_json(
            200,
            {
                "Name": "Temp ambiente",
                "Reading": 19.7,
                "ReadingUnits": "Cel",
            },
        )

    def log_message(self, *_args):
        return


class CliPollingTests(unittest.TestCase):
    def setUp(self):
        PollingFakeRedfishHandler.session_count = 0
        PollingFakeRedfishHandler.sensor_count = 0
        self.server = HTTPServer(("127.0.0.1", 0), PollingFakeRedfishHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_read_watch_reuses_login_and_respects_count(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "read",
                    "--boss",
                    self.base_url,
                    "--user",
                    "admin",
                    "--password",
                    "dummy-password",
                    "--chassis-id",
                    "C1",
                    "--sensor",
                    "Temp_ambiente_TpAmbiente",
                    "--watch",
                    "--polling-ms",
                    "250",
                    "--count",
                    "2",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("Polling Redfish every 250 ms", stdout.getvalue())
        self.assertEqual(stdout.getvalue().count("Temp ambiente"), 2)
        self.assertEqual(PollingFakeRedfishHandler.session_count, 1)
        self.assertEqual(PollingFakeRedfishHandler.sensor_count, 2)

    def test_read_watch_json_outputs_json_lines(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "read",
                    "--boss",
                    self.base_url,
                    "--user",
                    "admin",
                    "--password",
                    "dummy-password",
                    "--chassis-id",
                    "C1",
                    "--sensor",
                    "Temp_ambiente_TpAmbiente",
                    "--watch",
                    "--polling-ms",
                    "250",
                    "--count",
                    "1",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 0)
        lines = stdout.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["readings"]["Temp_ambiente_TpAmbiente"]["Reading"], 19.7)
        self.assertIn("timestamp", payload)
        self.assertIn("elapsed_ms", payload)


if __name__ == "__main__":
    unittest.main()
