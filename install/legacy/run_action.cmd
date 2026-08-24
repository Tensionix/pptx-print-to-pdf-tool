@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
cd /d "%BASE_DIR%"

set "MAIN_FILE=%BASE_DIR%\system_core\main.py"

call :RESOLVE_PYTHON
if errorlevel 1 goto NO_PYTHON
if not exist "%MAIN_FILE%" goto NO_MAIN

"%PYTHON_CMD%" %PYTHON_ARGS% "%MAIN_FILE%" %*
exit /b %ERRORLEVEL%

:RESOLVE_PYTHON
set "PYTHON_CMD="
set "PYTHON_ARGS="

if defined AUDION_ACTION_PYTHON if exist "%AUDION_ACTION_PYTHON%" (
  set "PYTHON_CMD=%AUDION_ACTION_PYTHON%"
  exit /b 0
)

if exist "%BASE_DIR%\runtime\python.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python.exe"
  exit /b 0
)

if exist "%BASE_DIR%\runtime\python\python.exe" (
  set "PYTHON_CMD=%BASE_DIR%\runtime\python\python.exe"
  exit /b 0
)

py -3.12 -V >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py"
  set "PYTHON_ARGS=-3.12"
  exit /b 0
)

exit /b 1

:NO_MAIN
echo [ERROR] Command bridge was not found:
echo %MAIN_FILE%
exit /b 1

:NO_PYTHON
echo [ERROR] Python runtime was not resolved.
echo Supported locations:
echo   runtime\python.exe
echo   runtime\python\python.exe
echo   py -3.12
echo   AUDION_ACTION_PYTHON=C:\path\to\python.exe
exit /b 1
