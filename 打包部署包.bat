@echo off
chcp 65001 >nul
echo ========================================
echo 📦 医疗AI平台 - 打包部署包
echo ========================================
echo.

cd /d "%~dp0"

set PACKAGE_NAME=医疗AI平台_部署包_%date:~0,4%%date:~5,2%%date:~8,2%
set PACKAGE_DIR=%PACKAGE_NAME%

echo [1/5] 创建部署包目录...
if exist "%PACKAGE_DIR%" rmdir /s /q "%PACKAGE_DIR%"
mkdir "%PACKAGE_DIR%"
echo ✅ 目录已创建: %PACKAGE_DIR%

echo.
echo [2/5] 复制必需文件...

REM 后端文件
copy backend_server.py "%PACKAGE_DIR%\" >nul
copy medication_management.py "%PACKAGE_DIR%\" >nul 2>&1

REM 前端文件
copy index.html "%PACKAGE_DIR%\" >nul
copy medication.html "%PACKAGE_DIR%\" >nul 2>&1
copy script.js "%PACKAGE_DIR%\" >nul
copy ai-medical.js "%PACKAGE_DIR%\" >nul
copy medication.js "%PACKAGE_DIR%\" >nul 2>&1
copy pre_consultation.js "%PACKAGE_DIR%\" >nul 2>&1
copy utils_camera.js "%PACKAGE_DIR%\" >nul 2>&1
copy styles.css "%PACKAGE_DIR%\" >nul
copy service-worker.js "%PACKAGE_DIR%\" >nul 2>&1

REM 启动脚本
copy start_app.py "%PACKAGE_DIR%\" >nul
copy start.bat "%PACKAGE_DIR%\" >nul
copy restart.bat "%PACKAGE_DIR%\" >nul 2>&1
copy stop.bat "%PACKAGE_DIR%\" >nul 2>&1

REM 部署脚本
copy deploy.bat "%PACKAGE_DIR%\" >nul
copy deploy.sh "%PACKAGE_DIR%\" >nul 2>&1
copy check_environment.py "%PACKAGE_DIR%\" >nul
copy start.sh "%PACKAGE_DIR%\" >nul 2>&1

REM 配置文件
copy requirements.txt "%PACKAGE_DIR%\" >nul
copy config.example "%PACKAGE_DIR%\" >nul 2>&1
copy deploy_files.txt "%PACKAGE_DIR%\" >nul 2>&1
copy 部署指南.md "%PACKAGE_DIR%\" >nul 2>&1
copy README.md "%PACKAGE_DIR%\" >nul 2>&1

REM 创建数据目录结构
mkdir "%PACKAGE_DIR%\data" >nul 2>&1
mkdir "%PACKAGE_DIR%\data\uploads" >nul 2>&1

REM 复制中医部分（如果存在）
if exist "中医部分" (
    echo    正在复制中医功能模块...
    xcopy /E /I /Y "中医部分" "%PACKAGE_DIR%\中医部分\" >nul 2>&1
)

echo ✅ 文件复制完成

echo.
echo [3/5] 创建快速开始文档...
(
echo # 快速开始
echo.
echo ## Windows用户
echo 1. 双击运行 deploy.bat 进行环境检查和依赖安装
echo 2. 双击运行 start.bat 启动服务
echo 3. 浏览器会自动打开，或手动访问: http://localhost:8000
echo.
echo ## Linux/Mac用户
echo 1. 运行: chmod +x deploy.sh start.sh
echo 2. 运行: ./deploy.sh
echo 3. 运行: ./start.sh
echo 4. 访问: http://localhost:8000
echo.
echo ## 重要配置
echo - 编辑 backend_server.py 配置 Qwen API密钥
echo - 编辑 index.html 配置百度地图API密钥
echo.
echo 详细说明请查看: 部署指南.md
) > "%PACKAGE_DIR%\快速开始.txt"
echo ✅ 快速开始文档已创建

echo.
echo [4/5] 创建部署说明...
(
echo ========================================
echo 📋 部署包内容说明
echo ========================================
echo.
echo ✅ 已包含的文件:
echo    - 后端服务文件 (backend_server.py等)
echo    - 前端文件 (index.html, *.js, *.css)
echo    - 启动脚本 (start.bat, start.sh等)
echo    - 部署脚本 (deploy.bat, deploy.sh)
echo    - 配置文件 (requirements.txt等)
echo    - 数据目录结构 (data/)
echo.
echo ⚠️  不包含的内容:
echo    - Python运行环境 (需要单独安装)
echo    - 数据文件 (首次运行会自动创建)
echo    - 日志文件
echo    - 测试文件
echo.
echo 📝 部署步骤:
echo    1. 确保已安装Python 3.7+
echo    2. 运行部署脚本: deploy.bat 或 deploy.sh
echo    3. 配置API密钥 (见部署指南.md)
echo    4. 运行启动脚本启动服务
echo.
echo 📚 详细文档: 部署指南.md
echo.
echo ========================================
) > "%PACKAGE_DIR%\部署说明.txt"
echo ✅ 部署说明已创建

echo.
echo [5/5] 清理临时文件...
REM 不清理，保持完整

echo.
echo ========================================
echo ✅ 打包完成！
echo ========================================
echo.
echo 📦 部署包位置: %CD%\%PACKAGE_DIR%
echo.
echo 📋 下一步:
echo    1. 将 "%PACKAGE_DIR%" 文件夹复制到目标电脑
echo    2. 在目标电脑上运行 deploy.bat (Windows) 或 deploy.sh (Linux/Mac)
echo    3. 按照部署指南配置API密钥
echo    4. 启动服务并访问应用
echo.
echo 💡 提示:
echo    - 部署包大小约: 
dir /s /-c "%PACKAGE_DIR%" | find "个文件" > "%TEMP%\size.txt"
echo    - 可以压缩成ZIP文件方便传输
echo    - 建议在目标环境先运行 check_environment.py 检查环境
echo.
echo ========================================
pause


