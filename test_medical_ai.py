#!/usr/bin/env python3
import sys
import os
sys.path.append('.')

# 导入后端的MedicalAI类
from backend_server import MedicalAIService

# 测试MedicalAI
try:
    print("正在测试MedicalAI服务...")
    ai = MedicalAIService()
    
    # 测试健康咨询
    print("测试健康咨询...")
    result = ai.health_consultation("我发烧38度伴咳嗽怎么办？")
    print(f"结果: {result}")
    
    if result.get("success"):
        print("✅ MedicalAI 测试成功!")
        print(f"响应: {result['response'][:100]}...")
    else:
        print(f"❌ MedicalAI 测试失败: {result.get('message', 'Unknown error')}")
        if 'error_detail' in result:
            print(f"详细错误: {result['error_detail']}")
        
except Exception as e:
    print(f"❌ 测试异常: {e}")
    import traceback
    traceback.print_exc()