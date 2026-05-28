from __future__ import annotations

import getpass
from dataclasses import dataclass
from pathlib import Path

from .acquiredp import AcquiredpCatalog, Device, Variable, filter_devices, filter_variables, parse_acquiredp
from .client import RedfishClient, RedfishError, build_reading_summary
from .discovery import BossUrls, diagnose_boss, fetch_text, normalize_boss_urls
from .template import build_sensor_definitions, chassis_id_for_device, create_generic_template_archive
from .web_import import assisted_import_template, manual_import_steps


@dataclass(frozen=True)
class Selection:
    device: Device
    variables: list[Variable]
    chassis_id: str
    output_zip: Path


def print_banner(title: str) -> None:
    print()
    print("=" * 58)
    print(title)
    print("=" * 58)


def print_diagnostic(raw_boss: str) -> BossUrls:
    print_banner("Diagnostico BOSS / Redfish")
    report = diagnose_boss(raw_boss)
    for probe in report.probes:
        status = probe.status if probe.status is not None else "-"
        marker = "OK" if probe.ok else "ERRO"
        print(f"[{marker}] {probe.name:<30} {status:<4} {probe.url}")
        if probe.message:
            print(f"      {probe.message}")
    return report.urls


def load_catalog(urls: BossUrls) -> AcquiredpCatalog:
    _status, _content_type, xml_text = fetch_text(urls.acquiredp_url)
    return parse_acquiredp(xml_text)


def show_devices(devices: list[Device]) -> None:
    for idx, device in enumerate(devices, 1):
        print(f"[{idx}] {device.code:<7} {device.name}")
        print(f"    Tipo: {device.type_name}")


def choose_device(catalog: AcquiredpCatalog) -> Device:
    print_banner("Escolha do controlador")
    print(f"Foram encontrados {len(catalog.devices)} controladores.")
    while True:
        query = input("Filtro por codigo, endereco, tipo ou nome: ").strip()
        matches = filter_devices(catalog.devices, query)
        if not matches:
            print("Nenhum controlador encontrado com esse filtro.")
            continue
        show_devices(matches[:20])
        choice = input("Escolha o numero do controlador: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= min(len(matches), 20):
            return matches[int(choice) - 1]
        print("Opcao invalida.")


def show_variables(variables: list[Variable]) -> None:
    print("Num | Nome | Codigo BOSS | Grupo | Tipo")
    print("-" * 78)
    for idx, variable in enumerate(variables, 1):
        print(f"{idx:>3} | {variable.label} | {variable.code} | {variable.group} | {variable.kind}")


def choose_variables(catalog: AcquiredpCatalog, device: Device) -> list[Variable]:
    print_banner(f"Variaveis de {device.code} - {device.name}")
    all_variables = catalog.variables_for_device(device)
    print(f"Esse controlador tem {len(all_variables)} variaveis.")
    selected: list[Variable] = []
    while True:
        query = input("Filtro de variavel (ex: temp, degelo, comp, pressao): ").strip()
        matches = filter_variables(all_variables, query)
        if not matches:
            print("Nenhuma variavel encontrada com esse filtro.")
            continue
        visible = matches[:40]
        show_variables(visible)
        raw = input("Selecione numeros separados por virgula: ").strip()
        indexes = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= len(visible):
                indexes.append(int(part) - 1)
        for index in indexes:
            variable = visible[index]
            if variable not in selected:
                selected.append(variable)
        print(f"Selecionadas ate agora: {len(selected)}")
        more = input("Adicionar mais variaveis? [s/N]: ").strip().lower()
        if more != "s":
            break
    if not selected:
        raise ValueError("nenhuma variavel selecionada")
    return selected


def output_name_for(device: Device) -> Path:
    safe = chassis_id_for_device(device).lower()
    return Path("dist") / f"redfish_{device.code.replace('.', '_')}_{safe}.zip"


def preview_selection(selection: Selection) -> None:
    print_banner("Previa do template")
    print(f"Controlador: {selection.device.code} - {selection.device.name}")
    print(f"Chassis ID:  {selection.chassis_id}")
    print(f"Arquivo:     {selection.output_zip}")
    print()
    for sensor in build_sensor_definitions(selection.device.code, selection.variables):
        print(f"- {sensor.name}")
        print(f"  Codigo BOSS: {sensor.variable_code}")
        print(f"  ID Redfish:  {sensor.resource_id}")
        print(f"  Placeholder: {sensor.placeholder}")


def print_manual_import_instructions(output_zip: Path) -> None:
    print_banner("Importacao manual")
    print(manual_import_steps(output_zip))


def read_after_import(urls: BossUrls, selection: Selection) -> None:
    should_read = input("Deseja tentar ler as variaveis publicadas agora? [s/N]: ").strip().lower()
    if should_read != "s":
        return
    password = getpass.getpass("Senha Redfish do usuario admin: ")
    sensor_ids = [sensor.resource_id for sensor in build_sensor_definitions(selection.device.code, selection.variables)]
    client = RedfishClient(
        base_url=urls.redfish_base,
        username="admin",
        password=password,
        verify_tls=False,
    )
    try:
        readings = client.read_sensors(selection.chassis_id, sensor_ids)
    except RedfishError as exc:
        print(f"Erro ao ler Redfish: {exc}")
        return
    print_banner("Leitura Redfish")
    summary = build_reading_summary(readings)
    width = max([len(name) for name in summary] + [8])
    for name, value in summary.items():
        print(f"{name:<{width}} : {value}")


def run_wizard(raw_boss: str, *, web_user: str = "") -> int:
    urls = print_diagnostic(raw_boss)
    if web_user:
        print()
        print(f"Usuario web informado: {web_user}")
        print("A senha web sera pedida apenas se a importacao por navegador for implementada nesta maquina.")

    catalog = load_catalog(urls)
    device = choose_device(catalog)
    variables = choose_variables(catalog, device)
    selection = Selection(
        device=device,
        variables=variables,
        chassis_id=chassis_id_for_device(device),
        output_zip=output_name_for(device),
    )
    preview_selection(selection)

    confirm = input("Gerar esse template? [S/n]: ").strip().lower()
    if confirm == "n":
        print("Operacao cancelada.")
        return 1

    create_generic_template_archive(
        output_zip=selection.output_zip,
        device=selection.device,
        variables=selection.variables,
        chassis_id=selection.chassis_id,
    )
    print(f"Template gerado: {selection.output_zip}")

    import_now = input("Deseja importar automaticamente no BOSS? [s/N]: ").strip().lower()
    if import_now == "s":
        web_user = input("Usuario web do BOSS: ").strip()
        web_password = getpass.getpass("Senha web do BOSS: ")
        result = assisted_import_template(
            urls=urls,
            web_user=web_user,
            web_password=web_password,
            template_zip=selection.output_zip,
        )
        print(result.message)
    else:
        print_manual_import_instructions(selection.output_zip)

    read_after_import(urls, selection)
    return 0


def run_diagnose(raw_boss: str) -> int:
    print_diagnostic(raw_boss)
    return 0
