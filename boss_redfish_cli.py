#!/usr/bin/env python3
"""Command line interface for the Carel BOSS Redfish Wizard."""

from __future__ import annotations

import argparse
from datetime import datetime
import getpass
import json
import sys
import time
from pathlib import Path
from typing import Any

from boss_redfish import (
    DEFAULT_CHASSIS_ID,
    DEFAULT_DEVICE_CODE,
    DEFAULT_DISPLAY_NAME,
    RedfishClient,
    RedfishError,
    build_reading_summary,
    create_template_archive,
)
from boss_redfish.acquiredp import filter_variables, parse_acquiredp
from boss_redfish.gui_core import parse_polling_ms
from boss_redfish.template import create_generic_template_archive
from boss_redfish.wizard import run_diagnose, run_wizard


DEFAULT_FIXTURE = Path("tests") / "fixtures" / "acquiredp.xml"


def print_summary(summary: dict[str, str]) -> None:
    width = max([len(name) for name in summary] + [8])
    for name, value in summary.items():
        print(f"{name:<{width}} : {value}")


def read_redfish_values(
    client: RedfishClient,
    chassis_id: str,
    sensor_ids: list[str],
) -> dict[str, dict[str, Any]]:
    if sensor_ids:
        return client.read_sensors(chassis_id, sensor_ids)
    return client.read_sensor_collection(chassis_id)


def timestamp_ms() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def print_polling_result(readings: dict[str, dict[str, Any]], elapsed_ms: int, *, json_output: bool) -> None:
    timestamp = timestamp_ms()
    if json_output:
        print(
            json.dumps(
                {
                    "timestamp": timestamp,
                    "elapsed_ms": elapsed_ms,
                    "readings": readings,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return

    for name, value in build_reading_summary(readings).items():
        print(f"{timestamp} | {name} | {value} | {elapsed_ms} ms | OK", flush=True)


def command_template(args: argparse.Namespace) -> int:
    output = create_template_archive(
        output_zip=Path(args.output),
        chassis_id=args.chassis_id,
        device_code=args.device_code,
        display_name=args.display_name,
    )
    print(output)
    return 0


def command_template_from_selection(args: argparse.Namespace) -> int:
    xml_path = Path(args.acquiredp)
    xml_text = xml_path.read_text(encoding="utf-8")
    catalog = parse_acquiredp(xml_text)
    device = catalog.get_device(args.device_code)
    if device is None:
        raise ValueError(f"device not found: {args.device_code}")

    all_variables = catalog.variables_for_device(device)
    selected = []
    for code in args.variable:
        matches = [variable for variable in all_variables if variable.code == code]
        if not matches:
            raise ValueError(f"variable not found for {device.code}: {code}")
        selected.append(matches[0])
    if not selected and args.filter:
        selected = filter_variables(all_variables, args.filter)
    if not selected:
        raise ValueError("select at least one --variable or --filter")

    output = create_generic_template_archive(
        output_zip=Path(args.output),
        device=device,
        variables=selected,
        chassis_id=args.chassis_id or None,
    )
    print(output)
    return 0


def command_read(args: argparse.Namespace) -> int:
    polling_ms = parse_polling_ms(args.polling_ms) if args.watch else 0
    if args.count < 0:
        raise ValueError("--count must be zero or greater")

    password = args.password or getpass.getpass("Senha Redfish: ")
    client = RedfishClient(
        base_url=args.boss,
        username=args.user,
        password=password,
        verify_tls=not args.insecure,
        timeout=args.timeout,
    )

    if args.watch:
        if not args.json:
            print(f"Polling Redfish every {polling_ms} ms. Press Ctrl+C to stop.", flush=True)
        cycles = 0
        try:
            while True:
                started = time.monotonic()
                readings = read_redfish_values(client, args.chassis_id, args.sensor)
                elapsed_s = time.monotonic() - started
                elapsed_ms = max(0, round(elapsed_s * 1000))
                print_polling_result(readings, elapsed_ms, json_output=args.json)

                cycles += 1
                if args.count and cycles >= args.count:
                    break

                sleep_s = max(0.0, (polling_ms / 1000.0) - elapsed_s)
                if sleep_s:
                    time.sleep(sleep_s)
        except KeyboardInterrupt:
            if not args.json:
                print("Polling stopped.", flush=True)
        return 0

    readings = read_redfish_values(client, args.chassis_id, args.sensor)
    if args.json:
        print(json.dumps(readings, indent=2, ensure_ascii=False))
    else:
        print_summary(build_reading_summary(readings))
    return 0


def command_diagnose(args: argparse.Namespace) -> int:
    return run_diagnose(args.boss)


def command_wizard(args: argparse.Namespace) -> int:
    return run_wizard(args.boss, web_user=args.web_user)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Carel BOSS Redfish helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    diagnose = subparsers.add_parser("diagnose", help="diagnose BOSS web, acquiredp and Redfish")
    diagnose.add_argument("--boss", required=True, help="BOSS URL or IP, for example http://BOSS_IP/boss/")
    diagnose.set_defaults(func=command_diagnose)

    wizard = subparsers.add_parser("wizard", help="guided terminal controller and variable selection")
    wizard.add_argument("--boss", required=True, help="BOSS URL or IP, for example http://BOSS_IP/boss/")
    wizard.add_argument("--web-user", default="", help="BOSS web username, used for display/future assisted import")
    wizard.set_defaults(func=command_wizard)

    template = subparsers.add_parser("template", help="generate the default Eco2Pack Redfish template zip")
    template.add_argument("--output", default="dist/eco2pack-redfish-template.zip")
    template.add_argument("--device-code", default=DEFAULT_DEVICE_CODE)
    template.add_argument("--chassis-id", default=DEFAULT_CHASSIS_ID)
    template.add_argument("--display-name", default=DEFAULT_DISPLAY_NAME)
    template.set_defaults(func=command_template)

    generic = subparsers.add_parser("template-from-selection", help="generate a template from acquiredp selections")
    generic.add_argument("--acquiredp", default=str(DEFAULT_FIXTURE), help="path to acquiredp XML")
    generic.add_argument("--device-code", required=True)
    generic.add_argument("--variable", action="append", default=[])
    generic.add_argument("--filter", default="")
    generic.add_argument("--output", default="dist/redfish-selection-template.zip")
    generic.add_argument("--chassis-id", default="")
    generic.set_defaults(func=command_template_from_selection)

    read = subparsers.add_parser("read", help="read Redfish sensor values")
    read.add_argument("--boss", required=True, help="Redfish base URL or IP, for example https://BOSS_IP")
    read.add_argument("--user", default="admin")
    read.add_argument("--password", default="")
    read.add_argument("--chassis-id", default=DEFAULT_CHASSIS_ID)
    read.add_argument("--sensor", action="append", default=[], help="specific sensor id to read; can be repeated")
    read.add_argument("--timeout", type=float, default=15.0)
    read.add_argument("--insecure", action="store_true", help="disable TLS certificate verification")
    read.add_argument("--json", action="store_true", help="print full Redfish JSON")
    read.add_argument("--watch", action="store_true", help="repeat readings until Ctrl+C or --count is reached")
    read.add_argument("--polling-ms", default="1000", help="polling interval in milliseconds; minimum 250")
    read.add_argument("--count", type=int, default=0, help="number of polling cycles; 0 means forever")
    read.set_defaults(func=command_read)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (RedfishError, ValueError, OSError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
