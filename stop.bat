@echo off
chcp 65001 >nul
echo ========================================
echo 🛑 医疗AI平台 - 停止服务
echo ========================================
echo.

echo 正在检查运行中的服务...
tasklist | findstr python.exe >nul 2>&1
if %errorlevel%==0 (
    echo 🔍 发现以下Python进程:
    tasklist | findstr python.exe
    echo.
    echo 正在停止所有服务...
    taskkill /F /IM python.exe >nul 2>&1
    timeout /t 1 /nobreak >nul
    echo ✅ 所有服务已停止
) else (
    echo ℹ️  没有发现运行中的服务
)

echo.
echo ========================================
echo 🏁 操作完成
echo ========================================
echo.
echo 💡 提示:
echo    - 所有Python进程已终止
echo    - 端口5000和8000已释放
echo    - 可以重新运行 start.bat 启动服务
echo.
pause

