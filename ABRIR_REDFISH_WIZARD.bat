@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "APP_ENTRY=%~dp0boss_redfish_wizard.py"
set "PYTHON_CMD="

echo.
echo BOSS Redfish Wizard
echo ====================
echo.

call :find_python
if not defined PYTHON_CMD (
  echo Python com tkinter nao encontrado.
  call :install_python
  if errorlevel 1 goto :fatal
  call :find_python
)

if not defined PYTHON_CMD (
  echo.
  echo [ERRO] Nao foi possivel localizar um Python valido apos a instalacao.
  echo Instale manualmente Python 3.12 ou superior em https://www.python.org/downloads/windows/
  echo Marque a opcao "Add python.exe to PATH" durante a instalacao.
  goto :fatal
)

%PYTHON_CMD% -c "import boss_redfish.gui_app" >nul 2>nul
if errorlevel 1 (
  echo.
  echo [ERRO] Python foi encontrado, mas a aplicacao nao carregou corretamente.
  echo Confira se esta pasta esta completa e se o arquivo boss_redfish_wizard.py existe.
  goto :fatal
)

echo [OK] Python e dependencias basicas encontrados.
echo [OK] Iniciando interface grafica.
echo.

if "%BOSS_REDFISH_BOOTSTRAP_ONLY%"=="1" exit /b 0

%PYTHON_CMD% "%APP_ENTRY%"
if errorlevel 1 goto :fatal
exit /b 0

:find_python
set "PYTHON_CMD="
if defined BOSS_REDFISH_PYTHON call :check_python_path "%BOSS_REDFISH_PYTHON%"
call :check_python_path "%~dp0.venv\Scripts\python.exe"
call :check_python_path "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :check_python_path "%ProgramFiles%\Python312\python.exe"
call :check_python_path "%ProgramFiles(x86)%\Python312\python.exe"
call :check_python_command py -3
call :check_python_command python
call :check_python_command python3
exit /b 0

:check_python_path
if defined PYTHON_CMD exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys, tkinter, ssl, urllib.request, xml.etree.ElementTree; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0
set "PYTHON_CMD="%~1""
exit /b 0

:check_python_command
if defined PYTHON_CMD exit /b 0
%* -c "import sys, tkinter, ssl, urllib.request, xml.etree.ElementTree; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0
set "PYTHON_CMD=%*"
exit /b 0

:install_python
where winget >nul 2>nul
if errorlevel 1 (
  echo.
  echo [ERRO] O instalador automatico precisa do winget, mas ele nao foi encontrado.
  echo Instale manualmente Python 3.12 ou superior em https://www.python.org/downloads/windows/
  echo Marque a opcao "Add python.exe to PATH" durante a instalacao.
  exit /b 1
)

echo.
echo Instalando Python 3.12 via winget...
echo Pode aparecer uma tela de permissao do Windows.
winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
  echo.
  echo [ERRO] A instalacao automatica do Python falhou.
  echo Instale manualmente Python 3.12 ou superior em https://www.python.org/downloads/windows/
  echo Marque a opcao "Add python.exe to PATH" durante a instalacao.
  exit /b 1
)
exit /b 0

:fatal
echo.
echo Nao foi possivel iniciar o BOSS Redfish Wizard.
echo.
pause
exit /b 1
