@echo off
setlocal enabledelayedexpansion
title Building TalonSync
cd /d "%~dp0"
echo.
echo   ===============================================
echo     TalonSync - building TalonSync.exe   (build script v3)
echo   ===============================================
echo.

rem ---- find a Python 3.10.1 or newer. Well-tested versions first, then the newest one you have.
rem      (Python 3.10.0 has a bug that crashes the exe builder, so it is never used.)
set "OKPY=import sys; v=sys.version_info[:3]; sys.exit(0 if v >= (3,10,1) else 1)"
set PY=
for %%V in (3.13 3.14 3.12 3.11 3.15 3.16 3.10) do (
    if not defined PY ( py -%%V -c "%OKPY%" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( py -3 -c "%OKPY%" >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python -c "%OKPY%" >nul 2>&1 && set "PY=python" )
if not defined PY (
    echo   No usable Python found ^(3.10.1 or newer^).
    echo   Install one from https://www.python.org/downloads/windows/
    echo   ^(tick "Add python.exe to PATH"^), then run this again.
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%I in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set "WANTV=%%I"
echo   Using Python %WANTV%  ^(%PY%^)

rem ---- a private environment so nothing touches your other Python stuff.
rem      Rebuilt automatically when it was made with a different Python.
set HAVEV=
if exist ".venv\Scripts\python.exe" for /f "delims=" %%I in ('.venv\Scripts\python.exe -c "import sys; print(sys.version.split()[0])" 2^>nul') do set "HAVEV=%%I"
if exist ".venv" if not "%HAVEV%"=="%WANTV%" (
    echo   The old build environment uses Python %HAVEV% - making a fresh one ...
    rmdir /s /q ".venv"
)
if not exist ".venv\Scripts\python.exe" (
    echo   Making a build environment in .venv ...
    %PY% -m venv .venv || goto :fail
)
set VPY=.venv\Scripts\python.exe
if exist build rmdir /s /q build

echo.
echo   Installing packages ^(first time takes a minute^) ...
"%VPY%" -m pip install --upgrade pip >nul 2>&1

rem PyInstaller makes the exe: the only package the build really needs.
"%VPY%" -m pip install --upgrade pyinstaller >nul 2>&1
if errorlevel 1 "%VPY%" -m pip install --upgrade --pre pyinstaller >nul 2>&1
if errorlevel 1 goto :nopyi
echo     [ok] PyInstaller

rem Everything else is optional: TalonSync has a fallback for each one.
call :opt Pillow "tray icon + importing pictures" "a plainer tray icon"
call :opt pystray "system tray icon" "no tray icon - closing the window quits"
call :opt zeroconf "OSCQuery" "plain OSC ports 9000/9001 only"
call :opt psutil "PC Link: CPU and memory load" "PC Link shows -- for CPU and RAM"
call :opt openvr "PC Link: headset and controller battery" "PC Link shows -- for batteries"
call :opt pywebview "app window" "TalonSync opens in an Edge app window instead - works the same"
"%VPY%" -m pip install winsdk >nul 2>&1
if errorlevel 1 "%VPY%" -m pip install winrt-runtime winrt-Windows.Media.Control winrt-Windows.Foundation >nul 2>&1
if errorlevel 1 ( echo     [--] Windows media controls: Now Playing reads player window titles instead ) else ( echo     [ok] Now Playing from Windows media controls )

echo.
echo   Running the self-tests ...
"%VPY%" tests\test_formats.py >nul || goto :fail
"%VPY%" tests\test_fake_sync.py >nul || goto :fail
echo   Self-tests passed.

echo.
echo   Building TalonSync.exe ...
"%VPY%" -m PyInstaller --noconfirm --clean TalonSync.spec
if errorlevel 1 goto :nopyi

copy /y "dist\TalonSync.exe" "TalonSync.exe" >nul
echo.
echo   ===============================================
echo     Done! TalonSync.exe is in this folder.
echo     Double-click it to start.
echo   ===============================================
echo.
echo   Tip: put an empty file called portable.txt next to TalonSync.exe to keep
echo   its data in a "TalonSync Data" folder beside it instead of %%APPDATA%%.
echo.
explorer /select,"%cd%\TalonSync.exe"
pause
exit /b 0

rem ---- optional package: name, what it gives, what happens without it
:opt
"%VPY%" -m pip install --upgrade %1 >nul 2>&1
if errorlevel 1 ( echo     [--] %~1: not available for Python %WANTV% - %~3 ) else ( echo     [ok] %~1 ^(%~2^) )
exit /b 0

:nopyi
echo.
echo   The exe builder ^(PyInstaller^) doesn't support Python %WANTV% yet.
echo.
echo   You can still use TalonSync right now: double-click
echo       "Run TalonSync (without building).bat"
echo   It runs the same app straight from this folder.
echo.
echo   To get the .exe later, install Python 3.13 or 3.14 too ^(python.org/downloads/windows^)
echo   and run this again - it picks those first.
pause
exit /b 1

:fail
echo.
echo   Something went wrong ^(see the messages above^).
echo   Copy them to Claude and we'll fix it.
pause
exit /b 1
