from __future__ import annotations

from pathlib import Path
from typing import Any

from .acquiredp import AcquiredpCatalog, Device, Variable
from .client import build_reading_summary
from .template import build_sensor_definitions


MIN_POLLING_MS = 250
RECOMMENDED_POLLING_MS = 500
DEFAULT_POLLING_MS = 1000


def parse_polling_ms(value: str) -> int:
    text = str(value).strip()
    if not text:
        raise ValueError("Polling time must be an integer in ms.")
    try:
        polling_ms = int(text)
    except ValueError as exc:
        raise ValueError("Polling time must be an integer in ms.") from exc
    if polling_ms < MIN_POLLING_MS:
        raise ValueError(f"Polling time must be at least {MIN_POLLING_MS} ms.")
    return polling_ms


def polling_is_below_recommended(polling_ms: int) -> bool:
    return polling_ms < RECOMMENDED_POLLING_MS


def select_variables_by_code(
    catalog: AcquiredpCatalog,
    device: Device | None,
    variable_codes: list[str],
) -> list[Variable]:
    variables = catalog.variables_for_device(device)
    by_code = {variable.code: variable for variable in variables}
    return [by_code[code] for code in variable_codes if code in by_code]


def template_preview_rows(device: Device, variables: list[Variable]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for sensor in build_sensor_definitions(device.code, variables):
        rows.append(
            {
                "name": sensor.name,
                "variable_code": sensor.variable_code,
                "resource_id": sensor.resource_id,
                "placeholder": sensor.placeholder,
                "reading_type": sensor.reading_type,
                "units": sensor.units,
            }
        )
    return rows


def reading_table_rows(readings: dict[str, dict[str, Any]]) -> list[tuple[str, str]]:
    summary = build_reading_summary(readings)
    return list(summary.items())


SESSION_CACHE_FILE = Path("dist/last_session.json")


def save_last_session(*, redfish_url: str, chassis_id: str, sensor_ids: list[str]) -> None:
    try:
        from pathlib import Path
        import json
        SESSION_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "redfish_url": redfish_url,
            "chassis_id": chassis_id,
            "sensor_ids": sensor_ids,
        }
        with open(SESSION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def load_last_session() -> dict[str, Any] | None:
    try:
        import json
        if SESSION_CACHE_FILE.is_file():
            with open(SESSION_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None
