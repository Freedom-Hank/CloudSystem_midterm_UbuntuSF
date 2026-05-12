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
echo   [1] Run start_demo.sh (Full, 6 nodes - PC + Macbook)
echo   [2] Run start_demo.sh (Solo, 3 nodes - PC only)
echo   [3] Open 6 browser tabs (localhost + 100.122.78.117)
echo   [4] Clear transaction logs (storage/client*/*.txt)
echo   [0] Quit
echo ==========================================
set "choice="
set /p "choice=Choose (0-4): "

if "%choice%"=="1" goto run_demo
if "%choice%"=="2" goto run_demo_solo
if "%choice%"=="3" goto open_browsers
if "%choice%"=="4" goto clear_tx
if "%choice%"=="0" goto end
goto menu

:run_demo_solo
echo.
echo --- start_demo.sh (Solo mode, EXPECTED_NODES=3) ---
set "EXPECTED_NODES=3"
goto run_demo_dispatch

:run_demo
echo.
echo --- start_demo.sh ---
set "EXPECTED_NODES=6"

:run_demo_dispatch
set "GITBASH="
if exist "%ProgramFiles%\Git\bin\bash.exe"        set "GITBASH=%ProgramFiles%\Git\bin\bash.exe"
if not defined GITBASH if exist "%ProgramFiles%\Git\usr\bin\bash.exe"     set "GITBASH=%ProgramFiles%\Git\usr\bin\bash.exe"
if not defined GITBASH if exist "%ProgramFiles(x86)%\Git\bin\bash.exe"    set "GITBASH=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined GITBASH if exist "%LocalAppData%\Programs\Git\bin\bash.exe" set "GITBASH=%LocalAppData%\Programs\Git\bin\bash.exe"
rem 顯式把 EXPECTED_NODES 帶進 bash 子環境，避免 WSL/Git Bash 預設不繼承 cmd 的環境變數
if defined GITBASH (
    "%GITBASH%" -c "EXPECTED_NODES=%EXPECTED_NODES% ./start_demo.sh"
    goto run_done
)
where wsl >nul 2>nul
if !errorlevel! == 0 (
    wsl -d Ubuntu -- bash -c "EXPECTED_NODES=%EXPECTED_NODES% ./start_demo.sh" 2>nul
    if !errorlevel! == 0 goto run_done
    wsl bash -c "EXPECTED_NODES=%EXPECTED_NODES% ./start_demo.sh"
    goto run_done
)
echo [error] no usable bash found. Install Git for Windows or set up a real WSL distro (e.g. Ubuntu).
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
echo --- stopping and removing containers ---
docker-compose down
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