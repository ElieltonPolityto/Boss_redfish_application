# BOSS Redfish Wizard

## English

Python application for CAREL BOSS supervisors. It diagnoses the BOSS Redfish service, reads the `acquiredp` XML, lets the user select controllers and variables, generates Redfish template ZIP files, and reads published values from the Redfish API.

### Project Structure

- `boss_redfish/`: main Python package.
- `boss_redfish_wizard.py`: desktop GUI launcher.
- `boss_redfish_cli.py`: command-line interface for diagnostics, template generation, and readings.
- `ABRIR_REDFISH_WIZARD.bat`: Windows launcher for the desktop GUI.
- `tests/`: automated tests.
- `tests/fixtures/acquiredp.xml`: synthetic fixture used by tests.

Generated files, such as Redfish template ZIPs, are written to `dist/` and should not be committed.

### Run On Windows

Open the desktop GUI by double-clicking:

```text
ABRIR_REDFISH_WIZARD.bat
```

The launcher checks for Python 3.10 or newer with `tkinter`. If Python is not found, it attempts to install Python 3.12 through `winget` and then starts the application. The project currently does not require external `pip` dependencies.

If your environment already has a standard Python installation, you can point the launcher to it:

```powershell
$env:BOSS_REDFISH_PYTHON = "C:\Python312\python.exe"
.\ABRIR_REDFISH_WIZARD.bat
```

Or run it from PowerShell:

```powershell
cd C:\path\to\redfish
.\ABRIR_REDFISH_WIZARD.bat
```

### Run On Linux

```bash
python3 boss_redfish_wizard.py
```

### CLI

Diagnose BOSS:

```powershell
python boss_redfish_cli.py diagnose --boss http://BOSS_IP/boss/
```

Generate a template from an `acquiredp` XML:

```powershell
python boss_redfish_cli.py template-from-selection --acquiredp tests\fixtures\acquiredp.xml --device-code 9.007 --variable TpAmbiente --output dist\temperature_address_7.zip
```

Read a published sensor:

```powershell
python boss_redfish_cli.py read --boss https://BOSS_IP --user admin --insecure --chassis-id CHASSIS_NAME --sensor SENSOR_ID
```

### Operator Flow

1. Enter the BOSS URL.
2. Run diagnostics.
3. Load controllers from `acquiredp`.
4. Select a controller and variables.
5. Generate the template `.zip`.
6. Import the template in BOSS at `Data Transfer > Redfish Server`.
7. Click `Start` in the Redfish page after importing.
8. Read values from the reading tab.

### Local Validation

```powershell
python -m unittest discover -s tests -p "test*.py" -v
```

### Notes

- The Redfish password is the password for the built-in `admin` user configured in `Data Transfer > Redfish Server`.
- A `401` response from `/redfish/v1/Chassis` without a token is expected.
- `WRONG_PLACEHOLDER` usually means the selected BOSS variable is not logged/historicized.
- `Invalid value for property 'ReadingType'` usually means an old template was generated with an invalid type for a boolean variable. Generate the template again with the current version.

---

## Portugues

Aplicacao Python para supervisores CAREL BOSS. Ela diagnostica o servico Redfish do BOSS, le o XML `acquiredp`, permite escolher controladores e variaveis, gera templates Redfish em `.zip` e le valores publicados pela API Redfish.

### Estrutura Do Projeto

- `boss_redfish/`: pacote Python principal.
- `boss_redfish_wizard.py`: inicializador da interface grafica desktop.
- `boss_redfish_cli.py`: interface de linha de comando para diagnostico, geracao de template e leitura.
- `ABRIR_REDFISH_WIZARD.bat`: launcher Windows da interface grafica.
- `tests/`: testes automatizados.
- `tests/fixtures/acquiredp.xml`: fixture sintetica usada pelos testes.

Arquivos gerados, como templates Redfish em `.zip`, ficam em `dist/` e nao devem ser versionados.

### Rodar No Windows

Abra a interface grafica com dois cliques em:

```text
ABRIR_REDFISH_WIZARD.bat
```

O launcher verifica se existe Python 3.10 ou superior com `tkinter`. Se o Python nao for encontrado, ele tenta instalar Python 3.12 via `winget` e depois inicia a aplicacao. Atualmente o projeto nao usa dependencias externas de `pip`.

Se a empresa ja tiver um Python padronizado, voce pode apontar o launcher para ele:

```powershell
$env:BOSS_REDFISH_PYTHON = "C:\Python312\python.exe"
.\ABRIR_REDFISH_WIZARD.bat
```

Ou execute pelo PowerShell:

```powershell
cd C:\caminho\para\redfish
.\ABRIR_REDFISH_WIZARD.bat
```

### Rodar No Linux

```bash
python3 boss_redfish_wizard.py
```

### CLI

Diagnosticar o BOSS:

```powershell
python boss_redfish_cli.py diagnose --boss http://BOSS_IP/boss/
```

Gerar template a partir de um XML `acquiredp`:

```powershell
python boss_redfish_cli.py template-from-selection --acquiredp tests\fixtures\acquiredp.xml --device-code 9.007 --variable TpAmbiente --output dist\temperatura_endereco_7.zip
```

Ler um sensor publicado:

```powershell
python boss_redfish_cli.py read --boss https://BOSS_IP --user admin --insecure --chassis-id NOME_DO_CHASSIS --sensor ID_DO_SENSOR
```

### Fluxo Operacional

1. Informe a URL do BOSS.
2. Rode o diagnostico.
3. Carregue os controladores pelo `acquiredp`.
4. Escolha o controlador e as variaveis.
5. Gere o template `.zip`.
6. Importe o template no BOSS em `Data Transfer > Redfish Server`.
7. Clique em `Start` na tela Redfish depois da importacao.
8. Leia os valores pela aba de leitura.

### Validacao Local

```powershell
python -m unittest discover -s tests -p "test*.py" -v
```

### Observacoes

- A senha Redfish e a senha do usuario interno `admin`, configurada em `Data Transfer > Redfish Server`.
- Uma resposta `401` em `/redfish/v1/Chassis` sem token e esperada.
- `WRONG_PLACEHOLDER` normalmente indica que a variavel selecionada nao esta logada/historicizada no BOSS.
- `Invalid value for property 'ReadingType'` normalmente indica um template antigo gerado com tipo invalido para variavel booleana. Gere o template novamente com a versao atual.
