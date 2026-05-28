from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass


GROUP_NAMES = ("Digitals", "Analogs", "Integers", "Alarms")


@dataclass(frozen=True)
class Variable:
    group: str
    label: str
    code: str
    kind: str


@dataclass(frozen=True)
class Device:
    code: str
    name: str
    type_name: str
    address: int | None
    raw_name: str


@dataclass(frozen=True)
class AcquiredpCatalog:
    devices: list[Device]
    types: dict[str, list[Variable]]

    def get_device(self, code: str) -> Device | None:
        for device in self.devices:
            if device.code == code:
                return device
        return None

    def variables_for_device(self, device: Device | None) -> list[Variable]:
        if device is None:
            return []
        return list(self.types.get(device.type_name, []))


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower()


def _device_code(raw_name: str) -> str:
    match = re.match(r"^(-?\d+\.\d+)", raw_name.strip())
    if match:
        return match.group(1)
    return raw_name.split(".", 1)[0].strip()


def _device_address(code: str) -> int | None:
    if "." not in code:
        return None
    tail = code.rsplit(".", 1)[1]
    try:
        return int(tail)
    except ValueError:
        return None


def _device_display_name(raw_name: str, code: str) -> str:
    prefix = code + "."
    if raw_name.startswith(prefix):
        return raw_name[len(prefix) :].strip()
    return raw_name.strip()


def _parse_variable(group: str, node: ET.Element) -> Variable:
    raw_name = node.attrib.get("name", "").strip()
    if "|" in raw_name:
        label, code = raw_name.split("|", 1)
        label = label.strip()
        code = code.strip()
    else:
        label = raw_name
        code = raw_name
    return Variable(
        group=group,
        label=label,
        code=code,
        kind=node.attrib.get("type", "").strip(),
    )


def parse_acquiredp(xml_text: str) -> AcquiredpCatalog:
    root = ET.fromstring(xml_text)
    types: dict[str, list[Variable]] = {}
    devices: list[Device] = []

    for type_node in root.findall("type"):
        type_name = type_node.attrib.get("name", "").strip()
        variables: list[Variable] = []
        for group_name in GROUP_NAMES:
            group_node = next(
                (node for node in type_node.findall("item") if node.attrib.get("name") == group_name),
                None,
            )
            if group_node is None:
                continue
            for variable_node in group_node.findall("item"):
                variables.append(_parse_variable(group_name, variable_node))
        types[type_name] = variables

    for item_node in root.findall("item"):
        raw_type = item_node.attrib.get("type", "")
        if not raw_type.startswith("#"):
            continue
        raw_name = item_node.attrib.get("name", "").strip()
        code = _device_code(raw_name)
        devices.append(
            Device(
                code=code,
                name=_device_display_name(raw_name, code),
                type_name=raw_type[1:].strip(),
                address=_device_address(code),
                raw_name=raw_name,
            )
        )

    return AcquiredpCatalog(devices=devices, types=types)


def _matches_query(fields: list[str], query: str) -> bool:
    tokens = [token for token in _plain(query).split() if token]
    if not tokens:
        return True
    haystack = " ".join(_plain(field) for field in fields)
    return all(token in haystack for token in tokens)


def _device_score(device: Device, query: str) -> int:
    score = 0
    plain_query = _plain(query)
    tokens = [token for token in plain_query.split() if token]
    if plain_query and plain_query == _plain(device.code):
        score += 100
    if device.address is not None and str(device.address) in tokens:
        score += 80
    if re.search(rf"\b{re.escape(str(device.address))}\b", _plain(device.name)) if device.address is not None else False:
        score += 40
    if plain_query and plain_query in _plain(device.name):
        score += 20
    return score


def filter_devices(devices: list[Device], query: str) -> list[Device]:
    result: list[Device] = []
    for device in devices:
        fields = [
            device.code,
            device.name,
            device.type_name,
            str(device.address or ""),
            f"endereco {device.address}" if device.address is not None else "",
        ]
        if _matches_query(fields, query):
            result.append(device)
    return sorted(result, key=lambda device: (-_device_score(device, query), device.code))


def filter_variables(variables: list[Variable], query: str) -> list[Variable]:
    result = []
    for variable in variables:
        fields = [variable.label, variable.code, variable.group, variable.kind]
        if _matches_query(fields, query):
            result.append(variable)
    return result
