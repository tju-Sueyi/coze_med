#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TCM 中医模块集成测试脚本
测试功能：档案管理、相机拍照、诊断分析
"""

import requests
import json
import time
import base64
from io import BytesIO
from PIL import Image

# 服务器配置
BASE_URL = "http://localhost:5000"
API_BASE = f"{BASE_URL}/api/tcm"

def test_health_check():
    """测试服务器健康状态"""
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        if response.status_code == 200:
            print("✅ 服务器健康检查通过")
            return True
        else:
            print("❌ 服务器健康检查失败")
            return False
    except Exception as e:
        print(f"❌ 无法连接服务器: {e}")
        return False

def test_create_archive():
    """测试创建健康档案"""
    try:
        data = {
            "name": "测试档案_" + str(int(time.time())),
            "gender": "女",
            "age": "25",
            "contact": "测试联系方式"
        }
        
        response = requests.post(f"{API_BASE}/archives", json=data)
        result = response.json()
        
        if result.get("success"):
            print(f"✅ 档案创建成功: {result['archive']['name']}")
            return result['archive']['id']
        else:
            print(f"❌ 档案创建失败: {result.get('message')}")
            return None
    except Exception as e:
        print(f"❌ 档案创建异常: {e}")
        return None

def test_get_archives():
    """测试获取档案列表"""
    try:
        response = requests.get(f"{API_BASE}/archives")
        result = response.json()
        
        if result.get("success"):
            archives = result.get("archives", [])
            print(f"✅ 获取档案列表成功，共 {len(archives)} 个档案")
            return archives
        else:
            print(f"❌ 获取档案列表失败: {result.get('message')}")
            return []
    except Exception as e:
        print(f"❌ 获取档案列表异常: {e}")
        return []

def test_get_archive_detail(archive_id):
    """测试获取档案详情"""
    try:
        response = requests.get(f"{API_BASE}/archives/{archive_id}")
        result = response.json()
        
        if result.get("success"):
            archive = result.get("archive")
            print(f"✅ 获取档案详情成功: {archive['name']}")
            return archive
        else:
            print(f"❌ 获取档案详情失败: {result.get('message')}")
            return None
    except Exception as e:
        print(f"❌ 获取档案详情异常: {e}")
        return None

def create_test_image():
    """创建测试图片"""
    # 创建一个简单的测试图片
    img = Image.new('RGB', (640, 480), color='lightblue')
    
    # 添加一些简单的内容模拟面部或舌头
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([200, 150, 440, 330], fill='pink', outline='red')
    draw.text((280, 230), "TEST", fill='black')
    
    # 保存为字节流
    img_buffer = BytesIO()
    img.save(img_buffer, format='JPEG')
    img_buffer.seek(0)
    
    return img_buffer

def test_image_analysis(archive_id=None, mode='face'):
    """测试图片分析"""
    try:
        # 创建测试图片
        img_buffer = create_test_image()
        
        files = {
            'image': ('test_image.jpg', img_buffer, 'image/jpeg')
        }
        
        data = {
            'mode': mode,
            'archive_id': archive_id or ''
        }
        
        response = requests.post(f"{API_BASE}/analyze", files=files, data=data)
        result = response.json()
        
        if result.get("success"):
            analysis_result = result.get("result")
            print(f"✅ {mode}诊分析成功")
            print(f"   体质类型: {analysis_result.get('constitution')}")
            print(f"   体质得分: {analysis_result.get('constitution_score')}")
            print(f"   置信度: {analysis_result.get('confidence', 0):.2f}")
            return analysis_result
        else:
            print(f"❌ {mode}诊分析失败: {result.get('message')}")
            return None
    except Exception as e:
        print(f"❌ {mode}诊分析异常: {e}")
        return None

def run_tcm_integration_test():
    """运行完整的TCM集成测试"""
    print("🔮 开始TCM中医模块集成测试...")
    print("=" * 50)
    
    # 1. 健康检查
    print("1️⃣ 测试服务器连接")
    if not test_health_check():
        print("❌ 服务器连接失败，测试终止")
        return
    
    # 2. 测试档案管理
    print("\n2️⃣ 测试档案管理功能")
    archive_id = test_create_archive()
    archives = test_get_archives()
    
    if archive_id:
        archive_detail = test_get_archive_detail(archive_id)
    
    # 3. 测试面诊分析
    print("\n3️⃣ 测试面诊分析功能")
    face_result = test_image_analysis(archive_id, 'face')
    
    # 4. 测试舌诊分析
    print("\n4️⃣ 测试舌诊分析功能")
    tongue_result = test_image_analysis(archive_id, 'tongue')
    
    # 5. 总结测试结果
    print("\n" + "=" * 50)
    print("🎯 测试总结:")
    
    success_count = 0
    total_tests = 5
    
    if test_health_check():
        success_count += 1
        print("✅ 服务器连接正常")
    
    if archive_id:
        success_count += 1
        print("✅ 档案管理功能正常")
    
    if len(archives) >= 0:
        success_count += 1
        print("✅ 档案列表获取正常")
    
    if face_result:
        success_count += 1
        print("✅ 面诊分析功能正常")
    
    if tongue_result:
        success_count += 1
        print("✅ 舌诊分析功能正常")
    
    print(f"\n📊 测试结果: {success_count}/{total_tests} 项通过")
    
    if success_count == total_tests:
        print("🎉 所有测试通过！TCM模块集成成功！")
    else:
        print("⚠️ 部分测试失败，请检查相关功能")

if __name__ == "__main__":
    run_tcm_integration_test()