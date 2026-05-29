from __future__ import annotations

from pathlib import Path


def manual_import_steps(template_zip: Path) -> str:
    template_display = Path(template_zip).as_posix()
    return (
        "1. Abra o BOSS no navegador.\n"
        "2. Acesse Data Transfer > Redfish Server.\n"
        f"3. Em Upload template, selecione: {template_display}\n"
        "4. Confirme a importacao.\n"
        "5. Se o servico parar apos importar, clique em Start.\n"
    )
