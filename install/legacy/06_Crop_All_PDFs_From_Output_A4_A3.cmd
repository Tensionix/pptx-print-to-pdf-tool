@echo off
chcp 65001 >nul
call "%~dp0run_action.cmd" crop-output-a-series
if not defined AUDION_NO_PAUSE pause
