import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from boss_redfish.acquiredp import filter_devices, filter_variables, parse_acquiredp
from boss_redfish.discovery import normalize_boss_urls
from boss_redfish.template import (
    build_sensor_definitions,
    create_generic_template_archive,
    safe_odata_id,
)


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "acquiredp.xml"


class AcquiredpParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = parse_acquiredp(FIXTURE.read_text(encoding="utf-8"))

    def test_sample_acquiredp_finds_expected_boss_devices(self):
        self.assertEqual(len(self.catalog.devices), 3)

        cpco2 = self.catalog.get_device("9.002")
        self.assertIsNotNone(cpco2)
        self.assertEqual(cpco2.code, "9.002")
        self.assertIn("Controller 2", cpco2.name)
        self.assertEqual(cpco2.type_name, "MB_ChillPack_v307")

    def test_sample_acquiredp_counts_controller_variables(self):
        cpco2 = self.catalog.get_device("9.002")
        variables = self.catalog.variables_for_device(cpco2)
        self.assertEqual(len(variables), 6)

    def test_filters_find_controller_and_variables(self):
        devices = filter_devices(self.catalog.devices, "controller 2")
        self.assertEqual(devices[0].code, "9.002")

        variables = filter_variables(self.catalog.variables_for_device(devices[0]), "temp")
        self.assertTrue(any(var.code == "TempRetorno" for var in variables))
        self.assertTrue(all(var.group in {"Digitals", "Analogs", "Integers", "Alarms"} for var in variables))


class GenericTemplateTests(unittest.TestCase):
    def test_safe_odata_id_removes_invalid_chars_and_keeps_traceability(self):
        safe_id = safe_odata_id("Pressao succao - Offset", "AI_PressaoSuccao.p_Offset")

        self.assertEqual(safe_id, "Pressao_succao_Offset_AI_PressaoSuccao_p_Offset")
        self.assertNotIn("-", safe_id)
        self.assertNotIn("/", safe_id)
        self.assertNotIn(" ", safe_id)
        self.assertNotIn(".", safe_id)

    def test_sensor_definitions_are_unique_when_labels_repeat(self):
        catalog = parse_acquiredp(
            """<?xml version="1.0" encoding="UTF-8"?>
<item name="Root" separator=".">
  <type name="T">
    <item name="Analogs">
      <item name="Ti | P206" type="number" />
      <item name="Ti | P114" type="number" />
    </item>
  </type>
  <item name="9.001.Device" type="#T" />
</item>
"""
        )
        variables = catalog.variables_for_device(catalog.get_device("9.001"))

        sensors = build_sensor_definitions("9.001", variables)

        self.assertEqual(len({sensor.resource_id for sensor in sensors}), 2)
        self.assertEqual(sensors[0].placeholder, "{{'id':'9.001|P206|VALUE'}}")
        self.assertEqual(sensors[1].placeholder, "{{'id':'9.001|P114|VALUE'}}")

    def test_generic_template_preserves_original_boss_codes(self):
        catalog = parse_acquiredp(FIXTURE.read_text(encoding="utf-8"))
        device = catalog.get_device("9.002")
        selected = [var for var in catalog.variables_for_device(device) if var.code in {"TempRetorno", "DriveComp_dados.Power_KW"}]

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "template.zip"
            create_generic_template_archive(output_zip=output, device=device, variables=selected)

            with zipfile.ZipFile(output) as zf:
                names = set(zf.namelist())
                self.assertIn("Chassis/Controller_2_Sample_Chiller/Sensors/index.json", names)
                sensor_files = [name for name in names if name.endswith("/index.json") and "/Sensors/" in name and not name.endswith("/Sensors/index.json")]
                self.assertEqual(len(sensor_files), 2)
                payloads = [json.loads(zf.read(name)) for name in sensor_files]
                readings = {payload["Name"]: payload["Reading"] for payload in payloads}
                self.assertEqual(readings["Temp retorno"], "{{'id':'9.002|TempRetorno|VALUE'}}")
                self.assertEqual(readings["Comp - Potencia"], "{{'id':'9.002|DriveComp_dados.Power_KW|VALUE'}}")

    def test_boolean_sensor_omits_invalid_reading_type(self):
        catalog = parse_acquiredp(FIXTURE.read_text(encoding="utf-8"))
        device = catalog.get_device("9.007")
        selected = [var for var in catalog.variables_for_device(device) if var.code == "Def_Status"]

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "template.zip"
            create_generic_template_archive(output_zip=output, device=device, variables=selected)

            with zipfile.ZipFile(output) as zf:
                payload = json.loads(
                    zf.read(
                        "Chassis/Controller_7_Sample_Eco_Pack/"
                        "Sensors/Degelo_Def_Status/index.json"
                    )
                )
                self.assertEqual(payload["Reading"], "{{'id':'9.007|Def_Status|VALUE'}}")
                self.assertNotIn("ReadingType", payload)
                self.assertNotIn("ReadingUnits", payload)


class DiscoveryHelpersTests(unittest.TestCase):
    def test_normalize_boss_urls_uses_http_for_web_and_https_for_redfish(self):
        urls = normalize_boss_urls("http://192.0.2.10/boss/")

        self.assertEqual(urls.web_base, "http://192.0.2.10/boss")
        self.assertEqual(urls.acquiredp_url, "http://192.0.2.10/boss/servlet/acquiredp")
        self.assertEqual(urls.redfish_base, "https://192.0.2.10")


if __name__ == "__main__":
    unittest.main()
