@echo off
cd /d "%~dp0"

set "MPLCONFIGDIR=%TEMP%\matplotlib_cache"
if not exist "%MPLCONFIGDIR%" mkdir "%MPLCONFIGDIR%" 2>nul

python "%~dp0deepseek_monitor.py"
pause
