#!/bin/bash

echo "========================================"
echo "🚀 医疗AI平台 - 一键部署脚本 (Linux/Mac)"
echo "========================================"
echo ""

cd "$(dirname "$0")"

echo "[1/6] 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未检测到Python3环境！"
    echo "请先安装Python 3.7或更高版本"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo "✅ $PYTHON_VERSION"

echo ""
echo "[2/6] 检查pip工具..."
if ! command -v pip3 &> /dev/null; then
    echo "❌ 错误: pip3未安装或不可用"
    exit 1
fi
echo "✅ pip工具正常"

echo ""
echo "[3/6] 创建必要的目录结构..."
mkdir -p data/uploads
mkdir -p __pycache__
echo "✅ 目录结构已创建"

echo ""
echo "[4/6] 检查并初始化数据文件..."
python3 << 'EOF'
import os
import json

data_dir = 'data'
os.makedirs(data_dir, exist_ok=True)

files = {
    'users.json': [],
    'records.json': [],
    'community.json': [],
    'pre_consultation_pushes.json': [],
    'medications.json': [],
    'medication_intake_records.json': [],
    'medication_reminders.json': [],
    'tcm_archives.json': []
}

for filename, default_content in files.items():
    filepath = os.path.join(data_dir, filename)
    if not os.path.exists(filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(default_content, f, ensure_ascii=False, indent=2)
EOF
echo "✅ 数据文件已初始化"

echo ""
echo "[5/6] 安装Python依赖包..."
echo "正在安装依赖包，请稍候..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo "⚠️  警告: 部分依赖包安装可能失败"
    echo "请检查网络连接或手动运行: pip3 install -r requirements.txt"
else
    echo "✅ 依赖包安装完成"
fi

echo ""
echo "[6/6] 检查端口占用情况..."
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1 || lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  警告: 端口5000或8000已被占用"
    echo "部署完成后可能需要先停止占用这些端口的程序"
else
    echo "✅ 端口可用"
fi

echo ""
echo "========================================"
echo "✅ 部署完成！"
echo "========================================"
echo ""
echo "📋 部署信息:"
echo "   • Python版本: $PYTHON_VERSION"
echo "   • 数据目录: $(pwd)/data"
echo "   • 后端服务端口: 5000"
echo "   • 前端服务端口: 8000"
echo ""
echo "🔑 重要配置:"
echo "   1. API密钥配置: 编辑 backend_server.py 第239行"
echo "      或设置环境变量: export DASHSCOPE_API_KEY=你的密钥"
echo "   2. 百度地图API: 编辑 index.html 中的百度地图API密钥"
echo ""
echo "🚀 启动方式:"
echo "   • 方式1: bash start.sh (如果存在)"
echo "   • 方式2: python3 start_app.py"
echo "   • 方式3: 分别启动后端和前端"
echo ""
echo "📱 访问地址:"
echo "   • 前端: http://localhost:8000"
echo "   • 后端API: http://localhost:5000"
echo ""
echo "💡 提示:"
echo "   • 首次部署建议检查 .env 文件（如存在）"
echo "   • 部署到服务器时请配置防火墙规则"
echo "   • 建议使用生产环境时配置HTTPS"
echo ""
echo "========================================"


