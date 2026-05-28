from __future__ import annotations

from typing import Any

from .acquiredp import AcquiredpCatalog, Device, Variable
from .client import build_reading_summary
from .template import build_sensor_definitions


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
