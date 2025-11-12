#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用药管理功能测试脚本
测试后端API和数据管理功能
"""

import requests
import json
from datetime import datetime

API_BASE = 'http://localhost:5000/api'
TEST_USER = 'testuser'

def print_separator(title):
    """打印分隔线"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_add_medication():
    """测试添加用药记录"""
    print_separator("测试1：添加用药记录")
    
    medication = {
        "name": "阿莫西林胶囊",
        "dosage": "500mg",
        "frequency": "每日3次",
        "duration": "7天",
        "start_date": datetime.now().strftime('%Y-%m-%d'),
        "category": "西药",
        "prescribing_doctor": "张医生",
        "notes": "饭后服用，多喝水"
    }
    
    response = requests.post(
        f"{API_BASE}/medications",
        json={"username": TEST_USER, "medication": medication}
    )
    
    data = response.json()
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
    
    if data.get('success'):
        print("✅ 添加成功！")
        return data.get('medication_id')
    else:
        print("❌ 添加失败！")
        return None

def test_get_medications():
    """测试获取用药列表"""
    print_separator("测试2：获取用药列表")
    
    response = requests.get(f"{API_BASE}/medications?username={TEST_USER}")
    data = response.json()
    
    print(f"状态码: {response.status_code}")
    print(f"用药数量: {data.get('count', 0)}")
    
    if data.get('success') and data.get('medications'):
        print(f"前3条用药记录:")
        for i, med in enumerate(data['medications'][:3], 1):
            print(f"\n{i}. {med['name']}")
            print(f"   剂量: {med.get('dosage', '未设置')}")
            print(f"   频率: {med.get('frequency', '未设置')}")
            print(f"   状态: {med.get('status', '未知')}")
        print("✅ 获取成功！")
        return data['medications']
    else:
        print("❌ 获取失败或无数据！")
        return []

def test_add_reminder(medication_id):
    """测试添加服药提醒"""
    print_separator("测试3：添加服药提醒")
    
    if not medication_id:
        print("⚠️  需要先添加用药记录")
        return None
    
    reminder = {
        "medication_id": medication_id,
        "medication_name": "阿莫西林胶囊",
        "time": "08:00",
        "days": ["每天"],
        "enabled": True
    }
    
    response = requests.post(
        f"{API_BASE}/medications/reminders",
        json={"username": TEST_USER, "reminder": reminder}
    )
    
    data = response.json()
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
    
    if data.get('success'):
        print("✅ 提醒添加成功！")
        return data.get('reminder_id')
    else:
        print("❌ 提醒添加失败！")
        return None

def test_record_intake(medication_id):
    """测试记录服药"""
    print_separator("测试4：记录服药")
    
    if not medication_id:
        print("⚠️  需要先添加用药记录")
        return
    
    intake = {
        "medication_id": medication_id,
        "medication_name": "阿莫西林胶囊",
        "taken_at": datetime.now().isoformat(),
        "dosage": "500mg",
        "notes": "按时服用"
    }
    
    response = requests.post(
        f"{API_BASE}/medications/intake-records",
        json={"username": TEST_USER, "intake": intake}
    )
    
    data = response.json()
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
    
    if data.get('success'):
        print("✅ 服药记录成功！")
    else:
        print("❌ 服药记录失败！")

def test_adherence_stats():
    """测试用药统计"""
    print_separator("测试5：用药依从性统计")
    
    response = requests.get(f"{API_BASE}/medications/adherence-stats?username={TEST_USER}&days=7")
    data = response.json()
    
    print(f"状态码: {response.status_code}")
    
    if data.get('success'):
        print(f"\n📊 统计数据（近7天）:")
        print(f"  用药种类: {data.get('total_medications', 0)} 种")
        print(f"  应服次数: {data.get('total_doses_expected', 0)} 次")
        print(f"  已服次数: {data.get('total_doses_taken', 0)} 次")
        print(f"  依从性: {data.get('adherence_rate', 0)}%")
        print("✅ 统计成功！")
    else:
        print("❌ 统计失败！")

def test_ai_analyze():
    """测试AI分析"""
    print_separator("测试6：AI智能分析")
    
    # 先添加多个用药记录用于测试
    medications_to_add = [
        {
            "name": "阿司匹林",
            "dosage": "100mg",
            "frequency": "每日1次",
            "category": "西药"
        },
        {
            "name": "氯吡格雷",
            "dosage": "75mg",
            "frequency": "每日1次",
            "category": "西药"
        }
    ]
    
    print("添加测试用药记录...")
    for med in medications_to_add:
        requests.post(
            f"{API_BASE}/medications",
            json={"username": TEST_USER, "medication": med}
        )
    
    print("\n开始AI分析...")
    response = requests.post(
        f"{API_BASE}/medications/ai-analyze",
        json={"username": TEST_USER}
    )
    
    data = response.json()
    print(f"状态码: {response.status_code}")
    
    if data.get('success'):
        analysis = data.get('analysis', {})
        print(f"\n🤖 AI分析结果:")
        print(f"\n总体评估:")
        print(f"  {analysis.get('summary', '暂无')}")
        
        interactions = analysis.get('interactions', [])
        if interactions:
            print(f"\n⚠️  药物相互作用 ({len(interactions)}项):")
            for i, inter in enumerate(interactions[:2], 1):
                print(f"  {i}. {inter.get('drug1', '')} ↔️ {inter.get('drug2', '')}")
                print(f"     严重程度: {inter.get('severity', '未知')}")
                print(f"     说明: {inter.get('description', '')[:50]}...")
        
        warnings = analysis.get('warnings', [])
        if warnings:
            print(f"\n🚨 安全警告 ({len(warnings)}项):")
            for i, warn in enumerate(warnings[:2], 1):
                print(f"  {i}. {warn.get('type', '警告')}")
                print(f"     说明: {warn.get('description', '')[:50]}...")
        
        suggestions = analysis.get('suggestions', [])
        if suggestions:
            print(f"\n💡 用药建议 ({len(suggestions)}项):")
            for i, sug in enumerate(suggestions[:2], 1):
                text = sug if isinstance(sug, str) else sug.get('description', sug.get('text', ''))
                print(f"  {i}. {text[:60]}...")
        
        print("\n✅ AI分析完成！")
    else:
        print(f"❌ AI分析失败: {data.get('message', '未知错误')}")

def main():
    """主测试函数"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*15 + "用药管理功能测试" + " "*15 + "║")
    print("╚" + "="*58 + "╝")
    print(f"\n测试用户: {TEST_USER}")
    print(f"API地址: {API_BASE}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 测试1：添加用药
        medication_id = test_add_medication()
        
        # 测试2：获取用药列表
        medications = test_get_medications()
        if not medication_id and medications:
            medication_id = medications[0]['id']
        
        # 测试3：添加提醒
        test_add_reminder(medication_id)
        
        # 测试4：记录服药
        test_record_intake(medication_id)
        
        # 测试5：统计
        test_adherence_stats()
        
        # 测试6：AI分析
        test_ai_analyze()
        
        # 总结
        print_separator("测试完成")
        print("✅ 所有测试已完成！")
        print("\n建议:")
        print("1. 在浏览器中访问 http://localhost:5000/medication.html")
        print("2. 使用测试用户登录并体验完整功能")
        print("3. 查看数据文件: data/medications.json")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ 错误: 无法连接到服务器")
        print("请确保后端服务已启动:")
        print("  python backend_server.py")
    except Exception as e:
        print(f"\n❌ 测试出错: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

