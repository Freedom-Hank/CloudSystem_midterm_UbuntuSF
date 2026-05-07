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
echo   [1] 執行自動化腳本 (start_demo.sh)
echo   [2] 開啟 6 個瀏覽器分頁查看節點
echo   [3] 清除所有交易紀錄
echo   [0] 離開
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
rem 找一個真正能用的 bash。不要依賴 `where bash`：Windows 自帶
rem System32\bash.exe 只是 WSL 啟動器，遇到 Docker Desktop 的
rem "docker-desktop" distro（常常是預設）會炸 "/bin/bash: No such file"。
rem 所以先掃 Git Bash 的已知路徑。
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
    rem 先試 Ubuntu，找不到再回退到預設 distro。
    wsl -d Ubuntu -- bash ./start_demo.sh 2>nul
    if !errorlevel! == 0 goto run_done
    wsl bash ./start_demo.sh
    goto run_done
)
echo [錯誤] 找不到可用的 bash。請安裝 Git for Windows 或設定一個正常的 WSL distro（例如 Ubuntu）。
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