@echo off
rem Demo console for Windows / Docker Desktop.
rem Menu strings are kept ASCII on purpose: cmd.exe parses .bat files using
rem the system ANSI codepage (cp950 on zh-TW), which mangles UTF-8 Chinese
rem and turns parts of lines into bogus commands.
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Vortex P2P Demo

:menu
cls
echo ==========================================
echo   Vortex P2P  Demo Launcher
echo ==========================================
echo   [1] Run start_demo.sh
echo   [2] Clear transaction logs (storage/client*/*.txt)
echo   [3] Open 6 browser tabs (localhost + 100.122.78.117)
echo   [0] Quit
echo ==========================================
set "choice="
set /p "choice=Choose (0-3): "

if "%choice%"=="1" goto run_demo
if "%choice%"=="2" goto clear_tx
if "%choice%"=="3" goto open_browsers
if "%choice%"=="0" goto end
goto menu

:run_demo
echo.
echo --- start_demo.sh ---
where wsl >nul 2>nul
if !errorlevel! == 0 (
    wsl bash ./start_demo.sh
    goto run_done
)
where bash >nul 2>nul
if !errorlevel! == 0 (
    bash start_demo.sh
    goto run_done
)
echo [error] neither wsl nor bash found. Install WSL2 or Git Bash first.
:run_done
echo.
pause
goto menu

:clear_tx
echo.
echo --- clearing storage\client{1,2,3}\*.txt ---
del /Q ".\storage\client1\*.txt" 2>nul
del /Q ".\storage\client2\*.txt" 2>nul
del /Q ".\storage\client3\*.txt" 2>nul
echo done.
echo.
pause
goto menu

:open_browsers
echo.
echo --- opening 6 browser tabs ---
start "" "http://localhost:8081"
start "" "http://localhost:8082"
start "" "http://localhost:8083"
start "" "http://100.122.78.117:8081"
start "" "http://100.122.78.117:8082"
start "" "http://100.122.78.117:8083"
goto menu

:end
endlocal
exit /b 0
