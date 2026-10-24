@echo off
rem Runs TalonSync without building the exe (needs "Build TalonSync.bat" to have made .venv,
rem or any Python 3.10.1+ with no extra packages - it then opens in an Edge app window).
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" ( start "" ".venv\Scripts\pythonw.exe" talonsync_main.py %* & exit /b )
where pyw >nul 2>&1 && ( start "" pyw -3 talonsync_main.py %* & exit /b )
python talonsync_main.py %*
