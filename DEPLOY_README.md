# 医疗AI平台 - 快速部署说明

## 🚀 一键部署（推荐）

### Windows系统

1. **运行部署脚本**
   ```
   双击运行: deploy.bat
   ```
   
2. **启动服务**
   ```
   双击运行: start.bat
   ```

3. **访问应用**
   - 浏览器会自动打开
   - 或手动访问: http://localhost:8000

### Linux/Mac系统

1. **赋予执行权限**
   ```bash
   chmod +x deploy.sh start.sh
   ```

2. **运行部署脚本**
   ```bash
   ./deploy.sh
   ```

3. **启动服务**
   ```bash
   ./start.sh
   ```

4. **访问应用**
   - 打开浏览器访问: http://localhost:8000

## ⚙️ 必需配置

### 1. Qwen API密钥

**方式1: 环境变量（推荐）**
```bash
# Windows
set DASHSCOPE_API_KEY=sk-your-key-here

# Linux/Mac
export DASHSCOPE_API_KEY=sk-your-key-here
```

**方式2: 修改代码**
- 编辑 `backend_server.py` 第239行
- 替换默认的API密钥

### 2. 百度地图API密钥

- 编辑 `index.html`
- 找到百度地图API脚本标签
- 替换 `ak=您的百度地图API密钥` 为实际密钥

## ✅ 环境检查

部署前建议运行环境检查：
```bash
python check_environment.py
```

## 📋 前置要求

- Python 3.7 或更高版本
- pip 包管理器
- 网络连接（用于API调用）

## 📚 详细文档

更多信息请查看: `部署指南.md`

## ❓ 遇到问题？

1. 运行环境检查脚本
2. 查看日志文件（backend.log）
3. 检查浏览器控制台错误（F12）
4. 参考部署指南中的常见问题部分


