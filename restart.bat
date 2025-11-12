@echo off
chcp 65001 >nul
echo ========================================
echo 🔄 医疗AI平台 - 重启服务
echo ========================================
echo.

echo 步骤1: 停止现有服务...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo ✅ 已停止

echo.
echo 步骤2: 重新启动服务...
cd /d "%~dp0"

echo 🚀 启动后端服务...
start "医疗AI后端服务" /MIN cmd /c "python backend_server.py"
timeout /t 3 /nobreak >nul

echo 🌐 启动前端服务...
start "医疗AI前端服务" /MIN cmd /c "python -m http.server 8000"
timeout /t 2 /nobreak >nul

echo 🌍 打开浏览器...
start http://localhost:8000

echo.
echo ========================================
echo ✅ 重启完成！
echo ========================================
echo.
pause

