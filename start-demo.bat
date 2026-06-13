@echo off
chcp 65001 >nul
title 智能冰箱 - 一键演示启动器

REM ============================================================
REM  一键启动：后端 + 前端 + 端侧模拟器，各开一个窗口
REM  双击本文件即可。关闭演示：直接关掉弹出的三个黑窗口。
REM ============================================================

set ROOT=%~dp0
echo.
echo ============================================================
echo   智能冰箱食材管理系统 - 演示启动器
echo ============================================================
echo   后端端口: 8000
echo   前端端口: 3000 (若被占用会自动顺延到 3001)
echo   conda 环境: fastapi
echo ============================================================
echo.

REM ---- 1) 启动后端 (FastAPI) ----
echo [1/3] 正在启动后端 (FastAPI)...
start "冰箱-后端 8000" cmd /k "cd /d %ROOT%client && call conda activate fastapi && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

REM ---- 2) 启动前端 (Vite) ----
echo [2/3] 正在启动前端 (Vite)...
start "冰箱-前端 3000" cmd /k "cd /d %ROOT%web && call conda activate fastapi && npm run dev"

REM ---- 3) 等后端就绪后启动端侧模拟器 (持续发事件，让大屏有实时数据) ----
echo [3/3] 等待后端就绪后启动端侧模拟器...
timeout /t 10 /nobreak >nul
start "冰箱-端侧模拟器" cmd /k "cd /d %ROOT%client && call conda activate fastapi && python demo/luckfox_simulator.py loop --interval 15 --probability 0.6"

REM ---- 再等几秒让前端编译完成，自动打开浏览器 ----
echo.
echo 等待前端编译完成，即将打开浏览器...
timeout /t 8 /nobreak >nul
start "" "http://localhost:3000"

echo.
echo ============================================================
echo   全部启动完成!
echo   - 浏览器已打开 http://localhost:3000
echo   - 如果页面打不开, 看 "冰箱-前端" 窗口里显示的实际端口
echo     (可能是 http://localhost:3001)
echo   - 开发演示账号: admin/admin123 (管理员，仅开发默认)  xiaoyu/test123 (用户)
echo   - 关闭演示: 直接关掉弹出的三个黑色窗口
echo ============================================================
echo.
echo 本窗口可以关闭了。
pause
