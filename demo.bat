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
echo   [2] Open 6 browser tabs (localhost + 100.122.78.117)
echo   [3] Clear transaction logs (storage/client*/*.txt)
echo   [0] Quit
echo ==========================================
set "choice="
set /p "choice=Choose (0-3): "

if "%choice%"=="1" goto run_demo
if "%choice%"=="2" goto open_browsers
if "%choice%"=="3" goto clear_tx
if "%choice%"=="0" goto end
goto menu

:run_demo
echo.
echo --- start_demo.sh ---
set "GITBASH="
if exist "%ProgramFiles%\Git\bin\bash.exe"        set "GITBASH=%ProgramFiles%\Git\bin\bash.exe"
if not defined GITBASH if exist "%ProgramFiles%\Git\usr\bin\bash.exe"     set "GITBASH=%ProgramFiles%\Git\usr\bin\bash.exe"
if not defined GITBASH if exist "%ProgramFiles(x86)%\Git\bin\bash.exe"    set "GITBASH=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined GITBASH if exist "%LocalAppData%\Programs\Git\bin\bash.exe" set "GITBASH=%LocalAppData%\Programs\Git\bin\bash.exe"
if defined GITBASH (
    "%GITBASH%" start_demo.sh
    goto run_done
)
where wsl >nul 2>nul
if !errorlevel! == 0 (
    wsl -d Ubuntu -- bash ./start_demo.sh 2>nul
    if !errorlevel! == 0 goto run_done
    wsl bash ./start_demo.sh
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