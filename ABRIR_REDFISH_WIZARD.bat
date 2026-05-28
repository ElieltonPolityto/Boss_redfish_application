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
  echo Python with tkinter was not found.
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

%PYTHON_CMD% -c "import boss_redfish.gui_app" >nul 2>nul
if errorlevel 1 (
  echo.
  echo [ERROR] Python was found, but the application could not be loaded.
  echo Check that this folder is complete and that boss_redfish_wizard.py exists.
  goto :fatal
)

echo [OK] Python and basic dependencies found.
echo [OK] Starting graphical interface.
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
echo BOSS Redfish Wizard could not be started.
echo.
pause
exit /b 1
