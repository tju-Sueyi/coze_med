#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医疗AI应用启动脚本
同时启动前端和后端服务
"""

import subprocess
import sys
import time
import webbrowser
import threading
import os
from pathlib import Path

def check_requirements():
    """检查依赖项"""
    print("🔍 检查依赖项...")
    
    required_packages = ['flask', 'flask-cors', 'openai']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package} 已安装")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} 未安装")
    
    if missing_packages:
        print(f"\n📦 正在安装缺失的依赖项: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install'
            ] + missing_packages)
            print("✅ 依赖项安装完成")
        except subprocess.CalledProcessError as e:
            print(f"❌ 依赖项安装失败: {e}")
            print("请手动运行: pip install flask flask-cors openai")
            return False
    
    return True

def start_backend():
    """启动后端服务"""
    print("🚀 启动后端AI服务...")
    try:
        # 启动Flask后端服务
        os.system('python backend_server.py')
    except KeyboardInterrupt:
        print("\n🛑 后端服务已停止")
    except Exception as e:
        print(f"❌ 后端服务启动失败: {e}")

def start_frontend():
    """启动前端服务"""
    print("🌐 启动前端服务...")
    try:
        # 启动简单的HTTP服务器
        os.system('python -m http.server 8000')
    except KeyboardInterrupt:
        print("\n🛑 前端服务已停止")
    except Exception as e:
        print(f"❌ 前端服务启动失败: {e}")

def open_browser():
    """打开浏览器"""
    time.sleep(3)  # 等待服务启动
    print("🌐 正在打开浏览器...")
    try:
        webbrowser.open('http://localhost:8000')
        print("✅ 浏览器已打开")
    except Exception as e:
        print(f"❌ 自动打开浏览器失败: {e}")
        print("请手动访问: http://localhost:8000")

def main():
    """主函数"""
    print("=" * 50)
    print("🏥 医疗AI小助手 - 应用启动器")
    print("=" * 50)
    
    # 检查依赖项
    if not check_requirements():
        sys.exit(1)
    
    print("\n📋 服务配置:")
    print("   🤖 后端AI服务: http://localhost:5000")
    print("   🌐 前端网页: http://localhost:8000")
    print("   🔑 AI模型: Qwen-VL-Max")
    
    print("\n⚠️  重要提醒:")
    print("   • 请确保网络连接正常")
    print("   • 后端服务需要调用Qwen API")
    print("   • 首次启动可能需要几秒钟")
    
    input("\n按回车键开始启动服务...")
    
    try:
        # 在不同线程中启动服务
        backend_thread = threading.Thread(target=start_backend, daemon=True)
        frontend_thread = threading.Thread(target=start_frontend, daemon=True)
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        
        print("\n🚀 正在启动服务...")
        
        # 启动后端
        backend_thread.start()
        time.sleep(2)
        
        # 启动前端
        frontend_thread.start()
        
        # 打开浏览器
        browser_thread.start()
        
        print("\n✅ 所有服务已启动!")
        print("\n📱 使用说明:")
        print("   1. 选择角色 (患者/医生/家属)")
        print("   2. 使用症状分析功能")
        print("   3. 与AI医生对话")
        print("   4. 体验用药打卡等功能")
        
        print("\n🔧 开发者工具:")
        print("   • 按 F12 打开开发者工具")
        print("   • 选择移动设备模拟")
        print("   • 推荐使用 iPhone 12 Pro 视图")
        
        print("\n按 Ctrl+C 停止服务")
        
        # 保持主线程运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 正在停止服务...")
        print("👋 谢谢使用医疗AI小助手!")
        
    except Exception as e:
        print(f"\n❌ 服务运行出错: {e}")
        
    finally:
        print("🏁 应用已退出")

if __name__ == "__main__":
    main()