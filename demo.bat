@echo off
rem Windows 端的 demo 控制台。把工作目錄切到 .bat 所在資料夾，
rem 之後不論從哪裡按兩下都不會找錯路徑。
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
echo   [2] 清除所有交易紀錄
echo   [3] 開啟 6 個瀏覽器分頁查看節點
echo   [0] 離開
echo ==========================================
set "choice="
set /p "choice=請選擇 (0-3): "

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
echo [錯誤] 找不到 wsl 或 bash，請先安裝 WSL2 或 Git Bash。
:run_done
echo.
pause
goto menu

:clear_tx
echo.
echo --- 清除 storage\client{1,2,3}\*.txt ---
del /Q ".\storage\client1\*.txt" 2>nul
del /Q ".\storage\client2\*.txt" 2>nul
del /Q ".\storage\client3\*.txt" 2>nul
echo done.
echo.
pause
goto menu

:open_browsers
echo.
echo --- 開啟 6 個瀏覽器分頁 ---
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
