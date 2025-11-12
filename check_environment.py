#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境检查脚本
检查部署环境是否满足要求
"""

import sys
import os
import subprocess
import platform

def print_header(text):
    """打印标题"""
    print("\n" + "=" * 50)
    print(f"  {text}")
    print("=" * 50)

def check_python_version():
    """检查Python版本"""
    print_header("检查Python环境")
    version = sys.version_info
    print(f"Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print("❌ Python版本过低，需要Python 3.7或更高版本")
        return False
    else:
        print("✅ Python版本符合要求")
        return True

def check_pip():
    """检查pip工具"""
    print_header("检查pip工具")
    try:
        import pip
        pip_version = pip.__version__
        print(f"pip版本: {pip_version}")
        print("✅ pip工具可用")
        return True
    except ImportError:
        print("❌ pip未安装")
        return False

def check_packages():
    """检查必需的Python包"""
    print_header("检查Python依赖包")
    required_packages = {
        'flask': 'Flask',
        'flask_cors': 'flask-cors',
        'openai': 'openai',
    }
    
    missing_packages = []
    installed_packages = []
    
    for module_name, package_name in required_packages.items():
        try:
            __import__(module_name)
            print(f"✅ {package_name} 已安装")
            installed_packages.append(package_name)
        except ImportError:
            print(f"❌ {package_name} 未安装")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\n⚠️  缺失的包: {', '.join(missing_packages)}")
        print(f"安装命令: pip install {' '.join(missing_packages)}")
        return False
    else:
        print("\n✅ 所有必需的包已安装")
        return True

def check_directories():
    """检查必要的目录"""
    print_header("检查目录结构")
    required_dirs = [
        'data',
        'data/uploads',
    ]
    
    missing_dirs = []
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"✅ {dir_path} 存在")
        else:
            print(f"⚠️  {dir_path} 不存在（将自动创建）")
            missing_dirs.append(dir_path)
    
    return True

def check_data_files():
    """检查数据文件"""
    print_header("检查数据文件")
    data_files = [
        'data/users.json',
        'data/records.json',
        'data/community.json',
        'data/pre_consultation_pushes.json',
        'data/medications.json',
        'data/medication_intake_records.json',
        'data/medication_reminders.json',
        'data/tcm_archives.json',
    ]
    
    missing_files = []
    for file_path in data_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} 存在")
        else:
            print(f"⚠️  {file_path} 不存在（将自动创建）")
            missing_files.append(file_path)
    
    return True

def check_ports():
    """检查端口占用"""
    print_header("检查端口占用")
    ports = [5000, 8000]
    system = platform.system()
    
    for port in ports:
        try:
            if system == 'Windows':
                result = subprocess.run(
                    ['netstat', '-ano'],
                    capture_output=True,
                    text=True
                )
                if f':{port}' in result.stdout:
                    print(f"⚠️  端口 {port} 已被占用")
                else:
                    print(f"✅ 端口 {port} 可用")
            else:
                result = subprocess.run(
                    ['lsof', '-i', f':{port}'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print(f"⚠️  端口 {port} 已被占用")
                else:
                    print(f"✅ 端口 {port} 可用")
        except Exception as e:
            print(f"⚠️  无法检查端口 {port}: {e}")
    
    return True

def check_config():
    """检查配置文件"""
    print_header("检查配置文件")
    
    # 检查backend_server.py
    if os.path.exists('backend_server.py'):
        print("✅ backend_server.py 存在")
        with open('backend_server.py', 'r', encoding='utf-8') as f:
            content = f.read()
            if 'DASHSCOPE_API_KEY' in content:
                print("✅ API密钥配置项已找到")
            else:
                print("⚠️  未找到API密钥配置项")
    else:
        print("❌ backend_server.py 不存在")
        return False
    
    # 检查index.html
    if os.path.exists('index.html'):
        print("✅ index.html 存在")
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()
            if 'api.map.baidu.com' in content:
                print("⚠️  请检查百度地图API密钥配置")
            else:
                print("⚠️  未找到百度地图API配置")
    else:
        print("❌ index.html 不存在")
        return False
    
    return True

def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("  🏥 医疗AI平台 - 环境检查工具")
    print("=" * 50)
    
    results = []
    
    # 执行各项检查
    results.append(("Python版本", check_python_version()))
    results.append(("pip工具", check_pip()))
    results.append(("Python包", check_packages()))
    results.append(("目录结构", check_directories()))
    results.append(("数据文件", check_data_files()))
    results.append(("端口占用", check_ports()))
    results.append(("配置文件", check_config()))
    
    # 汇总结果
    print_header("检查结果汇总")
    failed = False
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
        if not result:
            failed = True
    
    if failed:
        print("\n⚠️  部分检查项目未通过，请根据上述提示进行修复")
        print("建议运行部署脚本: deploy.bat (Windows) 或 deploy.sh (Linux/Mac)")
        return 1
    else:
        print("\n✅ 环境检查全部通过，可以正常部署和运行！")
        return 0

if __name__ == "__main__":
    sys.exit(main())


