# BOSS Redfish Wizard

Aplicacao Python para diagnosticar o Redfish do supervisorio CAREL BOSS, ler o `acquiredp`, escolher controladores e variaveis, gerar templates Redfish e ler valores publicados pela API.

## Estrutura

- `boss_redfish/`: pacote principal.
- `boss_redfish_wizard.py`: interface grafica desktop.
- `boss_redfish_cli.py`: CLI para diagnostico, geracao de templates e leitura.
- `ABRIR_REDFISH_WIZARD.bat`: launcher Windows da interface grafica.
- `tests/`: testes automatizados.
- `tests/fixtures/acquiredp.xml`: fixture sintetica usada nos testes.

Arquivos gerados, como templates `.zip`, ficam em `dist/` e nao devem ser versionados.

## Rodar No Windows

Abra a interface grafica com dois cliques em:

```text
ABRIR_REDFISH_WIZARD.bat
```

O launcher verifica se existe Python 3.10 ou superior com `tkinter`. Se nao encontrar, tenta instalar Python 3.12 via `winget` e depois abre a interface. O projeto nao usa dependencias externas de `pip`.

Se a empresa ja tiver um Python padronizado, voce pode apontar manualmente:

```powershell
$env:BOSS_REDFISH_PYTHON = "C:\Python312\python.exe"
.\ABRIR_REDFISH_WIZARD.bat
```

Ou pelo PowerShell:

```powershell
cd C:\caminho\para\redfish
.\ABRIR_REDFISH_WIZARD.bat
```

## Rodar No Linux

```bash
python3 boss_redfish_wizard.py
```

## CLI

Diagnosticar BOSS:

```powershell
python boss_redfish_cli.py diagnose --boss http://BOSS_IP/boss/
```

Gerar template a partir de um `acquiredp`:

```powershell
python boss_redfish_cli.py template-from-selection --acquiredp tests\fixtures\acquiredp.xml --device-code 9.007 --variable TpAmbiente --output dist\temperatura_endereco_7.zip
```

Ler um sensor publicado:

```powershell
python boss_redfish_cli.py read --boss https://BOSS_IP --user admin --insecure --chassis-id NOME_DO_CHASSIS --sensor ID_DO_SENSOR
```

## Fluxo Operacional

1. Informe a URL do BOSS.
2. Rode o diagnostico.
3. Carregue os controladores pelo `acquiredp`.
4. Escolha controlador e variaveis.
5. Gere o template `.zip`.
6. Importe o template no BOSS em `Data Transfer > Redfish Server`.
7. Clique em `Start` no Redfish apos importar.
8. Leia os valores pela aba de leitura.

## Validacao Local

```powershell
python -m unittest discover -s tests -p "test*.py" -v
```

## Observacoes

- A senha Redfish e a senha do usuario `admin` configurada em `Data Transfer > Redfish Server`.
- `401` em `/redfish/v1/Chassis` sem token e esperado.
- `WRONG_PLACEHOLDER` normalmente indica variavel nao historicizada/logada no BOSS.
- `Invalid value for property 'ReadingType'` indica template antigo com tipo invalido para variavel booleana; gere o template novamente.
