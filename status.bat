@echo off
chcp 65001 >nul
echo ========================================
echo 📊 医疗AI平台 - 服务状态检查
echo ========================================
echo.

echo 🔍 检查Python进程...
tasklist | findstr python.exe >nul 2>&1
if %errorlevel%==0 (
    echo ✅ 发现运行中的Python进程:
    echo.
    tasklist | findstr python.exe
) else (
    echo ❌ 没有发现运行中的Python进程
)

echo.
echo ========================================
echo 🔍 检查端口占用情况...
echo ========================================
echo.

echo 后端服务端口 (5000):
netstat -ano | findstr ":5000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo ✅ 端口5000正在监听
    netstat -ano | findstr ":5000" | findstr "LISTENING"
) else (
    echo ❌ 端口5000未被占用
)

echo.
echo 前端服务端口 (8000):
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo ✅ 端口8000正在监听
    netstat -ano | findstr ":8000" | findstr "LISTENING"
) else (
    echo ❌ 端口8000未被占用
)

echo.
echo ========================================
echo 💡 服务访问地址
echo ========================================
echo.
echo 前端网页: http://localhost:8000
echo 后端API:  http://localhost:5000
echo.
echo 💡 如果服务未运行，请执行: start.bat
echo.
pause

