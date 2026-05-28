from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .discovery import BossUrls


@dataclass(frozen=True)
class ImportResult:
    ok: bool
    automated: bool
    message: str


BrowserRunner = Callable[[BossUrls, str, str, Path], ImportResult]


def manual_import_steps(template_zip: Path) -> str:
    template_display = Path(template_zip).as_posix()
    return (
        "Importacao manual\n"
        "1. Abra o BOSS no navegador.\n"
        "2. Acesse Data Transfer > Redfish Server.\n"
        f"3. Em Upload template, selecione: {template_display}\n"
        "4. Confirme a importacao.\n"
        "5. Se o servico parar apos importar, clique em Start.\n"
    )


def assisted_import_template(
    *,
    urls: BossUrls,
    web_user: str,
    web_password: str,
    template_zip: Path,
    browser_runner: BrowserRunner | None = None,
) -> ImportResult:
    if browser_runner is None:
        return ImportResult(
            ok=False,
            automated=False,
            message=manual_import_steps(template_zip),
        )

    try:
        result = browser_runner(urls, web_user, web_password, template_zip)
    except Exception as exc:  # noqa: BLE001 - surface browser automation failure as safe fallback
        return ImportResult(
            ok=False,
            automated=False,
            message=f"Automacao do navegador falhou: {exc}\n\n{manual_import_steps(template_zip)}",
        )
    if not result.ok:
        return ImportResult(
            ok=False,
            automated=result.automated,
            message=result.message + "\n\n" + manual_import_steps(template_zip),
        )
    return result
