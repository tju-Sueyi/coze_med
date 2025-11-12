#!/usr/bin/env python3
import requests
import json

# 测试Qwen API
try:
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Authorization": "Bearer sk-8e5ea74e20a54f88a4f1d2d0d82cd71c",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": "你好"}],
        "temperature": 0.3,
        "max_tokens": 100
    }
    
    print("正在测试Qwen API...")
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"响应: {data['choices'][0]['message']['content']}")
        print("✅ Qwen API 测试成功!")
    else:
        print(f"❌ API错误: {resp.text}")
        
except Exception as e:
    print(f"❌ 测试失败: {e}")