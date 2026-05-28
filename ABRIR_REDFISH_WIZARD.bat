@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "APP_ENTRY=%~dp0boss_redfish_cli.py"
set "PYTHON_CMD="

echo.
echo BOSS Redfish CLI
echo ================
echo.

call :find_python
if not defined PYTHON_CMD (
  echo Python was not found.
  call :install_python
  if errorlevel 1 goto :fatal
  call :find_python
)

if not defined PYTHON_CMD (
  echo.
  echo [ERROR] A valid Python installation could not be found after installation.
  echo Install Python 3.12 or newer manually from https://www.python.org/downloads/windows/
  echo Select "Add python.exe to PATH" during installation.
  goto :fatal
)

%PYTHON_CMD% -c "import boss_redfish_cli" >nul 2>nul
if errorlevel 1 (
  echo.
  echo [ERROR] Python was found, but the CLI application could not be loaded.
  echo Check that this folder is complete and that boss_redfish_cli.py exists.
  goto :fatal
)

echo [OK] Python and basic dependencies found.
echo [OK] Starting command line interface.
echo.

if "%BOSS_REDFISH_BOOTSTRAP_ONLY%"=="1" exit /b 0

:menu
echo Select an option:
echo   1 - Guided wizard
echo   2 - Diagnose BOSS / Redfish
echo   3 - Read sensor once or with polling
echo   4 - CLI help
echo   5 - Exit
echo.
choice /c 12345 /n /m "Option [1-5]: "
if errorlevel 5 exit /b 0
if errorlevel 4 goto :help
if errorlevel 3 goto :read_sensor
if errorlevel 2 goto :diagnose
if errorlevel 1 goto :wizard
goto :menu

:wizard
echo.
set "BOSS_URL="
set /p "BOSS_URL=BOSS URL/IP, example http://192.168.0.133/boss/: "
if "%BOSS_URL%"=="" goto :menu
set "WEB_USER="
set /p "WEB_USER=BOSS web user, optional: "
%PYTHON_CMD% "%APP_ENTRY%" wizard --boss "%BOSS_URL%" --web-user "%WEB_USER%"
echo.
pause
goto :menu

:diagnose
echo.
set "BOSS_URL="
set /p "BOSS_URL=BOSS URL/IP, example http://192.168.0.133/boss/: "
if "%BOSS_URL%"=="" goto :menu
%PYTHON_CMD% "%APP_ENTRY%" diagnose --boss "%BOSS_URL%"
echo.
pause
goto :menu

:read_sensor
echo.
set "REDFISH_URL="
set /p "REDFISH_URL=Redfish URL/IP, example https://192.168.0.133: "
if "%REDFISH_URL%"=="" goto :menu
set "REDFISH_USER="
set /p "REDFISH_USER=Redfish user [admin]: "
if "%REDFISH_USER%"=="" set "REDFISH_USER=admin"
set "CHASSIS_ID="
set /p "CHASSIS_ID=Chassis ID: "
if "%CHASSIS_ID%"=="" goto :menu
set "SENSOR_ID="
set /p "SENSOR_ID=Sensor ID: "
if "%SENSOR_ID%"=="" goto :menu
choice /c YN /n /m "Use polling? [Y/N]: "
if errorlevel 2 goto :read_once
set "POLLING_MS="
set /p "POLLING_MS=Polling time in ms [1000]: "
if "%POLLING_MS%"=="" set "POLLING_MS=1000"
%PYTHON_CMD% "%APP_ENTRY%" read --boss "%REDFISH_URL%" --user "%REDFISH_USER%" --chassis-id "%CHASSIS_ID%" --sensor "%SENSOR_ID%" --insecure --watch --polling-ms "%POLLING_MS%"
echo.
pause
goto :menu

:read_once
%PYTHON_CMD% "%APP_ENTRY%" read --boss "%REDFISH_URL%" --user "%REDFISH_USER%" --chassis-id "%CHASSIS_ID%" --sensor "%SENSOR_ID%" --insecure
echo.
pause
goto :menu

:help
echo.
%PYTHON_CMD% "%APP_ENTRY%" --help
echo.
pause
goto :menu

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
"%~1" -c "import sys, ssl, urllib.request, xml.etree.ElementTree; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0
set "PYTHON_CMD="%~1""
exit /b 0

:check_python_command
if defined PYTHON_CMD exit /b 0
%* -c "import sys, ssl, urllib.request, xml.etree.ElementTree; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0
set "PYTHON_CMD=%*"
exit /b 0

:install_python
where winget >nul 2>nul
if errorlevel 1 (
  echo.
  echo [ERROR] Automatic installation requires winget, but winget was not found.
  echo Install Python 3.12 or newer manually from https://www.python.org/downloads/windows/
  echo Select "Add python.exe to PATH" during installation.
  exit /b 1
)

echo.
echo Installing Python 3.12 through winget...
echo A Windows permission prompt may appear.
winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
  echo.
  echo [ERROR] Automatic Python installation failed.
  echo Install Python 3.12 or newer manually from https://www.python.org/downloads/windows/
  echo Select "Add python.exe to PATH" during installation.
  exit /b 1
)
exit /b 0

:fatal
echo.
echo BOSS Redfish CLI could not be started.
echo.
pause
exit /b 1
