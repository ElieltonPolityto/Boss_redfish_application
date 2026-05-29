import json
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from boss_redfish import (
    DEFAULT_VARIABLES,
    RedfishClient,
    build_reading_summary,
    create_template_archive,
    normalize_base_url,
    placeholder,
    sensor_resource,
)


class PlaceholderTests(unittest.TestCase):
    def test_placeholder_uses_boss_redfish_id_object_format(self):
        self.assertEqual(
            placeholder("9.006", "TpAmbiente"),
            "{{'id':'9.006|TpAmbiente|VALUE'}}",
        )

    def test_placeholder_rejects_empty_parts(self):
        with self.assertRaises(ValueError):
            placeholder("", "TpAmbiente")
        with self.assertRaises(ValueError):
            placeholder("9.006", "")


class TemplateTests(unittest.TestCase):
    def test_sensor_resource_maps_ambient_temperature(self):
        resource = sensor_resource(
            chassis_id="Eco2Pack_L2",
            device_code="9.006",
            variable=DEFAULT_VARIABLES[0],
        )

        self.assertEqual(
            resource["@odata.id"],
            "/redfish/v1/Chassis/Eco2Pack_L2/Sensors/AmbientTemp",
        )
        self.assertEqual(resource["Reading"], "{{'id':'9.006|TpAmbiente|VALUE'}}")
        self.assertEqual(resource["ReadingType"], "Temperature")

    def test_template_archive_contains_expected_redfish_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "template.zip"
            create_template_archive(
                output_zip=output,
                chassis_id="Eco2Pack_L2",
                device_code="9.006",
                display_name="Eco2Pack L2 - Master - Congelados Carnes",
            )

            with zipfile.ZipFile(output) as zf:
                names = set(zf.namelist())
                self.assertIn("Chassis/index.json", names)
                self.assertIn("Chassis/Eco2Pack_L2/index.json", names)
                self.assertIn("Chassis/Eco2Pack_L2/Sensors/index.json", names)
                self.assertIn(
                    "Chassis/Eco2Pack_L2/Sensors/AmbientTemp/index.json",
                    names,
                )
                self.assertIn("Chassis/Eco2Pack_L2/Sensors/Defrost/index.json", names)
                self.assertIn("Chassis/Eco2Pack_L2/Sensors/CompCap/index.json", names)

                ambient = json.loads(
                    zf.read("Chassis/Eco2Pack_L2/Sensors/AmbientTemp/index.json")
                )
                self.assertEqual(ambient["Reading"], "{{'id':'9.006|TpAmbiente|VALUE'}}")


class ClientHelpersTests(unittest.TestCase):
    def test_normalize_base_url_removes_trailing_slashes_and_redfish_suffix(self):
        self.assertEqual(
            normalize_base_url("https://192.0.2.10/redfish/"),
            "https://192.0.2.10",
        )
        self.assertEqual(
            normalize_base_url("https://192.0.2.10/"),
            "https://192.0.2.10",
        )
        # Test converting HTTP to HTTPS for remote URLs
        self.assertEqual(
            normalize_base_url("http://192.168.0.133/boss/"),
            "https://192.168.0.133",
        )
        # Test keeping HTTP for local URLs
        self.assertEqual(
            normalize_base_url("http://127.0.0.1:8080/boss/redfish"),
            "http://127.0.0.1:8080",
        )
        # Test stripping /boss/redfish/v1
        self.assertEqual(
            normalize_base_url("http://192.168.0.133/boss/redfish/v1"),
            "https://192.168.0.133",
        )

    def test_build_reading_summary_formats_boolean_defrost(self):
        readings = {
            "AmbientTemp": {"Name": "Temperatura ambiente", "Reading": 4.8, "ReadingUnits": "Cel"},
            "Defrost": {"Name": "Degelo", "Reading": True, "ReadingUnits": ""},
            "CompCap": {"Name": "Comp Cap", "Reading": 37.5, "ReadingUnits": "%"},
        }

        summary = build_reading_summary(readings)

        self.assertEqual(summary["Temperatura ambiente"], "4.8 Cel")
        self.assertEqual(summary["Degelo"], "Ativo")
        self.assertEqual(summary["Comp Cap"], "37.5 %")


class FakeRedfishHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

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
        payload = json.loads(self.rfile.read(length))
        if payload != {"UserName": "admin", "Password": "dummy-password"}:
            self._send_json(401, {"error": "bad credentials"})
            return
        self._send_json(
            201,
            {"Id": "session-1", "Name": "Session"},
            {"X-Auth-Token": "dummy-token", "Location": "/redfish/v1/SessionService/Sessions/1"},
        )

    def do_GET(self):
        if self.headers.get("X-Auth-Token") != "dummy-token":
            self._send_json(401, {"error": "missing token"})
            return
        payloads = {
            "/redfish/v1/Chassis/Eco2Pack_L2/Sensors/AmbientTemp": {
                "Name": "Temperatura ambiente",
                "Reading": 5.1,
                "ReadingUnits": "Cel",
            },
            "/redfish/v1/Chassis/Eco2Pack_L2/Sensors/Defrost": {
                "Name": "Degelo",
                "Reading": False,
                "ReadingUnits": "",
            },
            "/redfish/v1/Chassis/Eco2Pack_L2/Sensors/CompCap": {
                "Name": "Comp Cap",
                "Reading": 45,
                "ReadingUnits": "%",
            },
        }
        if self.path not in payloads:
            self._send_json(404, {"error": "not found"})
            return
        self._send_json(200, payloads[self.path])

    def log_message(self, *_args):
        return


class RedfishClientTests(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), FakeRedfishHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_client_logs_in_and_reads_three_eco2pack_sensors(self):
        client = RedfishClient(
            base_url=self.base_url,
            username="admin",
            password="dummy-password",
            verify_tls=True,
        )

        self.assertEqual(client.login(), "dummy-token")
        readings = client.read_sensors("Eco2Pack_L2")

        self.assertEqual(readings["AmbientTemp"]["Reading"], 5.1)
        self.assertEqual(readings["Defrost"]["Reading"], False)
        self.assertEqual(readings["CompCap"]["Reading"], 45)


if __name__ == "__main__":
    unittest.main()
