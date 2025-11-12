@echo off
chcp 65001 >nul
echo ========================================
echo 🚀 医疗AI平台 - 一键部署脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/6] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误: 未检测到Python环境！
    echo 请先安装Python 3.7或更高版本
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Python版本: %PYTHON_VERSION%

echo.
echo [2/6] 检查pip工具...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误: pip未安装或不可用
    pause
    exit /b 1
)
echo ✅ pip工具正常

echo.
echo [3/6] 创建必要的目录结构...
if not exist "data" mkdir data
if not exist "data\uploads" mkdir data\uploads
if not exist "__pycache__" mkdir __pycache__
echo ✅ 目录结构已创建

echo.
echo [4/6] 检查并初始化数据文件...
python -c "import os; import json; data_dir='data'; os.makedirs(data_dir, exist_ok=True); files={'users.json':[],'records.json':[],'community.json':[],'pre_consultation_pushes.json':[],'medications.json':[],'medication_intake_records.json':[],'medication_reminders.json':[],'tcm_archives.json':[]}; [open(os.path.join(data_dir,f),'w',encoding='utf-8').write(json.dumps(v,ensure_ascii=False,indent=2)) if not os.path.exists(os.path.join(data_dir,f)) else None for f,v in files.items()]" 2>nul
echo ✅ 数据文件已初始化

echo.
echo [5/6] 安装Python依赖包...
echo 正在安装依赖包，请稍候...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ⚠️  警告: 部分依赖包安装可能失败
    echo 请检查网络连接或手动运行: pip install -r requirements.txt
) else (
    echo ✅ 依赖包安装完成
)

echo.
echo [6/6] 检查端口占用情况...
netstat -ano | findstr ":5000 :8000" >nul 2>&1
if %errorlevel%==0 (
    echo ⚠️  警告: 端口5000或8000已被占用
    echo 部署完成后可能需要先停止占用这些端口的程序
) else (
    echo ✅ 端口可用
)

echo.
echo ========================================
echo ✅ 部署完成！
echo ========================================
echo.
echo 📋 部署信息:
echo    • Python版本: %PYTHON_VERSION%
echo    • 数据目录: %CD%\data
echo    • 后端服务端口: 5000
echo    • 前端服务端口: 8000
echo.
echo 🔑 重要配置:
echo    1. API密钥配置: 编辑 backend_server.py 第239行
echo       或设置环境变量: DASHSCOPE_API_KEY=你的密钥
echo    2. 百度地图API: 编辑 index.html 中的百度地图API密钥
echo.
echo 🚀 启动方式:
echo    • 方式1: 双击 start.bat
echo    • 方式2: 运行 python start_app.py
echo.
echo 📱 访问地址:
echo    • 前端: http://localhost:8000
echo    • 后端API: http://localhost:5000
echo.
echo 💡 提示:
echo    • 首次部署建议检查 config.env 文件（如存在）
echo    • 部署到服务器时请配置防火墙规则
echo    • 建议使用生产环境时配置HTTPS
echo.
echo ========================================
pause


