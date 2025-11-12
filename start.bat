@echo off
chcp 65001 >nul
echo ========================================
echo 🏥 医疗AI平台 - 启动服务
echo ========================================
echo.

cd /d "%~dp0"

echo 正在检查端口占用...
netstat -ano | findstr ":5000 :8000" >nul 2>&1
if %errorlevel%==0 (
    echo ⚠️  检测到端口已被占用，正在清理...
    taskkill /F /IM python.exe >nul 2>&1
    timeout /t 2 /nobreak >nul
)

echo 🚀 正在启动后端服务 (端口5000)...
start "医疗AI后端服务" /MIN cmd /c "python backend_server.py"
timeout /t 3 /nobreak >nul

echo 🌐 正在启动前端服务 (端口8000)...
start "医疗AI前端服务" /MIN cmd /c "python -m http.server 8000"
timeout /t 2 /nobreak >nul

echo 🌍 正在打开浏览器...
start http://localhost:8000

echo.
echo ========================================
echo ✅ 服务启动完成！
echo ========================================
echo.
echo 📱 访问地址:
echo    前端网页: http://localhost:8000
echo    后端API:  http://localhost:5000
echo.
echo 💡 提示:
echo    - 浏览器会自动打开
echo    - 后台服务正在运行中
echo    - 关闭窗口不会停止服务
echo    - 要停止服务请运行 stop.bat
echo.
echo ========================================
pause

