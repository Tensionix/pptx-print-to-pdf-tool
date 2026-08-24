@echo off
chcp 65001 >nul
call "%~dp0run_action.cmd" doctor
if not defined AUDION_NO_PAUSE pause
