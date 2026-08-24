@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

title Audion PPTX Print to PDF Tool - Русский launcher

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"
cd /d "%BASE_DIR%"

set "RUNTIME_DIR=%BASE_DIR%\._runtime"
set "MENU_FILE=%RUNTIME_DIR%\project_menu_ru.txt"
set "RES_FILE=%RUNTIME_DIR%\project_menu_ru_res.txt"

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" >nul 2>nul
call :CLEAN_TEMP
call :RESOLVE_FZF
if errorlevel 1 (
  set "MENU_MODE=CMD fallback"
) else (
  set "MENU_MODE=FZF"
)

:MAIN
cls
call :SHOW_HEADER
if /I "%AUDION_AUTO_EXIT%"=="1" exit /b 0

if defined FZF_CMD goto FZF_MENU
goto FALLBACK_MENU

:FZF_MENU
call :CLEAN_TEMP
> "%MENU_FILE%" echo [GUI] ОТКРЫТЬ GUI SHELL                        ^| gui               ^| guided NiceGUI-сценарий
>>"%MENU_FILE%" echo [01] ВКЛЮЧИТЬ MICROSOFT PRINT TO PDF           ^| enable_default    ^| сохранить текущий принтер и переключить
>>"%MENU_FILE%" echo [02] РАСПЕЧАТАТЬ ВСЕ PPTX ИЗ INPUT             ^| print_input       ^| ручное сохранение в output
>>"%MENU_FILE%" echo [03] ОБРЕЗАТЬ ВСЕ PDF В OUTPUT ДО EXACT 16:9   ^| crop_output_exact ^| перезапись PDF на месте
>>"%MENU_FILE%" echo [04] ОБРЕЗАТЬ ВСЕ PDF В OUTPUT ДО A4/A3        ^| crop_output_a     ^| перезапись PDF на месте
>>"%MENU_FILE%" echo [05] ВЕРНУТЬ ПРЕДЫДУЩИЙ ПРИНТЕР ПО УМОЛЧАНИЮ   ^| restore_default   ^| восстановить сохранённый принтер
>>"%MENU_FILE%" echo [06] DOCTOR                                    ^| doctor            ^| проверить окружение и состояние принтера
>>"%MENU_FILE%" echo.
>>"%MENU_FILE%" echo [07] ОТКРЫТЬ ПАПКУ INPUT                       ^| open_input        ^| explorer
>>"%MENU_FILE%" echo [08] ОТКРЫТЬ ПАПКУ OUTPUT                      ^| open_output       ^| explorer
>>"%MENU_FILE%" echo [09] ОТКРЫТЬ ПАПКУ LOGS                        ^| open_logs         ^| explorer
>>"%MENU_FILE%" echo [10] СЛУЖЕБНЫЙ LAUNCHER                        ^| tools             ^| сервисное и builder-меню
>>"%MENU_FILE%" echo [00] ВЫХОД                                     ^| exit              ^| закрыть

type "%MENU_FILE%" | "%FZF_CMD%" --prompt="audion@pptx-print [RU] > " --pointer=">" --header="Выбери действие:" --layout=reverse --border="rounded" --info=hidden --margin=1,2 > "%RES_FILE%"

set "CHOICE="
set /p CHOICE=<"%RES_FILE%"
if not defined CHOICE goto MAIN

for /f "tokens=2 delims=|" %%a in ("%CHOICE%") do set "RAW=%%a"
call :TRIM RAW

if /I "%RAW%"=="enable_default" goto ENABLE_DEFAULT
if /I "%RAW%"=="print_input" goto PRINT_INPUT
if /I "%RAW%"=="crop_output_exact" goto CROP_OUTPUT_EXACT
if /I "%RAW%"=="crop_output_a" goto CROP_OUTPUT_A_SERIES
if /I "%RAW%"=="restore_default" goto RESTORE_DEFAULT
if /I "%RAW%"=="doctor" goto DOCTOR
if /I "%RAW%"=="gui" goto GUI
if /I "%RAW%"=="open_input" goto OPEN_INPUT
if /I "%RAW%"=="open_output" goto OPEN_OUTPUT
if /I "%RAW%"=="open_logs" goto OPEN_LOGS
if /I "%RAW%"=="tools" goto TOOLS
if /I "%RAW%"=="exit" exit /b 0
goto MAIN

:FALLBACK_MENU
echo [G] Открыть GUI shell
echo [1] Включить Microsoft Print to PDF и сделать его принтером по умолчанию
echo [2] Распечатать все PPTX-файлы из input
echo [3] Обрезать все PDF в output до exact 16:9
echo [4] Обрезать все PDF в output до A4/A3
echo [5] Вернуть предыдущий принтер по умолчанию
echo [6] Doctor
echo [A] Открыть папку input
echo [B] Открыть папку output
echo [C] Открыть папку logs
echo [T] Служебный launcher
echo [0] Выход
echo.
choice /C G123456ABCT0 /N /M "Выбор: "
if errorlevel 12 exit /b 0
if errorlevel 11 goto TOOLS
if errorlevel 10 goto OPEN_LOGS
if errorlevel 9 goto OPEN_OUTPUT
if errorlevel 8 goto OPEN_INPUT
if errorlevel 7 goto DOCTOR
if errorlevel 6 goto RESTORE_DEFAULT
if errorlevel 5 goto CROP_OUTPUT_A_SERIES
if errorlevel 4 goto CROP_OUTPUT_EXACT
if errorlevel 3 goto PRINT_INPUT
if errorlevel 2 goto ENABLE_DEFAULT
if errorlevel 1 goto GUI
goto MAIN

:GUI
if exist "%BASE_DIR%\launcher_gui.cmd" (
  call "%BASE_DIR%\launcher_gui.cmd"
) else (
  echo [ERROR] launcher_gui.cmd не найден.
  if not defined AUDION_NO_PAUSE pause
)
goto MAIN

:ENABLE_DEFAULT
call :RUN_ACTION enable-default
goto MAIN

:PRINT_INPUT
call :RUN_ACTION print-input
goto MAIN

:CROP_OUTPUT_EXACT
call :RUN_ACTION crop-output-exact
goto MAIN

:CROP_OUTPUT_A_SERIES
call :RUN_ACTION crop-output-a-series
goto MAIN

:RESTORE_DEFAULT
call :RUN_ACTION restore-default
goto MAIN

:DOCTOR
call :RUN_ACTION doctor
goto MAIN

:OPEN_INPUT
start "" explorer "%BASE_DIR%\input"
goto MAIN

:OPEN_OUTPUT
start "" explorer "%BASE_DIR%\output"
goto MAIN

:OPEN_LOGS
start "" explorer "%BASE_DIR%\logs"
goto MAIN

:TOOLS
if exist "%BASE_DIR%\launcher_tools.cmd" (
  call "%BASE_DIR%\launcher_tools.cmd"
) else (
  echo [ERROR] launcher_tools.cmd не найден.
  if not defined AUDION_NO_PAUSE pause
)
goto MAIN

:RUN_ACTION
call "%BASE_DIR%\run_action.cmd" %*
if not defined AUDION_NO_PAUSE pause
goto :eof

:SHOW_HEADER
echo ======================================================================
echo   AUDION PPTX PRINT TO PDF TOOL
echo ======================================================================
echo Корень:      %BASE_DIR%
echo Режим меню:  %MENU_MODE%
echo.
goto :eof

:RESOLVE_FZF
set "FZF_CMD="
if /I "%AUDION_DISABLE_FZF%"=="1" exit /b 1
if exist "%BASE_DIR%\system_core\fzf.exe" (
  set "FZF_CMD=%BASE_DIR%\system_core\fzf.exe"
  exit /b 0
)
where fzf.exe >nul 2>nul
if not errorlevel 1 (
  set "FZF_CMD=fzf.exe"
  exit /b 0
)
where fzf >nul 2>nul
if not errorlevel 1 (
  set "FZF_CMD=fzf"
  exit /b 0
)
exit /b 1

:CLEAN_TEMP
if exist "%MENU_FILE%" del /f /q "%MENU_FILE%" >nul 2>nul
if exist "%RES_FILE%" del /f /q "%RES_FILE%" >nul 2>nul
goto :eof

:TRIM
for /f "tokens=* delims= " %%z in ("!%~1!") do set "%~1=%%z"
:TRIM_R
if "!%~1:~-1!"==" " set "%~1=!%~1:~0,-1!" & goto TRIM_R
goto :eof
