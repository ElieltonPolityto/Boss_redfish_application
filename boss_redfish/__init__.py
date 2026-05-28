"""Helpers for Carel BOSS Redfish template generation and reading."""

from .client import RedfishClient, RedfishError, build_reading_summary, format_reading, normalize_base_url
from .template import (
    DEFAULT_CHASSIS_ID,
    DEFAULT_DEVICE_CODE,
    DEFAULT_DISPLAY_NAME,
    DEFAULT_VARIABLES,
    SensorDefinition,
    create_template_archive,
    placeholder,
    sensor_resource,
)

__all__ = [
    "DEFAULT_CHASSIS_ID",
    "DEFAULT_DEVICE_CODE",
    "DEFAULT_DISPLAY_NAME",
    "DEFAULT_VARIABLES",
    "RedfishClient",
    "RedfishError",
    "SensorDefinition",
    "build_reading_summary",
    "create_template_archive",
    "format_reading",
    "normalize_base_url",
    "placeholder",
    "sensor_resource",
]
