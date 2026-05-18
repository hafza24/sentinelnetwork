@echo off
REM ============================================================
REM  Sentinel Net - Windows executable builder
REM  Produces single-file .exe artifacts via PyInstaller:
REM    - SentinelAgent.exe   (headless agent + watchdog)
REM    - SentinelTray.exe    (system tray UI)
REM    - SentinelInstaller.exe
REM ============================================================
setlocal enableextensions

echo [build] Sentinel Net executable builder
echo [build] python: %PYTHON%
if "%PYTHON%"=="" set PYTHON=python

echo [build] upgrading pip and installing build deps...
%PYTHON% -m pip install --upgrade pip wheel || goto :fail
%PYTHON% -m pip install --upgrade pyinstaller httpx psutil pystray Pillow plyer websocket-client || goto :fail

if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo [build] building SentinelAgent.exe (windowed, no console)...
%PYTHON% -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name SentinelAgent ^
    --hidden-import=plyer.platforms.win.notification ^
    --hidden-import=pystray._win32 ^
    --collect-submodules websocket ^
    sentinel_agent.py || goto :fail

echo [build] building SentinelTray.exe...
%PYTHON% -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name SentinelTray ^
    --hidden-import=plyer.platforms.win.notification ^
    --hidden-import=pystray._win32 ^
    sentinel_tray.py || goto :fail

echo [build] building SentinelInstaller.exe...
%PYTHON% -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --console ^
    --name SentinelInstaller ^
    installer.py || goto :fail

echo.
echo [build] SUCCESS — artifacts in .\dist\
dir /b dist
exit /b 0

:fail
echo [build] FAILED
exit /b 1
