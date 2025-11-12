#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个性化用药管理模块
提供用药记录、提醒、分析等功能
"""

import os
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class MedicationManager:
    """用药管理类"""
    
    def __init__(self, data_dir='data'):
        self.data_dir = data_dir
        self.medications_file = os.path.join(data_dir, 'medications.json')
        self.reminders_file = os.path.join(data_dir, 'medication_reminders.json')
        self.intake_records_file = os.path.join(data_dir, 'medication_intake_records.json')
        self._ensure_files()
    
    def _ensure_files(self):
        """确保数据文件存在"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        if not os.path.exists(self.medications_file):
            with open(self.medications_file, 'w', encoding='utf-8') as f:
                json.dump({'medications': {}}, f, ensure_ascii=False, indent=2)
        
        if not os.path.exists(self.reminders_file):
            with open(self.reminders_file, 'w', encoding='utf-8') as f:
                json.dump({'reminders': {}}, f, ensure_ascii=False, indent=2)
        
        if not os.path.exists(self.intake_records_file):
            with open(self.intake_records_file, 'w', encoding='utf-8') as f:
                json.dump({'records': {}}, f, ensure_ascii=False, indent=2)
    
    def _load_json(self, file_path):
        """加载JSON文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载文件失败 {file_path}: {e}")
            return {}
    
    def _save_json(self, file_path, data):
        """保存JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存文件失败 {file_path}: {e}")
            return False
    
    # ==================== 用药记录管理 ====================
    
    def add_medication(self, username: str, medication_data: Dict) -> Dict:
        """
        添加用药记录
        
        Args:
            username: 用户名
            medication_data: 用药信息
                - name: 药品名称
                - dosage: 剂量（如 "100mg"）
                - frequency: 频率（如 "每日3次"）
                - duration: 疗程（如 "7天"）
                - start_date: 开始日期
                - notes: 备注
                - category: 分类（西药/中药/营养品）
                - prescribing_doctor: 开药医生
                - record_id: 关联的健康档案ID
        
        Returns:
            包含medication_id的结果字典
        """
        try:
            data = self._load_json(self.medications_file)
            if 'medications' not in data:
                data['medications'] = {}
            
            if username not in data['medications']:
                data['medications'][username] = []
            
            medication_id = str(uuid.uuid4())
            medication_record = {
                'id': medication_id,
                'name': medication_data.get('name', ''),
                'dosage': medication_data.get('dosage', ''),
                'frequency': medication_data.get('frequency', ''),
                'duration': medication_data.get('duration', ''),
                'start_date': medication_data.get('start_date', datetime.now().strftime('%Y-%m-%d')),
                'end_date': medication_data.get('end_date', ''),
                'notes': medication_data.get('notes', ''),
                'category': medication_data.get('category', '西药'),
                'prescribing_doctor': medication_data.get('prescribing_doctor', ''),
                'side_effects': medication_data.get('side_effects', ''),
                'record_id': medication_data.get('record_id', ''),  # 健康档案ID
                'status': 'active',  # active, completed, stopped
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            data['medications'][username].append(medication_record)
            
            if self._save_json(self.medications_file, data):
                return {'success': True, 'medication_id': medication_id, 'data': medication_record}
            else:
                return {'success': False, 'error': '保存失败'}
        
        except Exception as e:
            logger.error(f"添加用药记录失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_user_medications(self, username: str, status: Optional[str] = None) -> List[Dict]:
        """
        获取用户的用药记录
        
        Args:
            username: 用户名
            status: 状态筛选（active/completed/stopped）
        
        Returns:
            用药记录列表
        """
        try:
            data = self._load_json(self.medications_file)
            medications = data.get('medications', {}).get(username, [])
            
            if status:
                medications = [m for m in medications if m.get('status') == status]
            
            # 按创建时间倒序排序
            medications.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return medications
        except Exception as e:
            logger.error(f"获取用药记录失败: {e}")
            return []
    
    def update_medication(self, username: str, medication_id: str, update_data: Dict) -> Dict:
        """更新用药记录"""
        try:
            data = self._load_json(self.medications_file)
            
            if username not in data.get('medications', {}):
                return {'success': False, 'error': '用户无用药记录'}
            
            medications = data['medications'][username]
            for i, med in enumerate(medications):
                if med['id'] == medication_id:
                    # 更新字段
                    for key, value in update_data.items():
                        if key != 'id':  # 不允许修改ID
                            med[key] = value
                    
                    med['updated_at'] = datetime.now().isoformat()
                    medications[i] = med
                    
                    if self._save_json(self.medications_file, data):
                        return {'success': True, 'data': med}
                    else:
                        return {'success': False, 'error': '保存失败'}
            
            return {'success': False, 'error': '未找到该用药记录'}
        
        except Exception as e:
            logger.error(f"更新用药记录失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_medication(self, username: str, medication_id: str) -> Dict:
        """删除用药记录"""
        try:
            data = self._load_json(self.medications_file)
            
            if username not in data.get('medications', {}):
                return {'success': False, 'error': '用户无用药记录'}
            
            medications = data['medications'][username]
            original_count = len(medications)
            medications = [m for m in medications if m['id'] != medication_id]
            
            if len(medications) == original_count:
                return {'success': False, 'error': '未找到该用药记录'}
            
            data['medications'][username] = medications
            
            if self._save_json(self.medications_file, data):
                return {'success': True}
            else:
                return {'success': False, 'error': '保存失败'}
        
        except Exception as e:
            logger.error(f"删除用药记录失败: {e}")
            return {'success': False, 'error': str(e)}
    
    # ==================== 服药提醒管理 ====================
    
    def add_reminder(self, username: str, reminder_data: Dict) -> Dict:
        """
        添加服药提醒
        
        Args:
            username: 用户名
            reminder_data: 提醒信息
                - medication_id: 关联的用药ID
                - medication_name: 药品名称
                - times: 提醒时间数组（如 ["08:00", "14:00", "20:00"]）
                - reminder_type: 提醒类型（daily/interval/custom）
                - interval_days: 间隔天数（可选）
                - custom_schedule: 自定义星期列表（可选）
                - enabled: 是否启用
                - record_id: 健康档案ID
        """
        try:
            data = self._load_json(self.reminders_file)
            if 'reminders' not in data:
                data['reminders'] = {}
            
            if username not in data['reminders']:
                data['reminders'][username] = []
            
            reminder_id = str(uuid.uuid4())
            
            # 支持新的times数组格式，兼容旧的time字段
            times = reminder_data.get('times')
            if not times:
                # 兼容旧格式：如果没有times，从time获取
                time_val = reminder_data.get('time', '08:00')
                times = [time_val] if time_val else ['08:00']
            
            reminder = {
                'id': reminder_id,
                'medication_id': reminder_data.get('medication_id', ''),
                'medication_name': reminder_data.get('medication_name', ''),
                'times': times,  # 使用times数组
                'reminder_type': reminder_data.get('reminder_type', 'daily'),  # 新增：提醒类型
                'interval_days': reminder_data.get('interval_days'),  # 新增：间隔天数
                'custom_schedule': reminder_data.get('custom_schedule'),  # 新增：自定义日程
                'enabled': reminder_data.get('enabled', True),
                'record_id': reminder_data.get('record_id', ''),  # 健康档案ID
                'created_at': datetime.now().isoformat(),
                'last_reminded': None
            }
            
            data['reminders'][username].append(reminder)
            
            if self._save_json(self.reminders_file, data):
                return {'success': True, 'reminder_id': reminder_id, 'data': reminder}
            else:
                return {'success': False, 'error': '保存失败'}
        
        except Exception as e:
            logger.error(f"添加提醒失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_user_reminders(self, username: str) -> List[Dict]:
        """获取用户的提醒列表"""
        try:
            data = self._load_json(self.reminders_file)
            return data.get('reminders', {}).get(username, [])
        except Exception as e:
            logger.error(f"获取提醒列表失败: {e}")
            return []
    
    def update_reminder(self, username: str, reminder_id: str, update_data: Dict) -> Dict:
        """更新提醒"""
        try:
            data = self._load_json(self.reminders_file)
            
            if username not in data.get('reminders', {}):
                return {'success': False, 'error': '用户无提醒记录'}
            
            reminders = data['reminders'][username]
            for i, reminder in enumerate(reminders):
                if reminder['id'] == reminder_id:
                    for key, value in update_data.items():
                        if key != 'id':
                            reminder[key] = value
                    
                    reminders[i] = reminder
                    
                    if self._save_json(self.reminders_file, data):
                        return {'success': True, 'data': reminder}
                    else:
                        return {'success': False, 'error': '保存失败'}
            
            return {'success': False, 'error': '未找到该提醒'}
        
        except Exception as e:
            logger.error(f"更新提醒失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_reminder(self, username: str, reminder_id: str) -> Dict:
        """删除提醒"""
        try:
            data = self._load_json(self.reminders_file)
            
            if username not in data.get('reminders', {}):
                return {'success': False, 'error': '用户无提醒记录'}
            
            reminders = data['reminders'][username]
            original_count = len(reminders)
            reminders = [r for r in reminders if r['id'] != reminder_id]
            
            if len(reminders) == original_count:
                return {'success': False, 'error': '未找到该提醒'}
            
            data['reminders'][username] = reminders
            
            if self._save_json(self.reminders_file, data):
                return {'success': True}
            else:
                return {'success': False, 'error': '保存失败'}
        
        except Exception as e:
            logger.error(f"删除提醒失败: {e}")
            return {'success': False, 'error': str(e)}
    
    # ==================== 服药记录管理 ====================
    
    def record_intake(self, username: str, intake_data: Dict) -> Dict:
        """
        记录服药
        
        Args:
            username: 用户名
            intake_data: 服药信息
                - medication_id: 用药ID
                - medication_name: 药品名称
                - taken_at: 服药时间
                - dosage: 服用剂量
                - notes: 备注
                - record_id: 健康档案ID
                - record_name: 健康档案名称
        """
        try:
            data = self._load_json(self.intake_records_file)
            if 'records' not in data:
                data['records'] = {}
            
            if username not in data['records']:
                data['records'][username] = []
            
            record_id = str(uuid.uuid4())
            record = {
                'id': record_id,
                'medication_id': intake_data.get('medication_id', ''),
                'medication_name': intake_data.get('medication_name', ''),
                'taken_at': intake_data.get('taken_at', datetime.now().isoformat()),
                'dosage': intake_data.get('dosage', ''),
                'notes': intake_data.get('notes', ''),
                'record_id': intake_data.get('record_id', ''),  # 健康档案ID
                'record_name': intake_data.get('record_name', ''),  # 健康档案名称
                'created_at': datetime.now().isoformat()
            }
            
            data['records'][username].append(record)
            
            if self._save_json(self.intake_records_file, data):
                return {'success': True, 'record_id': record_id, 'data': record}
            else:
                return {'success': False, 'error': '保存失败'}
        
        except Exception as e:
            logger.error(f"记录服药失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_intake_records(self, username: str, medication_id: Optional[str] = None, 
                          start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """
        获取服药记录
        
        Args:
            username: 用户名
            medication_id: 用药ID（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
        """
        try:
            data = self._load_json(self.intake_records_file)
            records = data.get('records', {}).get(username, [])
            
            # 按用药ID筛选
            if medication_id:
                records = [r for r in records if r.get('medication_id') == medication_id]
            
            # 按日期筛选
            if start_date:
                records = [r for r in records if r.get('taken_at', '') >= start_date]
            if end_date:
                records = [r for r in records if r.get('taken_at', '') <= end_date]
            
            # 按时间倒序排序
            records.sort(key=lambda x: x.get('taken_at', ''), reverse=True)
            
            return records
        except Exception as e:
            logger.error(f"获取服药记录失败: {e}")
            return []
    
    def get_adherence_stats(self, username: str, days: int = 7) -> Dict:
        """
        获取用药依从性统计
        
        Args:
            username: 用户名
            days: 统计天数
        
        Returns:
            统计数据
        """
        try:
            # 获取活跃的用药记录
            medications = self.get_user_medications(username, status='active')
            
            # 获取最近的服药记录
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            intake_records = self.get_intake_records(username, start_date=start_date)
            
            # 计算统计数据
            total_medications = len(medications)
            total_doses_expected = 0
            total_doses_taken = len(intake_records)
            
            # 简单估算：假设每个药物每天3次
            for med in medications:
                freq = med.get('frequency', '')
                if '3' in freq:
                    total_doses_expected += days * 3
                elif '2' in freq:
                    total_doses_expected += days * 2
                else:
                    total_doses_expected += days
            
            adherence_rate = (total_doses_taken / total_doses_expected * 100) if total_doses_expected > 0 else 0
            
            return {
                'success': True,
                'total_medications': total_medications,
                'total_doses_expected': total_doses_expected,
                'total_doses_taken': total_doses_taken,
                'adherence_rate': round(adherence_rate, 2),
                'days': days,
                'period': {
                    'start': start_date,
                    'end': datetime.now().isoformat()
                }
            }
        
        except Exception as e:
            logger.error(f"获取依从性统计失败: {e}")
            return {'success': False, 'error': str(e)}

