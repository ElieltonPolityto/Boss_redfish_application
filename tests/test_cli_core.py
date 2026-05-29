import unittest
from pathlib import Path

from boss_redfish.acquiredp import parse_acquiredp
from boss_redfish.cli_core import (
    parse_polling_ms,
    reading_table_rows,
    select_variables_by_code,
    template_preview_rows,
    save_last_session,
    load_last_session,
)


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "acquiredp.xml"


class GuiCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = parse_acquiredp(FIXTURE.read_text(encoding="utf-8"))

    def test_select_variables_by_code_preserves_requested_order(self):
        device = self.catalog.get_device("9.007")

        selected = select_variables_by_code(
            self.catalog,
            device,
            ["TpAmbiente", "Def_Status", "Out_ConvFreq"],
        )

        self.assertEqual([variable.code for variable in selected], ["TpAmbiente", "Def_Status", "Out_ConvFreq"])

    def test_template_preview_rows_show_traceability(self):
        device = self.catalog.get_device("9.007")
        variables = select_variables_by_code(self.catalog, device, ["TpAmbiente"])

        rows = template_preview_rows(device, variables)

        self.assertEqual(rows[0]["name"], "Temp ambiente")
        self.assertEqual(rows[0]["variable_code"], "TpAmbiente")
        self.assertEqual(rows[0]["resource_id"], "Temp_ambiente_TpAmbiente")
        self.assertEqual(rows[0]["placeholder"], "{{'id':'9.007|TpAmbiente|VALUE'}}")

    def test_reading_table_rows_format_values(self):
        rows = reading_table_rows(
            {
                "Temp_ambiente_TpAmbiente": {
                    "Name": "Temp ambiente",
                    "Reading": 19.7,
                    "ReadingUnits": "Cel",
                }
            }
        )

        self.assertEqual(rows, [("Temp ambiente", "19.7 Cel")])

    def test_parse_polling_ms_accepts_integer_milliseconds(self):
        self.assertEqual(parse_polling_ms("500"), 500)
        self.assertEqual(parse_polling_ms(" 1000 "), 1000)

    def test_parse_polling_ms_rejects_invalid_values(self):
        for value in ("", "abc", "12.5", "249", "-500"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_polling_ms(value)


class SessionCacheTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import boss_redfish.cli_core
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_cache_file = boss_redfish.cli_core.SESSION_CACHE_FILE
        self.test_cache_file = Path(self.tmpdir.name) / "last_session.json"
        boss_redfish.cli_core.SESSION_CACHE_FILE = self.test_cache_file

    def tearDown(self):
        import boss_redfish.cli_core
        boss_redfish.cli_core.SESSION_CACHE_FILE = self.old_cache_file
        self.tmpdir.cleanup()

    def test_save_and_load_session_caching(self):
        # Assert no session initially
        self.assertIsNone(load_last_session())

        # Save session
        save_last_session(
            redfish_url="https://192.168.0.133",
            chassis_id="CPCO_7_Eco2Pack_L3_Master_Cam_Congelados",
            sensor_ids=["Temp_ambiente_TpAmbiente"],
        )

        # Load session and check contents
        session = load_last_session()
        self.assertIsNotNone(session)
        self.assertEqual(session["redfish_url"], "https://192.168.0.133")
        self.assertEqual(session["chassis_id"], "CPCO_7_Eco2Pack_L3_Master_Cam_Congelados")
        self.assertEqual(session["sensor_ids"], ["Temp_ambiente_TpAmbiente"])


if __name__ == "__main__":
    unittest.main()
