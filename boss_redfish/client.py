from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any


class RedfishError(RuntimeError):
    pass


def normalize_base_url(base_url: str) -> str:
    base_url = base_url.strip()
    if not base_url:
        raise ValueError("base_url is required")
    if "://" not in base_url:
        base_url = "https://" + base_url
    base_url = base_url.rstrip("/")
    for suffix in ("/redfish/v1", "/redfish"):
        if base_url.lower().endswith(suffix):
            base_url = base_url[: -len(suffix)]
            break
    return base_url.rstrip("/")


class RedfishClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        verify_tls: bool = False,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.timeout = timeout
        self.token: str | None = None

    def _ssl_context(self) -> ssl.SSLContext | None:
        if self.base_url.lower().startswith("https://") and not self.verify_tls:
            return ssl._create_unverified_context()
        return None

    def _url(self, path: str) -> str:
        return self.base_url + "/" + path.lstrip("/")

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> tuple[dict[str, Any], Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if auth:
            if not self.token:
                self.login()
            headers["X-Auth-Token"] = self.token or ""

        request = urllib.request.Request(
            self._url(path),
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=self._ssl_context(),
            ) as response:
                raw = response.read()
                parsed = json.loads(raw.decode("utf-8")) if raw else {}
                return parsed, response
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RedfishError(f"HTTP {exc.code} calling {path}: {message}") from exc
        except urllib.error.URLError as exc:
            raise RedfishError(f"Could not reach BOSS at {self.base_url}: {exc.reason}") from exc

    def login(self) -> str:
        payload = {"UserName": self.username, "Password": self.password}
        _parsed, response = self._request_json(
            "POST",
            "/redfish/v1/SessionService/Sessions",
            payload=payload,
            auth=False,
        )
        token = response.headers.get("X-Auth-Token")
        if not token:
            raise RedfishError("Login succeeded but BOSS did not return X-Auth-Token")
        self.token = token
        return token

    def get_json(self, path: str) -> dict[str, Any]:
        parsed, _response = self._request_json("GET", path)
        return parsed

    def read_sensors(self, chassis_id: str, sensor_ids: list[str] | None = None) -> dict[str, dict[str, Any]]:
        if sensor_ids is None:
            sensor_ids = ["AmbientTemp", "Defrost", "CompCap"]
        readings = {}
        for sensor_id in sensor_ids:
            path = f"/redfish/v1/Chassis/{chassis_id}/Sensors/{sensor_id}"
            readings[sensor_id] = self.get_json(path)
        return readings

    def read_sensor_collection(self, chassis_id: str) -> dict[str, dict[str, Any]]:
        collection = self.get_json(f"/redfish/v1/Chassis/{chassis_id}/Sensors")
        sensor_ids = [
            str(member.get("@odata.id", "")).rstrip("/").rsplit("/", 1)[-1]
            for member in collection.get("Members", [])
            if member.get("@odata.id")
        ]
        return self.read_sensors(chassis_id, sensor_ids)


def format_reading(value: Any, units: str) -> str:
    if isinstance(value, bool):
        return "Ativo" if value else "Inativo"
    if value is None:
        return "Sem valor"
    if units:
        return f"{value} {units}"
    return str(value)


def build_reading_summary(readings: dict[str, dict[str, Any]]) -> dict[str, str]:
    summary = {}
    for payload in readings.values():
        name = str(payload.get("Name") or payload.get("Id") or "Valor")
        value = payload.get("Reading")
        units = str(payload.get("ReadingUnits") or "")
        summary[name] = format_reading(value, units)
    return summary
