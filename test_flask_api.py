#!/usr/bin/env python3
import requests
import json

# 测试Flask API
try:
    print("正在测试Flask健康咨询API...")
    
    url = "http://localhost:5000/api/health-consultation"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {
        "question": "我发烧38度伴咳嗽怎么办？",
        "context": []
    }
    
    print(f"请求URL: {url}")
    print(f"请求数据: {json.dumps(data, ensure_ascii=False)}")
    
    resp = requests.post(url, headers=headers, json=data, timeout=30)
    
    print(f"响应状态码: {resp.status_code}")
    print(f"响应头: {dict(resp.headers)}")
    
    if resp.status_code == 200:
        result = resp.json()
        if result.get("success"):
            print("✅ Flask API 测试成功!")
            print(f"AI响应: {result['response'][:100]}...")
        else:
            print(f"❌ API返回错误: {result}")
    else:
        print(f"❌ HTTP错误: {resp.text}")
        
except Exception as e:
    print(f"❌ 测试异常: {e}")
    import traceback
    traceback.print_exc()