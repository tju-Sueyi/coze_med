#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设置用户角色工具
可以将指定用户设置为医生或患者
"""

import json
import os
import sys

# 设置输出编码
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def load_users():
    """加载用户数据"""
    users_file = os.path.join('data', 'users.json')
    if not os.path.exists(users_file):
        print(f"[错误] 用户文件不存在: {users_file}")
        return None
    
    with open(users_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users_data):
    """保存用户数据"""
    users_file = os.path.join('data', 'users.json')
    with open(users_file, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, ensure_ascii=False, indent=2)

def list_users(users_data):
    """列出所有用户及其角色"""
    users = users_data.get('users', {})
    if not users:
        print("[错误] 没有找到任何用户")
        return
    
    print("\n当前所有用户：")
    print("-" * 60)
    for i, (username, user_data) in enumerate(users.items(), 1):
        role = user_data.get('role', 'user')
        role_text = '医生' if role == 'doctor' else '患者'
        print(f"   {i}. [{role_text}] {username}")
    print("-" * 60)

def set_role(username, role):
    """设置用户角色"""
    users_data = load_users()
    if users_data is None:
        return False
    
    users = users_data.get('users', {})
    
    if username not in users:
        print(f"[错误] 用户不存在: {username}")
        print(f"\n可用的用户名：")
        for uname in users.keys():
            print(f"   - {uname}")
        return False
    
    old_role = users[username].get('role', 'user')
    users[username]['role'] = role
    
    save_users(users_data)
    
    role_text = '医生' if role == 'doctor' else '患者'
    old_role_text = '医生' if old_role == 'doctor' else '患者'
    
    print(f"\n[成功] 已更新用户角色！")
    print(f"   用户名: {username}")
    print(f"   旧角色: {old_role_text}")
    print(f"   新角色: {role_text}")
    
    return True

def interactive_mode():
    """交互模式"""
    users_data = load_users()
    if users_data is None:
        return
    
    # 显示所有用户
    list_users(users_data)
    
    print("\n" + "="*60)
    print("设置用户角色")
    print("="*60)
    
    # 输入用户名
    username = input("\n请输入要修改的用户名: ").strip()
    if not username:
        print("[错误] 用户名不能为空")
        return
    
    # 选择角色
    print("\n请选择角色：")
    print("  1. 患者")
    print("  2. 医生")
    
    choice = input("\n请输入选项 (1 或 2): ").strip()
    
    if choice == '1':
        role = 'user'
    elif choice == '2':
        role = 'doctor'
    else:
        print("[错误] 无效的选项")
        return
    
    # 确认
    role_text = '医生' if role == 'doctor' else '患者'
    confirm = input(f"\n确认将 {username} 设置为 {role_text}？(y/n): ").strip().lower()
    
    if confirm in ['y', 'yes', '是', 'Y']:
        set_role(username, role)
    else:
        print("[取消] 操作已取消")

def main():
    """主函数"""
    print("="*60)
    print("用户角色设置工具")
    print("="*60)
    
    if len(sys.argv) >= 3:
        # 命令行模式
        username = sys.argv[1]
        role_arg = sys.argv[2].lower()
        
        if role_arg in ['doctor', '医生', 'doc', 'd']:
            role = 'doctor'
        elif role_arg in ['user', 'patient', '患者', 'u', 'p']:
            role = 'user'
        else:
            print(f"[错误] 无效的角色: {role_arg}")
            print("\n用法:")
            print("  python set_user_role.py <用户名> <角色>")
            print("\n角色可选值:")
            print("  - doctor / 医生 / doc / d")
            print("  - user / patient / 患者 / u / p")
            return
        
        set_role(username, role)
    else:
        # 交互模式
        interactive_mode()
    
    print("\n[提示] 修改角色后无需重启服务，即时生效！")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[取消] 操作已取消")
    except Exception as e:
        print(f"\n[错误] 发生错误: {e}")

