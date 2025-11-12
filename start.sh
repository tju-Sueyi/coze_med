#!/bin/bash

echo "========================================"
echo "🏥 医疗AI平台 - 启动服务"
echo "========================================"
echo ""

cd "$(dirname "$0")"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未检测到Python3环境！"
    exit 1
fi

# 检查端口占用
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1 || lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  检测到端口已被占用，正在清理..."
    pkill -f "python.*backend_server.py" 2>/dev/null
    pkill -f "python.*http.server.*8000" 2>/dev/null
    sleep 2
fi

echo "🚀 正在启动后端服务 (端口5000)..."
python3 backend_server.py > backend.log 2>&1 &
BACKEND_PID=$!
sleep 3

echo "🌐 正在启动前端服务 (端口8000)..."
python3 -m http.server 8000 > frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 2

echo ""
echo "========================================"
echo "✅ 服务启动完成！"
echo "========================================"
echo ""
echo "📱 访问地址:"
echo "   前端网页: http://localhost:8000"
echo "   后端API:  http://localhost:5000"
echo ""
echo "💡 提示:"
echo "   - 服务正在后台运行"
echo "   - 要停止服务请运行: pkill -f 'python.*backend_server.py' && pkill -f 'python.*http.server'"
echo "   - 或查看进程: ps aux | grep python"
echo ""
echo "========================================"

# 保存PID到文件
echo $BACKEND_PID > .backend.pid
echo $FRONTEND_PID > .frontend.pid

# 尝试打开浏览器
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8000 2>/dev/null &
elif command -v open &> /dev/null; then
    open http://localhost:8000 2>/dev/null &
fi


