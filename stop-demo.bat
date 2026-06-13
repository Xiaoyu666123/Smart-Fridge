@echo off
chcp 65001 >nul
title 智能冰箱 - 停止演示

REM ============================================================
REM  停止演示：关掉占用 8000 / 3000 / 3001 端口的进程
REM  以及残留的 uvicorn / vite / 模拟器
REM ============================================================

echo 正在停止演示相关进程...

REM 按端口杀进程（8000 后端 / 3000 3001 前端）
for %%P in (8000 3000 3001) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
        echo   关闭占用端口 %%P 的进程 PID=%%a
        taskkill /F /PID %%a >nul 2>&1
    )
)

REM 关掉按标题命名的演示窗口（start-demo.bat 起的那三个）
taskkill /F /FI "WINDOWTITLE eq 冰箱-后端*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq 冰箱-前端*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq 冰箱-端侧模拟器*" >nul 2>&1

echo.
echo 已停止。如仍有残留, 可手动关闭对应黑窗口。
timeout /t 3 /nobreak >nul
