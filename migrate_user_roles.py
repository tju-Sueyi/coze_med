#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户角色数据迁移脚本
为所有旧账号添加 role 字段
"""

import json
import os
import sys

# 设置输出编码
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def migrate_user_roles():
    """为所有用户添加 role 字段"""
    users_file = os.path.join('data', 'users.json')
    
    if not os.path.exists(users_file):
        print(f"[错误] 用户文件不存在: {users_file}")
        return
    
    # 读取用户数据
    with open(users_file, 'r', encoding='utf-8') as f:
        users_data = json.load(f)
    
    users = users_data.get('users', {})
    updated_count = 0
    
    # 为每个用户添加 role 字段（如果不存在）
    for username, user_data in users.items():
        if 'role' not in user_data:
            user_data['role'] = 'user'  # 默认为患者
            updated_count += 1
            print(f"[+] 更新用户 {username}: role = user (患者)")
        else:
            role_text = '医生' if user_data['role'] == 'doctor' else '患者'
            print(f"[-] 跳过用户 {username}: 已有角色 {user_data['role']} ({role_text})")
    
    # 保存更新后的数据
    users_data['users'] = users
    with open(users_file, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n" + "="*60)
    print(f"迁移完成！")
    print(f"   - 总用户数: {len(users)}")
    print(f"   - 已更新: {updated_count}")
    print(f"   - 已跳过: {len(users) - updated_count}")
    print("="*60)
    
    # 显示所有用户的角色
    print("\n当前所有用户角色：")
    print("-" * 60)
    for username, user_data in users.items():
        role = user_data.get('role', 'unknown')
        role_text = '医生' if role == 'doctor' else '患者'
        print(f"   [{role_text}] {username}")
    print("-" * 60)

if __name__ == '__main__':
    print("="*60)
    print("开始迁移用户角色数据...")
    print("="*60)
    migrate_user_roles()
    print("\n提示：如需将某个用户改为医生角色，请使用 set_user_role.py")

