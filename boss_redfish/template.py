from __future__ import annotations

import json
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .acquiredp import Device, Variable


DEFAULT_DEVICE_CODE = "9.006"
DEFAULT_CHASSIS_ID = "Eco2Pack_L2"
DEFAULT_DISPLAY_NAME = "Eco2Pack L2 - Master - Congelados Carnes"


@dataclass(frozen=True)
class SensorDefinition:
    resource_id: str
    name: str
    variable_code: str
    reading_type: str
    units: str
    placeholder: str = ""
    group: str = ""
    kind: str = ""


DEFAULT_VARIABLES = [
    SensorDefinition(
        resource_id="AmbientTemp",
        name="Temperatura ambiente",
        variable_code="TpAmbiente",
        reading_type="Temperature",
        units="Cel",
    ),
    SensorDefinition(
        resource_id="Defrost",
        name="Degelo",
        variable_code="Def_Status",
        reading_type="",
        units="",
    ),
    SensorDefinition(
        resource_id="CompCap",
        name="Comp Cap",
        variable_code="Out_ConvFreq",
        reading_type="Percent",
        units="%",
    ),
]


def placeholder(device_code: str, variable_code: str, field: str = "VALUE") -> str:
    if not device_code or not device_code.strip():
        raise ValueError("device_code is required")
    if not variable_code or not variable_code.strip():
        raise ValueError("variable_code is required")
    if not field or not field.strip():
        raise ValueError("field is required")
    return "{{'id':'" + device_code.strip() + "|" + variable_code.strip() + "|" + field.strip() + "'}}"


def _ascii(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _collapse_identifier(text: str) -> str:
    text = _ascii(text)
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = "Item"
    if text[0].isdigit():
        text = "I_" + text
    return text


def safe_odata_id(label: str, code: str) -> str:
    return _collapse_identifier(f"{label}_{code}")


def unique_id(base: str, used: set[str]) -> str:
    candidate = base
    counter = 2
    while candidate in used:
        candidate = f"{base}_{counter}"
        counter += 1
    used.add(candidate)
    return candidate


def chassis_id_for_device(device: Device) -> str:
    return _collapse_identifier(device.name)


def reading_type_for(variable: Variable) -> str:
    label = f"{variable.label} {variable.code}".lower()
    if variable.kind == "boolean":
        return ""
    if "temp" in label:
        return "Temperature"
    if "press" in label or "pr " in label or "pressao" in label:
        return "Pressure"
    if "cap" in label or "pct" in label or "%" in label:
        return "Percent"
    return ""


def units_for(variable: Variable) -> str:
    label = f"{variable.label} {variable.code}".lower()
    if variable.kind == "boolean":
        return ""
    if "temp" in label:
        return "Cel"
    if "pct" in label or "%" in label or "cap" in label:
        return "%"
    return ""


def build_sensor_definitions(device_code: str, variables: Iterable[Variable]) -> list[SensorDefinition]:
    sensors: list[SensorDefinition] = []
    used: set[str] = set()
    for variable in variables:
        resource_id = unique_id(safe_odata_id(variable.label, variable.code), used)
        sensors.append(
            SensorDefinition(
                resource_id=resource_id,
                name=variable.label,
                variable_code=variable.code,
                reading_type=reading_type_for(variable),
                units=units_for(variable),
                placeholder=placeholder(device_code, variable.code),
                group=variable.group,
                kind=variable.kind,
            )
        )
    return sensors


def sensor_resource(
    *,
    chassis_id: str,
    device_code: str,
    variable: SensorDefinition,
) -> dict[str, Any]:
    reading = variable.placeholder or placeholder(device_code, variable.variable_code)
    payload = {
        "@odata.id": f"/redfish/v1/Chassis/{chassis_id}/Sensors/{variable.resource_id}",
        "@odata.type": "#Sensor.v1_10_1.Sensor",
        "Id": variable.resource_id,
        "Name": variable.name,
        "Reading": reading,
    }
    if variable.reading_type:
        payload["ReadingType"] = variable.reading_type
    if variable.units:
        payload["ReadingUnits"] = variable.units
    return payload


def sensors_collection(chassis_id: str, sensors: list[SensorDefinition]) -> dict[str, Any]:
    return {
        "@odata.id": f"/redfish/v1/Chassis/{chassis_id}/Sensors",
        "@odata.type": "#SensorCollection.SensorCollection",
        "Name": "BOSS Controller Sensors",
        "Members@odata.count": len(sensors),
        "Members": [
            {"@odata.id": f"/redfish/v1/Chassis/{chassis_id}/Sensors/{sensor.resource_id}"}
            for sensor in sensors
        ],
    }


def chassis_resource(chassis_id: str, display_name: str, model: str = "") -> dict[str, Any]:
    payload = {
        "@odata.id": f"/redfish/v1/Chassis/{chassis_id}",
        "@odata.type": "#Chassis.v1_25_2.Chassis",
        "Id": chassis_id,
        "Name": display_name,
        "ChassisType": "Module",
        "Manufacturer": "CAREL INDUSTRIES S.p.A.",
        "Sensors": {"@odata.id": f"/redfish/v1/Chassis/{chassis_id}/Sensors"},
    }
    if model:
        payload["Model"] = model
    return payload


def chassis_collection(chassis_id: str) -> dict[str, Any]:
    return {
        "@odata.id": "/redfish/v1/Chassis",
        "@odata.type": "#ChassisCollection.ChassisCollection",
        "Name": "Chassis Collection",
        "Members@odata.count": 1,
        "Members": [{"@odata.id": f"/redfish/v1/Chassis/{chassis_id}"}],
    }


def _zip_json(zf: zipfile.ZipFile, name: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
    zf.writestr(name, body)


def create_archive_from_sensors(
    *,
    output_zip: Path,
    chassis_id: str,
    display_name: str,
    device_code: str,
    sensors: list[SensorDefinition],
    model: str = "",
) -> Path:
    if not sensors:
        raise ValueError("at least one sensor must be selected")

    output_zip = Path(output_zip)
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _zip_json(zf, "Chassis/index.json", chassis_collection(chassis_id))
        _zip_json(zf, f"Chassis/{chassis_id}/index.json", chassis_resource(chassis_id, display_name, model))
        _zip_json(zf, f"Chassis/{chassis_id}/Sensors/index.json", sensors_collection(chassis_id, sensors))
        for sensor in sensors:
            _zip_json(
                zf,
                f"Chassis/{chassis_id}/Sensors/{sensor.resource_id}/index.json",
                sensor_resource(chassis_id=chassis_id, device_code=device_code, variable=sensor),
            )

    return output_zip


def create_generic_template_archive(
    *,
    output_zip: Path,
    device: Device,
    variables: list[Variable],
    chassis_id: str | None = None,
) -> Path:
    sensors = build_sensor_definitions(device.code, variables)
    resolved_chassis_id = chassis_id or chassis_id_for_device(device)
    return create_archive_from_sensors(
        output_zip=output_zip,
        chassis_id=resolved_chassis_id,
        display_name=device.name,
        device_code=device.code,
        sensors=sensors,
        model=device.type_name,
    )


def create_template_archive(
    *,
    output_zip: Path,
    chassis_id: str = DEFAULT_CHASSIS_ID,
    device_code: str = DEFAULT_DEVICE_CODE,
    display_name: str = DEFAULT_DISPLAY_NAME,
) -> Path:
    return create_archive_from_sensors(
        output_zip=output_zip,
        chassis_id=chassis_id,
        display_name=display_name,
        device_code=device_code,
        sensors=list(DEFAULT_VARIABLES),
        model="Eco2Pack",
    )
