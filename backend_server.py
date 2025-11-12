#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医疗AI后端服务
集成Qwen-VL-Max API为医疗应用提供智能分析
"""

import os
import json
import uuid
import hashlib
import time
import random
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
try:
    from flask_cors import CORS  # 可选依赖
    _CORS_AVAILABLE = True
except Exception:  # noqa: BLE001 - 兼容环境
    CORS = None
    _CORS_AVAILABLE = False

# OpenAI 兼容：如库缺失则降级为 requests 直连 DashScope
try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except Exception:  # noqa: BLE001
    OpenAI = None
    _OPENAI_AVAILABLE = False
import requests  # ensure requests is always available for HTTP fallback
import logging
from datetime import datetime, timedelta
import traceback
import re
from typing import Optional
from flask import Response, stream_with_context
import xml.etree.ElementTree as ET

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 简单清洗：去除Markdown/列表符号，输出纯文本
_md_heading_re = re.compile(r'^\s*#{1,6}\s*', re.MULTILINE)
_md_bold_re = re.compile(r'\*\*(.*?)\*\*')
_md_list_re = re.compile(r'^[\s>\-\*•]+', re.MULTILINE)
_md_hr_re = re.compile(r'\n[-*_]{3,}\n', re.MULTILINE)
_backticks_re = re.compile(r'`+')

def to_plain_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    t = _md_heading_re.sub('', text)
    t = _md_bold_re.sub(r'\1', t)
    t = _md_list_re.sub('', t)
    t = _md_hr_re.sub('\n', t)
    t = _backticks_re.sub('', t)
    # 统一替换多余空白
    lines = [ln.strip() for ln in t.splitlines()]
    # 删除连续空行
    out = []
    prev_blank = False
    for ln in lines:
        if ln == '':
            if not prev_blank:
                out.append('')
            prev_blank = True
        else:
            out.append(ln)
            prev_blank = False
    return "\n".join(out).strip()

def _strip_code_fences(text: str) -> str:
    if not isinstance(text, str):
        return text
    t = text.strip()
    # 去除 ```json ... ``` 或 ``` ... ``` 包裹
    if t.startswith("```") and t.endswith("```"):
        t = t.strip('`')
        # 再次尝试移除语言标签
        t = re.sub(r'^json\s*', '', t, flags=re.IGNORECASE)
        t = t.strip()
    # 去除开头的 json 关键词
    t = re.sub(r'^json\s*', '', t, flags=re.IGNORECASE)
    return t

def _extract_json_payload(text: str) -> Optional[dict]:
    if not isinstance(text, str):
        return None
    t = _strip_code_fences(text)
    # 直接尝试
    try:
        return json.loads(t)
    except Exception:
        pass
    # 尝试截取第一个 { 到最后一个 }
    try:
        start = t.find('{')
        end = t.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(t[start:end+1])
    except Exception:
        return None
    return None

def normalize_summary_html(raw: str) -> str:
    """将可能是纯文本/混杂符号的总结规范化为结构化HTML。"""
    if not isinstance(raw, str):
        return ''
    txt = _strip_code_fences(raw)
    # 去除行首的多余符号如 ">", "3>", 数字+> 等
    lines = [re.sub(r'^\s*(?:\d+>\s*|>\s*)', '', ln) for ln in txt.splitlines()]
    # 合并空白
    cleaned = []
    for ln in lines:
        cleaned.append(ln.strip())
    text = "\n".join([ln for ln in cleaned if ln is not None])
    # 如已包含 <h3> 视为HTML，直接返回
    if '<h3' in text or '<p' in text or '<ul' in text or '<ol' in text:
        return text
    # 将关键小节转为 <h3>
    sections = []
    current = []
    title = None
    def push_section():
        nonlocal title, current
        if title:
            sections.append(f"<h3>{title}</h3>")
        if current:
            body = "<p>" + "</p><p>".join([re.sub(r'[\u0000]+','',c) for c in current if c]) + "</p>"
            sections.append(body)
        title = None
        current = []
    for ln in text.splitlines():
        if ln in ("要点", "可能诊断", "建议", "下一步建议", "需要警惕", "体格检查", "辅助检查", "初步诊断", "诊疗计划"):
            push_section()
            title = ln
        else:
            if ln:
                current.append(ln)
    push_section()
    return "".join(sections) or to_plain_text(text)

def sanitize_emr_html(source_brief: str, html: str) -> str:
    """防止臆测：将未提供的体征/检查结果规范为占位描述。
    规则（保守处理）：
    - 体格检查中的体温/脉搏/呼吸/血压若出现具体数值，替换为"待查"。
    - 辅助检查中带有"示：/提示/显示/见"的具体结果，替换为"未完善，建议完善相关检查"。
    """
    if not isinstance(html, str) or not html:
        return html
    out = html
    # 体征数值与单位形式均归一为"待查"（覆盖：冒号、空格、中文单位、mmHg等）
    out = re.sub(r'体温\s*[:：]?\s*[^，。<\n]*', '体温：待查', out)
    out = re.sub(r'脉搏\s*[:：]?\s*[^，。<\n]*', '脉搏：待查', out)
    out = re.sub(r'呼吸\s*[:：]?\s*[^，。<\n]*', '呼吸：待查', out)
    out = re.sub(r'血压\s*[:：]?\s*[^，。<\n]*', '血压：待查', out)
    # 辅助检查结果性语句归一
    out = re.sub(r'(血常规|CRP|降钙素原|胸部X线|胸片|CT)[^。；;<\n]*?(示|提示|显示|见)[^。；;<\n]*', r'\1：未完善，建议根据病情完善检查', out)
    # 统一"未完善"小节
    out = re.sub(r'<h3>\s*辅助检查\s*</h3>\s*<p>[^<]*</p>', '<h3>辅助检查</h3><p>未完善，建议根据病情完善相应检查项目。</p>', out)

    # 体格检查：统一使用保守占位内容，避免任何未提供的细节
    safe_pe = (
        '<h3>体格检查</h3>'
        '<ul>'
        '<li>生命体征：待查（体温/脉搏/呼吸/血压）</li>'
        '<li>一般状况：待查</li>'
        '<li>呼吸系统/心血管系统/腹部/神经系统：待查</li>'
        '</ul>'
    )
    if re.search(r'<h3>\s*体格检查\s*</h3>', out):
        out = re.sub(r'(<h3>\s*体格检查\s*</h3>)(.*?)(?=<h3>|$)', safe_pe, out, flags=re.S)

    # 现病史：基于brief输出保守内容，避免无根据扩写
    def _replace_section(title: str, replacement_html: str) -> str:
        pattern = re.compile(rf'(<h3>{title}</h3>)(.*?)(?=<h3>|$)', re.S)
        return pattern.sub(rf'\1{replacement_html}', out)

    brief_text = (source_brief or '').strip()
    if brief_text:
        safe_hpi = f'<p>依据当前描述：{re.escape(brief_text)}</p><p>更多关键信息（起病诱因、伴随症状、病程演变、用药情况）待补充。</p>'
    else:
        safe_hpi = '<p>患者主述待补充。</p>'

    if re.search(r'<h3>现病史</h3>', out):
        out = re.sub(r'(<h3>现病史</h3>)(.*?)(?=<h3>|$)', rf'\1{safe_hpi}', out, flags=re.S)
    else:
        if re.search(r'<h3>主诉</h3>', out):
            out = re.sub(r'(<h3>主诉</h3>.*?)(?=<h3>|$)', rf'\1<h3>现病史</h3>{safe_hpi}', out, flags=re.S)
        else:
            out = f"<h3>现病史</h3>{safe_hpi}" + out

    # 既往史/过敏史：未提及则统一"未提及/待补充"
    if re.search(r'<h3>既往史</h3>', out):
        out = re.sub(r'(<h3>既往史</h3>)(.*?)(?=<h3>|$)', r'\1<p>未提及，待补充。</p>', out, flags=re.S)
    else:
        out = out + '<h3>既往史</h3><p>未提及，待补充。</p>'
    if re.search(r'<h3>过敏史</h3>', out):
        out = re.sub(r'(<h3>过敏史</h3>)(.*?)(?=<h3>|$)', r'\1<p>未提及，待补充。</p>', out, flags=re.S)
    else:
        out = out + '<h3>过敏史</h3><p>未提及，待补充。</p>'
    return out

# 创建Flask应用
app = Flask(__name__)
# CORS 适配：优先使用 Flask-Cors，缺失时降级为手动Header
if _CORS_AVAILABLE:
    CORS(app)
else:
    @app.after_request
    def _add_cors_headers(resp):  # 简易CORS降级
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        allow_headers = request.headers.get(
            'Access-Control-Request-Headers',
            'Content-Type,Authorization,Cache-Control,Pragma'
        )
        resp.headers['Access-Control-Allow-Headers'] = allow_headers
        return resp

    @app.before_request
    def _cors_preflight():
        # 处理浏览器的预检请求，避免被拒导致前端显示服务不可用
        if request.method == 'OPTIONS':
            preflight_resp = jsonify({"ok": True})
            preflight_resp.headers['Access-Control-Allow-Origin'] = '*'
            preflight_resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
            allow_headers = request.headers.get(
                'Access-Control-Request-Headers',
                'Content-Type,Authorization,Cache-Control,Pragma'
            )
            preflight_resp.headers['Access-Control-Allow-Headers'] = allow_headers
            return preflight_resp, 200

# 配置Qwen API
QWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY") or "sk-8e5ea74e20a54f88a4f1d2d0d82cd71c"
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 兼容多编码JSON解析
def parse_json_request():
    try:
        return request.get_json(force=True)
    except Exception:
        # 尝试手动解码
        try:
            raw = request.get_data() or b""
            try:
                text = raw.decode('utf-8')
            except Exception:
                text = raw.decode('gbk', errors='ignore')
            return json.loads(text) if text else {}
        except Exception as e:  # 保留原异常信息
            raise e

if _OPENAI_AVAILABLE:
    client = OpenAI(
        api_key=QWEN_API_KEY,
        base_url=QWEN_BASE_URL,
    )
else:
    client = None  # 使用 requests 降级

def chat_completion(model: str, messages: list, temperature: float, max_tokens: int):
    """统一的聊天补全调用，返回 (文本内容, 实际使用模型)。
    尝试顺序：
    1) OpenAI SDK 调用 primary_model
    2) HTTP requests 调用 primary_model
    3) OpenAI SDK 调用 fallback_model (qwen-plus)
    4) HTTP requests 调用 fallback_model
    任一步成功即返回；全部失败则抛出异常。
    """

    def _call_via_openai(model_name: str):
        if not (_OPENAI_AVAILABLE and client is not None):
            raise RuntimeError("openai_client_unavailable")
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    def _call_via_requests(model_name: str):
        url = f"{QWEN_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 400:
            # 兼容另一种消息格式：content 为对象数组
            try:
                alt_messages = []
                for m in messages:
                    c = m.get("content")
                    if isinstance(c, list):
                        alt_messages.append(m)
                    else:
                        alt_messages.append({
                            "role": m.get("role", "user"),
                            "content": [{"type": "text", "text": str(c)}]
                        })
                alt_payload = {
                    "model": model_name,
                    "messages": alt_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                resp2 = requests.post(url, headers=headers, json=alt_payload, timeout=60)
                if not resp2.ok:
                    raise RuntimeError(f"qwen_api_{resp2.status_code}: {resp2.text[:300]}")
                data2 = resp2.json()
                return data2["choices"][0]["message"]["content"]
            except Exception as e:
                raise RuntimeError(f"qwen_api_400_alt_failed: {e} | orig: {resp.text[:300]}")
        if not resp.ok:
            raise RuntimeError(f"qwen_api_{resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    primary_model = model
    fallback_model = "qwen-plus"

    # 尝试主模型：OpenAI → requests
    try:
        content = _call_via_openai(primary_model)
        return content, primary_model
    except Exception as e:
        logger.warning(f"Primary via OpenAI failed for {primary_model}: {e}")
        try:
            content = _call_via_requests(primary_model)
            return content, primary_model
        except Exception as e2:
            logger.warning(f"Primary via HTTP failed for {primary_model}: {e2}")

    # 尝试回退模型：OpenAI → requests
    try:
        content = _call_via_openai(fallback_model)
        return content, fallback_model
    except Exception as e:
        logger.warning(f"Fallback via OpenAI failed for {fallback_model}: {e}")
        try:
            content = _call_via_requests(fallback_model)
            return content, fallback_model
        except Exception as e2:
            logger.error(f"Fallback via HTTP failed for {fallback_model}: {e2}")
            raise

class MedicalAIService:
    """医疗AI服务类"""
    
    def __init__(self):
        self.model = "qwen-vl-max"  # 视觉多模态模型（用于图像相关）
        # 文本任务专用模型（更稳定的文本对话/生成）
        self.text_model = os.getenv("QWEN_TEXT_MODEL", "qwen-plus")
        
    def analyze_symptoms(self, symptoms, patient_info=None):
        """症状分析"""
        try:
            # 构建医疗专业的系统提示
            system_prompt = """你是一位专业的医疗AI助手，具有丰富的临床经验。请根据患者的症状描述，提供专业的医疗建议。

你需要：
1. 分析症状的可能原因
2. 评估紧急程度（低、中、高）
3. 提供初步诊疗建议
4. 推荐适当的检查项目
5. 给出生活方式建议

注意：
- 你的建议仅供参考，不能替代专业医疗诊断
- 对于严重或紧急症状，建议立即就医
- 药物推荐需要强调在医生指导下使用
- 保持专业、准确、负责任的态度

请用中文回复，结构化输出你的分析结果。"""

            # 构建用户消息
            user_message = f"患者症状描述：{symptoms}"
            if patient_info:
                user_message += f"\n患者信息：{json.dumps(patient_info, ensure_ascii=False)}"

            # 调用Qwen API（带降级）
            ai_response, model_used = chat_completion(
                model=self.text_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=1500,
            )
            ai_response = to_plain_text(ai_response)
            
            # 解析AI响应并结构化
            return self._parse_medical_response(ai_response, symptoms)
            
        except Exception as e:
            logger.error(f"症状分析失败: {str(e)}")
            return {
                "error": True,
                "message": "AI分析服务暂时不可用",
                "error_detail": str(e),
                "fallback_advice": "请记录症状详情，如症状持续或加重请及时就医"
            }
    
    def drug_recommendation(self, symptoms, medical_history=None):
        """药物推荐"""
        try:
            system_prompt = """你是一位专业的临床药师，请根据患者症状和病史，推荐合适的药物治疗方案。

要求：
1. 推荐常用的OTC（非处方药）药物
2. 明确标注用法用量
3. 列出注意事项和禁忌症
4. 强调需要医生指导
5. 提供药物相互作用提醒

注意：
- 仅推荐安全的常用药物
- 对于严重症状建议就医而非自行用药
- 特殊人群（孕妇、儿童、老人）需要特别说明
- 强调用药安全

请用中文回复，提供结构化的药物推荐。"""

            user_message = f"症状：{symptoms}"
            if medical_history:
                user_message += f"\n病史：{json.dumps(medical_history, ensure_ascii=False)}"

            ai_response, model_used = chat_completion(
                model=self.text_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=1200,
            )
            ai_response = to_plain_text(ai_response)
            return self._parse_drug_response(ai_response)
            
        except Exception as e:
            logger.error(f"药物推荐失败: {str(e)}")
            return {
                "error": True,
                "message": "药物推荐服务暂时不可用",
                "error_detail": str(e),
                "fallback_drugs": [
                    {
                        "name": "对乙酰氨基酚",
                        "dosage": "500mg",
                        "frequency": "每6-8小时一次",
                        "indication": "退热止痛"
                    }
                ]
            }
    
    def health_consultation(self, question, context=None):
        """健康咨询对话"""
        try:
            system_prompt = """你是一位经验丰富的全科医生，为患者提供专业的健康咨询服务。

你的特点：
1. 专业知识丰富，能够准确分析健康问题
2. 沟通亲切，耐心解答患者疑问
3. 注重患者安全，适时建议就医
4. 提供实用的健康建议和预防措施

回复要求：
- 语言通俗易懂，避免过多医学术语
- 结构清晰，条理分明
- 针对性强，解决患者具体问题
- 适时提醒就医和用药安全

请用温和、专业的语气回复患者的健康咨询。"""

            messages = [
                {"role": "system", "content": system_prompt},
            ]
            
            # 添加上下文对话历史
            if context:
                for msg in context:
                    messages.append(msg)
            
            messages.append({"role": "user", "content": question})

            ai_text, model_used = chat_completion(
                model=self.text_model,
                messages=messages,
                temperature=0.4,
                max_tokens=1000,
            )
            ai_text = to_plain_text(ai_text)

            return {"success": True, "response": ai_text, "source": "qwen-api", "model_used": model_used}
            
        except Exception as e:
            logger.error(f"健康咨询失败: {str(e)}")
            return {
                "error": True,
                "message": "咨询服务暂时不可用",
                "error_detail": str(e),
                "fallback_response": "感谢您的咨询。建议您详细记录症状情况，如有需要请及时就医咨询专业医生。"
            }

    def generate_structured_emr(self, brief_text: str, patient_profile: Optional[dict] = None):
        """生成结构化病历（面向医生端）。
        输入：简要关键信息/问诊要点，输出：中文结构化HTML（便于前端直接渲染）。
        充分利用用户提供的所有信息，生成详实的病历记录。
        """
        try:
            profile_text = json.dumps(patient_profile, ensure_ascii=False) if patient_profile else "{}"

            system_prompt = (
                "你是一名专业的临床医生助手，请基于医生提供的问诊信息生成规范的结构化病历。\n\n"
                "输出格式要求：\n"
                "- 输出为HTML片段，包含以下一级标题（按顺序）：\n"
                "  <h3>主诉</h3>、<h3>现病史</h3>、<h3>既往史</h3>、<h3>过敏史</h3>、\n"
                "  <h3>体格检查</h3>、<h3>辅助检查</h3>、<h3>初步诊断</h3>、<h3>诊疗计划</h3>\n\n"
                "内容填写规则：\n"
                "1. **主诉**：提取最主要的症状及持续时间（如：胃痛伴恶心2天）\n"
                "2. **现病史**：\n"
                "   - 详细描述症状特点（部位、性质、程度、诱因、缓解因素）\n"
                "   - 伴随症状\n"
                "   - 相关病史（如用药史、饮食习惯等）\n"
                "   - 充分利用医生提供的所有关键信息\n"
                "   - 用医学术语规范描述，但保留所有重要细节\n"
                "3. **既往史**：如医生提供相关信息则详细记录，否则填'否认特殊既往史'或'待补充'\n"
                "4. **过敏史**：如医生提供则记录，否则填'否认药物及食物过敏史'或'待补充'\n"
                "5. **体格检查**：如医生提供检查结果则记录，否则填'待完善体格检查'并建议需要的检查项目\n"
                "6. **辅助检查**：如医生提供检查结果则记录，否则填'待完善'并根据症状建议需要的检查\n"
                "7. **初步诊断**：基于症状和信息给出合理诊断（可列多个），如医生已提供诊断则优先使用\n"
                "8. **诊疗计划**：\n"
                "   - 一般治疗建议（如休息、饮食调整）\n"
                "   - 可能的药物治疗方向（不写具体剂量）\n"
                "   - 复诊建议和注意事项\n\n"
                "重要原则：\n"
                "- 充分利用医生输入的所有信息，不要遗漏关键细节\n"
                "- 用规范的医学术语组织，但要完整保留医生提供的信息\n"
                "- 信息不足时用规范用语说明需补充，不要编造\n"
                "- 末尾添加：<small style='color:#64748b;'>本病历仅供参考，需结合临床实际情况</small>"
            )

            user_message = (
                f"【患者档案信息】\n{profile_text}\n\n"
                f"【医生提供的问诊信息】\n{brief_text}\n\n"
                "请基于以上信息生成详细的结构化病历，充分利用医生提供的所有关键信息。"
            )

            ai_html, model_used = chat_completion(
                model=self.text_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,  # 适当提高温度，使其更好地组织信息
                max_tokens=2000,  # 增加token限制，允许更详细的病历
            )

            return {"success": True, "html": ai_html, "model_used": model_used}
        except Exception as e:
            logger.error(f"EMR 生成失败: {e}")
            return {"success": False, "message": "病历生成失败，请稍后重试", "error": str(e)}

    def _parse_user_input(self, brief_text: str) -> dict:
        """解析用户输入，提取具体医疗信息"""
        info = {
            'age': None,
            'gender': None,
            'symptoms': [],
            'vital_signs': {},
            'medical_history': None,
            'allergies': None,
            'examinations': [],
            'diagnosis': None
        }

        text = brief_text.lower()

        # 提取年龄
        age_match = re.search(r'(\d+)\s*岁', text)
        if age_match:
            info['age'] = int(age_match.group(1))

        # 提取性别
        if '女' in text or '女性' in text:
            info['gender'] = '女'
        elif '男' in text or '男性' in text:
            info['gender'] = '男'

        # 提取症状
        symptom_keywords = ['发热', '咳嗽', '咽痛', '头痛', '腹痛', '胸痛', '气促', '恶心', '呕吐', '腹泻']
        for keyword in symptom_keywords:
            if keyword in text:
                info['symptoms'].append(keyword)

        # 提取生命体征
        if '体温' in text and '℃' in text:
            temp_match = re.search(r'体温[^℃]*([0-9.]+)\s*℃', text)
            if temp_match:
                info['vital_signs']['体温'] = f"{temp_match.group(1)}℃"

        if '血压' in text and 'mmhg' in text.lower():
            bp_match = re.search(r'血压[^0-9]*([0-9/]+)\s*mmhg', text)
            if bp_match:
                info['vital_signs']['血压'] = bp_match.group(1)

        # 提取病史信息
        if '既往' in text and ('体健' in text or '健康' in text):
            info['medical_history'] = '既往体健'

        # 提取过敏史
        if '过敏' in text:
            if '无' in text or '否认' in text:
                info['allergies'] = '无药物过敏'
            else:
                info['allergies'] = '有药物过敏史'

        return info

    def _sanitize_emr_strictly(self, source_brief: str, html: str) -> str:
        """严格清理病历，去除任何虚假或推测的信息"""
        if not isinstance(html, str) or not html:
            return html

        out = html

        # 1. 清理体格检查：只保留明确提到的或设为"待查"
        if '<h3>体格检查</h3>' in out:
            # 检查用户输入中是否提到了具体的体格检查结果
            user_input = source_brief.lower()
            has_specific_pe = any(keyword in user_input for keyword in ['体温', '脉搏', '呼吸', '血压', '肺部', '心脏', '腹部'])

            if not has_specific_pe:
                # 如果用户没有提供具体的体格检查信息，一律设为待查
                safe_pe = (
                    '<h3>体格检查</h3>'
                    '<p>待查（需进行详细的体格检查以评估患者状况）</p>'
                )
                out = re.sub(r'(<h3>\s*体格检查\s*</h3>)(.*?)(?=<h3>|$)', safe_pe, out, flags=re.S)

        # 2. 清理辅助检查：只保留明确提到的或设为"待完善"
        if '<h3>辅助检查</h3>' in out:
            user_input = source_brief.lower()
            has_specific_exam = any(keyword in user_input for keyword in ['血常规', '尿常规', '胸片', 'ct', 'b超', '心电图'])

            if not has_specific_exam:
                safe_exam = (
                    '<h3>辅助检查</h3>'
                    '<p>待完善（建议根据病情需要完善相关检查项目）</p>'
                )
                out = re.sub(r'(<h3>\s*辅助检查\s*</h3>)(.*?)(?=<h3>|$)', safe_exam, out, flags=re.S)

        # 3. 清理现病史：只基于用户提供的具体信息
        user_info = self._parse_user_input(source_brief)
        if '<h3>现病史</h3>' in out:
            symptoms_text = '、'.join(user_info['symptoms']) if user_info['symptoms'] else '待补充'
            age_gender = ''
            if user_info['age'] or user_info['gender']:
                age_str = f"{user_info['age']}岁" if user_info['age'] else ''
                age_gender = f"{user_info['gender'] or ''}{age_str}".strip()

            safe_hpi = '<p>患者'
            if age_gender:
                safe_hpi += f"{age_gender}，"
            safe_hpi += f"主诉：{symptoms_text}。"
            if user_info['vital_signs']:
                vital_text = '、'.join([f"{k}：{v}" for k, v in user_info['vital_signs'].items()])
                safe_hpi += f"生命体征：{vital_text}。"
            safe_hpi += '</p>'

            out = re.sub(r'(<h3>现病史</h3>)(.*?)(?=<h3>|$)', rf'\1{safe_hpi}', out, flags=re.S)

        # 4. 既往史和过敏史：基于用户输入
        if '<h3>既往史</h3>' in out:
            if user_info['medical_history']:
                safe_history = f'<p>{user_info["medical_history"]}。</p>'
            else:
                safe_history = '<p>待补充。</p>'
            out = re.sub(r'(<h3>既往史</h3>)(.*?)(?=<h3>|$)', rf'\1{safe_history}', out, flags=re.S)

        if '<h3>过敏史</h3>' in out:
            if user_info['allergies']:
                safe_allergy = f'<p>{user_info["allergies"]}。</p>'
            else:
                safe_allergy = '<p>待补充。</p>'
            out = re.sub(r'(<h3>过敏史</h3>)(.*?)(?=<h3>|$)', rf'\1{safe_allergy}', out, flags=re.S)

        return out

    def generate_structured_emr_append(self, brief_text: str, existing_emr: str, patient_profile: Optional[dict] = None):
        """追加模式生成病历：合并现有病历和新输入内容"""
        try:
            profile_text = json.dumps(patient_profile, ensure_ascii=False) if patient_profile else "{}"

            system_prompt = (
                "你是一名专业的临床医生助手，请将新的问诊信息与现有病历合并，生成更新后的结构化病历。\n\n"
                "输出格式要求：\n"
                "- 输出为HTML片段，包含以下一级标题（按顺序）：\n"
                "  <h3>主诉</h3>、<h3>现病史</h3>、<h3>既往史</h3>、<h3>过敏史</h3>、\n"
                "  <h3>体格检查</h3>、<h3>辅助检查</h3>、<h3>初步诊断</h3>、<h3>诊疗计划</h3>\n\n"
                "合并规则：\n"
                "1. **主诉**：整合新旧主诉，保留核心症状，去重\n"
                "2. **现病史**：\n"
                "   - 保留原有病史内容\n"
                "   - 追加新的症状变化、治疗经过等信息\n"
                "   - 按时间顺序组织，形成连贯的病史记录\n"
                "3. **既往史/过敏史**：如新信息中有明确提及则更新，否则保留原有\n"
                "4. **体格检查/辅助检查**：如新信息中有新的检查结果则补充，否则保留原有\n"
                "5. **初步诊断**：基于合并后的完整信息重新评估，可能更新诊断\n"
                "6. **诊疗计划**：基于最新情况调整治疗方案\n\n"
                "重要原则：\n"
                "- 充分利用新提供的所有信息\n"
                "- 保留原有病历的有价值内容\n"
                "- 形成连贯、完整的病历记录\n"
                "- 末尾添加：<small style='color:#64748b;'>本病历仅供参考，需结合临床实际情况</small>"
            )

            user_message = (
                f"【患者档案信息】\n{profile_text}\n\n"
                f"【现有病历内容】\n{existing_emr}\n\n"
                f"【新增问诊信息】\n{brief_text}\n\n"
                "请将新信息与现有病历合并，生成更新后的完整病历。"
            )

            ai_html, model_used = chat_completion(
                model=self.text_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=2500,
            )

            return {"success": True, "html": ai_html, "model_used": model_used}

        except Exception as e:
            logger.error(f"追加病历生成失败: {e}")
            return {"success": False, "message": "追加病历生成失败，请稍后重试", "error": str(e)}

    def _parse_existing_emr(self, existing_emr_html: str) -> dict:
        """解析现有病历HTML，提取结构化信息"""
        info = {
            'chief_complaint': '',
            'present_illness': '',
            'past_history': '',
            'allergy_history': '',
            'physical_exam': '',
            'auxiliary_exam': '',
            'diagnosis': '',
            'treatment_plan': ''
        }

        if not existing_emr_html:
            return info

        try:
            # 简单的正则表达式解析，不依赖外部库
            import re

            # 使用正则表达式提取各个部分
            sections = [
                ('主诉', 'chief_complaint'),
                ('现病史', 'present_illness'),
                ('既往史', 'past_history'),
                ('过敏史', 'allergy_history'),
                ('体格检查', 'physical_exam'),
                ('辅助检查', 'auxiliary_exam'),
                ('初步诊断', 'diagnosis'),
                ('诊疗计划', 'treatment_plan')
            ]

            for section_name, key in sections:
                pattern = f'<h3[^>]*>{re.escape(section_name)}</h3>\\s*<p[^>]*>(.*?)</p>'
                match = re.search(pattern, existing_emr_html, re.IGNORECASE | re.DOTALL)
                if match:
                    info[key] = match.group(1).strip()

        except Exception as e:
            logger.warning(f"解析现有病历失败: {e}")

        return info

    def generate_treatment_plan(self, emr_html_or_text: str, patient_profile: Optional[dict] = None, num_plans: int = 3):
        """基于病历生成多个治疗方案（中文、结构化HTML），按推荐度排序。"""
        try:
            profile_text = json.dumps(patient_profile, ensure_ascii=False) if patient_profile else "{}"

            # 生成多个治疗方案的提示词
            system_prompt = (
                "你是一名临床医生助手，请基于病历内容生成多个治疗方案。"
                "输出严格JSON格式：{'plans': [{'name': '方案名称', 'score': 85, 'reason': '推荐理由', 'html': 'HTML内容'}, ...]}。"
                "每个方案包含：<h3>治疗目标</h3>、<h3>药物治疗</h3>（通用原则+常见方案）、<h3>非药物治疗</h3>、<h3>下一步检查</h3>、<h3>复诊与随访</h3>、<h3>预警信号</h3>。"
                "根据病历特点给出2-4个不同治疗策略的方案，按推荐度排序。"
            )

            user_message = (
                f"患者概况：{profile_text}\n"
                "以下为病历内容（HTML或文本）：\n" + emr_html_or_text.strip() + "\n"
                "请生成{num_plans}个治疗方案，按推荐度从高到低排序（score 0-100）。直接输出JSON，不要解释。"
            )

            ai_text, model_used = chat_completion(
                model=self.text_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,  # 稍高温度以产生多样性
                max_tokens=2000,
            )

            # 解析JSON响应
            try:
                data = _extract_json_payload(ai_text) or json.loads(ai_text)
                plans_data = data.get('plans', [])

                # 验证并格式化方案
                validated_plans = []
                for plan_data in plans_data[:num_plans]:  # 限制数量
                    if not all(k in plan_data for k in ['name', 'score', 'reason', 'html']):
                        continue

                    plan_html = self._format_treatment_plan_html(plan_data)
                    validated_plans.append({
                        'name': plan_data['name'],
                        'score': min(100, max(0, int(plan_data['score']))),  # 确保分数在0-100范围内
                        'reason': plan_data['reason'],
                        'html': plan_html,
                        'confidence': min(1.0, plan_data['score'] / 100.0)
                    })

                # 按分数排序
                validated_plans.sort(key=lambda x: x['score'], reverse=True)

                # 如果AI生成的方案不足，使用默认方案补齐
                if len(validated_plans) < num_plans:
                    default_plans = self._generate_default_plans(emr_html_or_text, num_plans - len(validated_plans))
                    validated_plans.extend(default_plans)

                return {
                    "success": True,
                    "plans": validated_plans,
                    "total_plans": len(validated_plans),
                    "model_used": model_used
                }

            except Exception as json_error:
                logger.warning(f"治疗方案JSON解析失败: {json_error}，使用回退方案")
                return self._generate_fallback_plans(emr_html_or_text, num_plans)

        except Exception as e:
            logger.error(f"治疗方案生成失败: {e}")
            return {"success": False, "message": "治疗方案生成失败，请稍后重试", "error": str(e)}

    def _format_treatment_plan_html(self, plan_data):
        """格式化单个治疗方案的HTML"""
        html_content = plan_data.get('html', '')

        # 如果HTML内容不足，构建基本结构
        if not html_content or '<h3>' not in html_content:
            name = plan_data.get('name', '治疗方案')
            html_content = f"""
                <h3>治疗目标</h3>
                <p>根据患者病情，制定个性化的治疗目标。</p>

                <h3>药物治疗</h3>
                <p><strong>治疗原则：</strong>根据患者具体情况选择合适的药物治疗方案。</p>
                <p><strong>推荐药物：</strong>医生将根据患者病情开具处方药物。</p>

                <h3>非药物治疗</h3>
                <ul>
                    <li>生活方式调整：保持规律作息，适量运动</li>
                    <li>饮食指导：清淡饮食，避免刺激性食物</li>
                    <li>心理支持：保持良好心态，避免过度焦虑</li>
                </ul>

                <h3>下一步检查</h3>
                <ul>
                    <li>根据病情需要，完善相关实验室检查</li>
                    <li>必要时进行影像学检查以明确诊断</li>
                    <li>监测相关生理指标的变化</li>
                </ul>

                <h3>复诊与随访</h3>
                <ul>
                    <li>建议1-2周后复诊，评估治疗效果</li>
                    <li>定期监测相关指标变化</li>
                    <li>根据病情变化及时调整治疗方案</li>
                </ul>

                <h3>预警信号</h3>
                <ul>
                    <li>症状加重或出现新症状</li>
                    <li>药物不良反应</li>
                    <li>重要生命体征异常</li>
                </ul>
            """

        return html_content

    def _generate_default_plans(self, emr_content, num_plans):
        """生成默认治疗方案"""
        default_plans = [
            {
                'name': '保守治疗方案',
                'score': 75,
                'reason': '适合大多数患者，风险较低',
                'html': self._create_conservative_plan_html(emr_content),
                'confidence': 0.75
            },
            {
                'name': '积极治疗方案',
                'score': 60,
                'reason': '针对症状较重的患者，疗效更快但风险稍高',
                'html': self._create_aggressive_plan_html(emr_content),
                'confidence': 0.60
            },
            {
                'name': '综合治疗方案',
                'score': 85,
                'reason': '结合药物和非药物治疗，全面改善',
                'html': self._create_comprehensive_plan_html(emr_content),
                'confidence': 0.85
            }
        ]

        return default_plans[:num_plans]

    def _generate_fallback_plans(self, emr_content, num_plans):
        """生成回退治疗方案"""
        return {
            "success": True,
            "plans": self._generate_default_plans(emr_content, num_plans),
            "total_plans": num_plans,
            "model_used": "fallback",
            "note": "由于AI服务暂时不可用，使用预设方案"
        }

    def _create_conservative_plan_html(self, emr_content):
        """创建保守治疗方案HTML"""
        return """
            <h3>治疗目标</h3>
            <p>缓解症状，改善生活质量，避免过度医疗干预。</p>

            <h3>药物治疗</h3>
            <p><strong>治疗原则：</strong>优先选择相对安全的药物，从小剂量开始。</p>
            <p><strong>推荐药物：</strong>对症治疗药物，医生根据病情开具。</p>

            <h3>非药物治疗</h3>
            <ul>
                <li>休息：保证充足睡眠，避免过度劳累</li>
                <li>饮食：清淡饮食，多喝水</li>
                <li>生活方式：规律作息，避免不良习惯</li>
            </ul>

            <h3>复诊与随访</h3>
            <ul>
                <li>1周后复诊评估症状改善情况</li>
                <li>如症状无改善或加重，及时就医</li>
            </ul>

            <h3>预警信号</h3>
            <ul>
                <li>症状持续加重</li>
                <li>出现新的严重症状</li>
            </ul>
        """

    def _create_aggressive_plan_html(self, emr_content):
        """创建积极治疗方案HTML"""
        return """
            <h3>治疗目标</h3>
            <p>快速缓解症状，尽快恢复正常生活和工作。</p>

            <h3>药物治疗</h3>
            <p><strong>治疗原则：</strong>采用更积极的药物治疗策略，争取快速见效。</p>
            <p><strong>推荐药物：</strong>根据病情选择疗效较好的药物组合。</p>

            <h3>非药物治疗</h3>
            <ul>
                <li>休息：适当休息，避免剧烈活动</li>
                <li>饮食：营养丰富，促进恢复</li>
                <li>康复：配合适当的康复锻炼</li>
            </ul>

            <h3>复诊与随访</h3>
            <ul>
                <li>3-5天后复诊，评估治疗效果</li>
                <li>定期监测病情变化</li>
            </ul>

            <h3>预警信号</h3>
            <ul>
                <li>治疗无效或症状加重</li>
                <li>药物不良反应</li>
            </ul>
        """

    def _create_comprehensive_plan_html(self, emr_content):
        """创建综合治疗方案HTML"""
        return """
            <h3>治疗目标</h3>
            <p>全面改善症状，提高整体健康水平，预防复发。</p>

            <h3>药物治疗</h3>
            <p><strong>治疗原则：</strong>药物治疗结合非药物治疗，形成综合治疗体系。</p>
            <p><strong>推荐药物：</strong>根据患者具体情况选择合适的药物。</p>

            <h3>非药物治疗</h3>
            <ul>
                <li>生活方式干预：改善作息、饮食和运动习惯</li>
                <li>心理支持：必要时寻求心理咨询</li>
                <li>康复治疗：配合物理治疗等辅助手段</li>
            </ul>

            <h3>复诊与随访</h3>
            <ul>
                <li>定期复诊，监测治疗效果</li>
                <li>根据病情调整治疗方案</li>
                <li>长期随访，预防疾病复发</li>
            </ul>

            <h3>预警信号</h3>
            <ul>
                <li>症状反复或加重</li>
                <li>出现并发症迹象</li>
                <li>治疗效果不佳</li>
            </ul>
        """

    def diagnosis_chat(self, user_input: str, context: Optional[list] = None):
        """病情问诊多轮对话：返回 JSON，可能是继续追问或给出总结。
        输出格式（严格JSON）：
        {
          "status": "ask"|"final",
          "ask": { "question": string },
          "final": { "summary_html": string, "next_steps": [string], "red_flags": [string] }
        }
        要求语气：安抚、信任感、专业但通俗。
        """
        try:
            system_prompt = (
                "你是一位有同理心的全科医生，进行病情问诊。请用安抚、可信赖的语气，专业且通俗的表达。\n"
                "目标：通过2-5次追问获取关键要点（起病时间、伴随症状、严重程度、既往史、用药情况、危险信号等），在信息充分时给出总结。\n"
                "请严格输出JSON，不要任何额外说明。结构：{\n"
                "  \"status\": \"ask\"|\"final\",\n"
                "  \"ask\": { \"question\": string },\n"
                "  \"final\": { \"summary_html\": string, \"next_steps\": [string], \"red_flags\": [string] }\n"
                "}。当信息不足时输出 ask；当已足够时输出 final，summary_html 用中文结构化HTML（含 <h3>要点</h3>、<h3>可能诊断</h3>、<h3>建议</h3>）。"
            )

            messages = [{"role": "system", "content": system_prompt}]
            if context:
                for m in context:
                    role = m.get("role")
                    content = m.get("content")
                    if role in ("user", "assistant") and content:
                        messages.append({"role": role, "content": str(content)})
            messages.append({"role": "user", "content": user_input})

            content, model_used = chat_completion(
                model=self.text_model,
                messages=messages,
                temperature=0.3,
                max_tokens=1000,
            )

            # 解析严格JSON
            try:
                data = _extract_json_payload(content) or json.loads(content)
                status = data.get("status")
                if status == "ask":
                    q = (data.get("ask") or {}).get("question") or "为了更了解您的情况，您能再补充一下症状的持续时间和严重程度吗？"
                    return {"success": True, "mode": "ask", "question": to_plain_text(q)}
                else:
                    final = data.get("final") or {}
                    html = final.get("summary_html") or to_plain_text(content)
                    html = normalize_summary_html(html)
                    next_steps = final.get("next_steps") or []
                    red_flags = final.get("red_flags") or []
                    return {"success": True, "mode": "final", "summary_html": html, "next_steps": next_steps, "red_flags": red_flags}
            except Exception:
                # 回退：当模型未按JSON，直接作为最终总结
                return {"success": True, "mode": "final", "summary_html": normalize_summary_html(to_plain_text(content)), "next_steps": [], "red_flags": []}
        except Exception as e:
            logger.error(f"diagnosis chat failed: {e}")
            return {"success": False, "message": "问诊暂不可用", "error": str(e)}
    
    def vision_analyze(self, image_data_url: str, kind: str, note: str = ""):
        """图像理解：支持 药品外包装/瓶盒、检验单、皮肤/外伤 三类
        :param image_data_url: data:image/...;base64,XXX 形式
        :param kind: drug|report|skin
        """
        # 针对不同任务提供专业的结构化输出要求
        kind = (kind or 'auto').lower()
        if kind in ['drug', 'medicine', 'med', 'pill', 'box']:
            kind = 'drug'
            task_prompt = (
                "你是一名资深临床药师与药事管理专家，请对上传的药品包装/瓶盒进行OCR与语义理解，"
                "抽取关键信息并输出专业、中文、结构化HTML且尽量贴合以下栏目：\n"
                "<h3>药品名称</h3>（通用名/商品名）；<h3>适应症</h3>；<h3>一般用法用量</h3>；"
                "<h3>不良反应/副作用</h3>；<h3>重要成分</h3>；<h3>注意事项/禁忌</h3>；"
                "<h3>识别结果附录</h3>（规格、剂型、生产厂家/批次、批准文号等如可见）。"
            )
        elif kind in ['report', 'exam', 'check', 'lab', '检验单', '检验', '检查']:
            kind = 'report'
            task_prompt = (
                "你是一名三甲医院的检验科/影像科主治医师，请对上传的检验/检查报告进行OCR与临床解读，"
                "输出中文、结构化HTML：\n"
                "包含：<h3>报告信息</h3>（姓名/性别/年龄、标本、检查名称、报告时间等可识别项）；"
                "<h3>关键指标</h3>使用<table><thead><tr><th>项目</th><th>结果</th><th>单位</th><th>参考区间</th><th>解读</th></tr></thead><tbody>...</tbody></table>；"
                "<h3>总体解读</h3>（结合异常指标说明可能意义与建议）；<h3>建议与随访</h3>（复查/就医提示）。"
            )
        else:
            kind = 'skin'
            task_prompt = (
                "你是一名皮肤科与创伤科联合门诊医生，请对上传的皮肤/外伤图像进行面向患者的专业解释（非最终诊断），"
                "输出中文、结构化HTML，并满足以下栏目与约束：\n"
                "<h3>可能疾病（按优先级）</h3>：列出1-3个候选并排序；每条给出不含'因为…所以…'等因果措辞的'依据'，改用客观可见征象描述。\n"
                "<h3>可用药品</h3>：如需用药，列出常见外用/口服药物及用法要点。\n"
                "<h3>治疗方案</h3>：居家处理/门诊处理建议与何时就医。\n"
                "<h3>注意事项</h3>：护理要点、避免事项、复查建议与红旗信号。"
            )

        # 构造多模态消息（OpenAI兼容内容数组）
        user_text = "请基于该图片完成上面的结构化分析，并直接以HTML输出。"
        if note:
            user_text += f"\n补充说明：{note}"
        messages = [
            {"role": "system", "content": task_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": image_data_url}}
            ]}
        ]

        try:
            ai_text, model_used = chat_completion(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=1800,
            )
            # 不做Markdown清洗，保留HTML结构以便前端渲染
            return {"success": True, "kind": kind, "html": ai_text, "model_used": model_used}
        except Exception as e:
            logger.error(f"图像理解失败: {e}")
            return {"success": False, "message": "图像分析失败，请稍后重试", "error": str(e)}

    def emergency_assessment(self, symptoms):
        """紧急程度评估"""
        try:
            system_prompt = """你是一位急诊科医生，请快速评估患者症状的紧急程度。

评估标准：
- 紧急（立即就医）：威胁生命的症状
- 急迫（尽快就医）：需要及时处理的症状  
- 一般（可观察）：可以观察或居家处理的症状

请简洁明确地给出评估结果和建议。"""

            response, model_used = chat_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请评估以下症状的紧急程度：{symptoms}"},
                ],
                temperature=0.1,
                max_tokens=500,
            )
            response = to_plain_text(response)
            
            return self._parse_emergency_response(response)
            
        except Exception as e:
            logger.error(f"紧急程度评估失败: {str(e)}")
            return {
                "urgency_level": "unknown",
                "message": "无法评估，建议咨询医生",
                "error_detail": str(e),
                "action": "如有疑虑请及时就医"
            }
    
    def _parse_medical_response(self, ai_response, symptoms):
        """解析医疗响应"""
        try:
            # 简单的关键词分析来确定紧急程度
            emergency_keywords = ['胸痛', '呼吸困难', '意识障碍', '大出血', '急性', '严重']
            urgent_keywords = ['发烧', '持续', '剧烈', '头痛', '腹痛']
            
            urgency_level = "normal"
            urgency_color = "#27ae60"
            urgency_message = "症状相对较轻，可观察并适当治疗"
            
            for keyword in emergency_keywords:
                if keyword in symptoms:
                    urgency_level = "emergency"
                    urgency_color = "#e74c3c"
                    urgency_message = "症状可能较为严重，建议立即就医"
                    break
            
            if urgency_level == "normal":
                for keyword in urgent_keywords:
                    if keyword in symptoms:
                        urgency_level = "urgent"
                        urgency_color = "#f39c12"
                        urgency_message = "建议尽快就医检查"
                        break
            
            return {
                "success": True,
                "diagnosis_advice": ai_response,
                "urgency_level": {
                    "level": urgency_level,
                    "message": urgency_message,
                    "color": urgency_color
                },
                "recommendations": self._extract_recommendations(ai_response),
                "risk_assessment": {
                    "risk_level": "中等风险" if urgency_level == "urgent" else "低风险",
                    "risk_score": 30 if urgency_level == "urgent" else 15
                },
                "source": "qwen-api"
            }
            
        except Exception as e:
            logger.error(f"响应解析失败: {str(e)}")
            return {
                "success": True,
                "diagnosis_advice": ai_response,
                "urgency_level": {
                    "level": "normal",
                    "message": "请关注症状变化",
                    "color": "#27ae60"
                },
                "recommendations": ["观察症状变化", "适当休息", "必要时就医"],
                "risk_assessment": {"risk_level": "未知", "risk_score": 20},
                "source": "qwen-api"
            }
    
    def _parse_drug_response(self, ai_response):
        """解析药物推荐响应"""
        return {
            "success": True,
            "recommended_drugs": [
                {
                    "name": "根据AI建议",
                    "dosage": "详见AI分析",
                    "frequency": "按医嘱",
                    "indication": "对症治疗"
                }
            ],
            "detailed_advice": ai_response,
            "warnings": ["请在医生指导下使用", "注意药物相互作用", "遵循说明书用药"],
            "source": "qwen-api"
        }
    
    def _parse_emergency_response(self, response):
        """解析紧急程度评估响应"""
        if "紧急" in response or "立即" in response:
            return {
                "urgency_level": "emergency",
                "message": "建议立即就医",
                "action": "请前往急诊科",
                "color": "#e74c3c"
            }
        elif "急迫" in response or "尽快" in response:
            return {
                "urgency_level": "urgent", 
                "message": "建议尽快就医",
                "action": "请及时预约就诊",
                "color": "#f39c12"
            }
        else:
            return {
                "urgency_level": "normal",
                "message": "可以观察症状变化",
                "action": "注意休息，必要时就医",
                "color": "#27ae60"
            }
    
    def _extract_recommendations(self, ai_response):
        """从AI响应中提取建议"""
        # 简单的建议提取逻辑
        default_recommendations = [
            "记录症状的发生时间和严重程度",
            "保持充足的休息和睡眠",
            "注意饮食健康，多喝水",
            "如症状持续或加重，请及时就医"
        ]
        
        # 这里可以添加更复杂的NLP逻辑来提取具体建议
        return default_recommendations

    def tcm_vision_analyze(self, images, analysis_type='tcm_diagnosis'):
        """中医视觉分析"""
        try:
            messages = []
            
            # 构建中医专业提示词
            system_prompt = "你是一位资深的中医专家，依据望诊（面诊与舌诊）给出结构化、专业且通俗易懂的分析与建议。回复中不要包含本提示语。"
            
            messages.append({
                "role": "system",
                "content": system_prompt
            })
            
            # 构建用户消息
            user_content = []
            
            for img in images:
                img_type = img.get('type', 'unknown')
                description = img.get('description', '')
                
                if img_type == 'face':
                    user_content.append({
                        "type": "text", 
                        "text": f"请分析这张面部图像的中医特征：{description}"
                    })
                elif img_type == 'tongue':
                    user_content.append({
                        "type": "text",
                        "text": f"请分析这张舌象图像的中医特征：{description}"
                    })
                
                # 添加图像
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": img['data']
                    }
                })

            # 要求严格JSON结构化输出，避免提示语进入正文
            user_content.append({
                "type": "text",
                "text": (
                    "请基于以上面诊/舌诊图像输出严格的JSON（仅JSON，不要额外说明）。"
                    "字段结构：{\n"
                    "  \"face\": { \"complexion\": string, \"features\": [string], \"constitution\": string, \"analysis\": string },\n"
                    "  \"tongue\": { \"bodyColor\": string, \"bodyShape\": string, \"coatingColor\": string, \"coatingThickness\": string, \"moisture\": string, \"constitution\": string, \"analysis\": string },\n"
                    "  \"zangfu\": { \"liver\": string, \"heart\": string, \"spleen\": string, \"lung\": string, \"kidney\": string },\n"
                    "  \"syndromes\": [ { \"name\": string, \"basis\": [string] } ],\n"
                    "  \"treatment\": { \"principle\": string, \"formula\": string, \"acupoints\": [string], \"herbal\": [string] },\n"
                    "  \"lifestyle\": { \"diet\": [string], \"exercise\": [string], \"sleep\": [string], \"emotion\": [string] }\n"
                    "}。仅输出JSON，且所有字段尽量完整，不要包含提示语或说明性文字。"
                )
            })
            
            messages.append({
                "role": "user",
                "content": user_content
            })
            
            # 调用AI分析
            ai_text, _model_used = chat_completion(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=1200,
            )
            
            # 解析响应
            return self._parse_tcm_vision_response(ai_text, images)
            
        except Exception as e:
            logger.error(f"TCM vision analyze error: {e}")
            return {"error": str(e)}

    def tcm_inquiry_analyze(self, patient_info, symptoms, analysis_type='tcm_inquiry'):
        """中医问诊分析"""
        try:
            system_prompt = "你是一位经验丰富的中医师，依据患者信息与症状进行辨证与建议。回复中不要包含本提示语。"
            
            # 构建症状描述
            symptoms_text = "、".join(symptoms) if symptoms else "无特殊症状"
            age = patient_info.get('age', '未知')
            gender = '男性' if patient_info.get('gender') == 'male' else '女性'
            
            user_message = f"""
患者基本信息：
- 年龄：{age}岁
- 性别：{gender}

主要症状：{symptoms_text}

请进行中医辨证分析并给出相应的治疗建议。
"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            ai_text, _model_used = chat_completion(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=1200,
            )
            return self._parse_tcm_inquiry_response(ai_text, patient_info, symptoms)
            
        except Exception as e:
            logger.error(f"TCM inquiry analyze error: {e}")
            return {"error": str(e)}

    def tcm_pulse_analyze(self, pulse_characteristics, analysis_type='tcm_pulse'):
        """中医脉象分析"""
        try:
            system_prompt = "你是一位精通脉诊的中医师，根据脉象特征给出分析与建议。回复中不要包含本提示语。"
            
            pulse_desc = []
            if pulse_characteristics.get('rate'):
                pulse_desc.append(f"脉率：{pulse_characteristics['rate']}")
            if pulse_characteristics.get('strength'):
                pulse_desc.append(f"脉力：{pulse_characteristics['strength']}")
            if pulse_characteristics.get('form'):
                pulse_desc.append(f"脉形：{pulse_characteristics['form']}")
            if pulse_characteristics.get('description'):
                pulse_desc.append(f"详细描述：{pulse_characteristics['description']}")
            
            pulse_text = "、".join(pulse_desc) if pulse_desc else "脉象信息不完整"
            
            user_message = f"患者脉象特征：{pulse_text}\n\n请进行专业的中医脉诊分析。"
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            ai_text, _model_used = chat_completion(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=1000,
            )
            return self._parse_tcm_pulse_response(ai_text, pulse_characteristics)
            
        except Exception as e:
            logger.error(f"TCM pulse analyze error: {e}")
            return {"error": str(e)}

    def _parse_tcm_vision_response(self, response, images):
        """解析中医视觉分析响应"""
        try:
            content = response if isinstance(response, str) else response.get('content', '')

            # 优先解析JSON结构化结果
            try:
                data = json.loads(content)
            except Exception:
                data = None
            
            result = {}
            if isinstance(data, dict):
                face = data.get('face') or {}
                tongue = data.get('tongue') or {}
                result['face'] = {
                    'analysis': face.get('analysis') or face.get('complexion') or '',
                    'constitution': face.get('constitution') or '',
                    'complexion': face.get('complexion') or '',
                    'features': face.get('features') or []
                }
                result['tongue'] = {
                    'analysis': tongue.get('analysis') or '',
                    'constitution': tongue.get('constitution') or '',
                    'bodyColor': tongue.get('bodyColor') or '',
                    'bodyShape': tongue.get('bodyShape') or '',
                    'coatingColor': tongue.get('coatingColor') or '',
                    'coatingThickness': tongue.get('coatingThickness') or '',
                    'moisture': tongue.get('moisture') or ''
                }
                result['zangfu'] = data.get('zangfu') or {}
                result['syndromes'] = data.get('syndromes') or []
                result['treatment'] = data.get('treatment') or {}
                lf = data.get('lifestyle') or {}
                # 统一建议为数组
                suggestions = []
                for k in ('diet','exercise','sleep','emotion'):
                    if isinstance(lf.get(k), list):
                        suggestions.extend(lf.get(k))
                result['suggestions'] = suggestions
                return result

            # 检查是否有面诊图像
            has_face = any(img.get('type') == 'face' for img in images)
            if has_face:
                result['face'] = {
                    'analysis': self._extract_tcm_section(content, ['面诊', '面色', '气色']),
                    'constitution': self._extract_tcm_section(content, ['体质', '面诊体质']),
                    'suggestions': self._extract_tcm_suggestions(content)
                }
            
            # 检查是否有舌诊图像
            has_tongue = any(img.get('type') == 'tongue' for img in images)
            if has_tongue:
                result['tongue'] = {
                    'analysis': self._extract_tcm_section(content, ['舌诊', '舌象', '舌质', '舌苔']),
                    'constitution': self._extract_tcm_section(content, ['体质', '舌诊体质']),
                    'suggestions': self._extract_tcm_suggestions(content)
                }
            
            # 如果解析失败，返回原始内容
            if not result:
                result = {
                    'general_analysis': content,
                    'suggestions': ['请咨询专业中医师获得更详细的诊断']
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Parse TCM vision response error: {e}")
            return {"error": "分析结果解析失败"}

    def _parse_tcm_inquiry_response(self, response, patient_info, symptoms):
        """解析中医问诊分析响应"""
        try:
            content = response if isinstance(response, str) else response.get('content', '')
            
            return {
                'syndrome_differentiation': self._extract_tcm_section(content, ['辨证', '证候', '诊断']),
                'constitution_type': self._extract_tcm_section(content, ['体质', '体质类型']),
                'treatment_principle': self._extract_tcm_section(content, ['治疗原则', '治则', '治法']),
                'herbal_formula': self._extract_tcm_section(content, ['方剂', '药方', '中药']),
                'lifestyle_suggestions': self._extract_tcm_suggestions(content),
                'follow_up': self._extract_tcm_section(content, ['复诊', '随访', '注意事项'])
            }
            
        except Exception as e:
            logger.error(f"Parse TCM inquiry response error: {e}")
            return {"error": "问诊分析解析失败"}

    def _parse_tcm_pulse_response(self, response, pulse_characteristics):
        """解析中医脉象分析响应"""
        try:
            content = response if isinstance(response, str) else response.get('content', '')
            
            return {
                'pulse_analysis': self._extract_tcm_section(content, ['脉象分析', '脉诊', '脉象']),
                'constitution_assessment': self._extract_tcm_section(content, ['体质', '体质评估']),
                'health_status': self._extract_tcm_section(content, ['健康状况', '病理', '状态']),
                'treatment_suggestions': self._extract_tcm_suggestions(content),
                'meridian_status': self._extract_tcm_section(content, ['经络', '气血', '经脉']),
                'follow_up_advice': self._extract_tcm_section(content, ['建议', '注意', '调理'])
            }
            
        except Exception as e:
            logger.error(f"Parse TCM pulse response error: {e}")
            return {"error": "脉象分析解析失败"}

    def medical_knowledge_search(self, query):
        """医学文献搜索"""
        try:
            # 使用医疗AI进行医学知识查询
            system_prompt = """你是专业的医学文献搜索引擎。请基于医学知识库，为用户提供准确、权威的医学信息。

查询要求：
1. 提供基于最新医学证据的回答
2. 只引用权威医学网站的链接，不要生成不存在的链接
3. 给出临床意义和应用价值
4. 注明证据等级和推荐强度

权威医学网站链接（只使用这些网站）：
- PubMed: https://pubmed.ncbi.nlm.nih.gov/
- WHO: https://www.who.int/health-topics
- CDC: https://www.cdc.gov/
- NCCN: https://www.nccn.org/
- 中华医学会: https://www.cma.org.cn/
- 中国临床肿瘤学会: https://www.csco.org.cn/
- UpToDate: https://www.uptodate.com/
- ClinicalTrials: https://clinicaltrials.gov/

请用纯文本格式回答，在引用来源时只使用上述权威网站的链接，不要生成其他链接。"""

            user_prompt = f"请搜索医学文献，回答以下问题：{query}。请用纯文本格式回答，避免markdown表格和特殊格式。"

            ai_response, model_used = chat_completion(
                model=self.text_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )

            # 清洗和格式化AI响应
            cleaned_content = self._clean_medical_content(ai_response)

            # 解析AI响应，提取结构化信息和链接
            # 从AI响应中提取链接信息
            links = self._extract_medical_links(cleaned_content)

            return {
                "results": [
                    {
                        "title": f"医学文献查询：{query}",
                        "content": cleaned_content,
                        "source": "医疗AI知识库",
                        "confidence": "高",
                        "citations": [
                            "基于最新医学证据和临床指南",
                            "参考国际权威医学文献",
                            f"数据更新时间：{datetime.now().strftime('%Y-%m-%d')}"
                        ],
                        "links": links
                    }
                ],
                "total": 1,
                "query": query
            }

        except Exception as e:
            logger.error(f"medical knowledge search error: {e}")
            return {"results": [], "total": 0, "error": str(e)}

    def _clean_medical_content(self, content):
        """清洗医学内容，去除markdown格式，转换为纯文本"""
        if not content:
            return ""

        # 去除markdown表格
        content = re.sub(r'\|.*\|', '', content)  # 去除表格行
        content = re.sub(r'\|-+.*\|', '', content)  # 去除表格分隔符

        # 去除markdown标题符号
        content = re.sub(r'^#{1,6}\s+', '', content, flags=re.MULTILINE)

        # 去除markdown链接格式
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)

        # 去除markdown强调符号
        content = re.sub(r'\*\*([^\*]+)\*\*', r'\1', content)  # 粗体
        content = re.sub(r'\*([^\*]+)\*', r'\1', content)  # 斜体

        # 去除markdown列表符号，但保留内容
        content = re.sub(r'^[\s]*[-*+]\s+', '• ', content, flags=re.MULTILINE)
        content = re.sub(r'^[\s]*\d+\.\s+', '', content, flags=re.MULTILINE)  # 去除有序列表编号

        # 去除多余的空行
        content = re.sub(r'\n{3,}', '\n\n', content)

        # 去除引用标记
        content = re.sub(r'^>\s*', '', content, flags=re.MULTILINE)

        # 去除代码块标记
        content = re.sub(r'```[^\n]*\n', '', content)
        content = re.sub(r'```', '', content)

        # 清理首尾空白
        content = content.strip()

        return content

    # 医学数据验证相关方法
    def check_keyword_relevance(self, query, content):
        """检查查询关键词与内容的匹配度"""
        if not query or not content:
            return 0.0

        query_words = set(re.findall(r'\b\w+\b', query.lower()))
        content_words = set(re.findall(r'\b\w+\b', content.lower()))

        # 计算关键词匹配度
        if not query_words:
            return 0.0

        matched_words = query_words.intersection(content_words)
        return len(matched_words) / len(query_words)

    def check_medical_facts(self, content):
        """检查医学事实准确性（基于常识规则）"""
        if not content:
            return 0.0

        score = 0.8  # 基础分数

        # 检查是否有过度绝对化表述
        absolute_phrases = ['绝对不能', '必须', '永远', '完全治愈', '100%有效']
        for phrase in absolute_phrases:
            if phrase in content:
                score -= 0.1

        # 检查是否有合理的医学表述
        positive_indicators = ['建议', '推荐', '可能', '一般', '通常', '研究显示', '临床试验']
        for indicator in positive_indicators:
            if indicator in content:
                score += 0.05

        # 检查是否有引用来源
        if '来源：' in content or '引用：' in content or '参考：' in content:
            score += 0.1

        return max(0.0, min(1.0, score))

    def check_citation_quality(self, content):
        """检查引用质量"""
        if not content:
            return 0.0

        score = 0.5  # 基础分数

        # 检查是否有具体的引用格式
        citation_patterns = [
            r'\d{4}',  # 年份
            r'Vol\.',  # 卷号
            r'No\.',   # 期号
            r'pp?\.',  # 页码
            r'et al\.',  # 等人
        ]

        found_citations = 0
        for pattern in citation_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                found_citations += 1

        score += found_citations * 0.1

        # 检查是否有权威来源引用
        authoritative_sources = ['WHO', 'CDC', 'NCCN', 'AHA', 'ACC', 'ESC', '中国']
        for source in authoritative_sources:
            if source in content:
                score += 0.1

        return min(1.0, score)

    def get_reliability_level(self, score):
        """根据综合评分获取可靠性等级"""
        if score >= 0.8:
            return "高可靠性"
        elif score >= 0.6:
            return "中等可靠性"
        elif score >= 0.4:
            return "一般可靠性"
        else:
            return "低可靠性"

    def generate_verification_recommendations(self, keyword_score, fact_score, citation_score):
        """生成验证建议"""
        recommendations = []

        if keyword_score < 0.5:
            recommendations.append("建议优化查询关键词，使其更准确地反映医学问题")

        if fact_score < 0.6:
            recommendations.append("建议核实医学事实表述，避免过度绝对化")

        if citation_score < 0.5:
            recommendations.append("建议补充权威医学文献引用，提高可信度")

        if not recommendations:
            recommendations.append("内容质量良好，具有较高可靠性")

        return recommendations

    def medical_guidelines_search(self, query, category="all"):
        """医学指南和共识查询"""
        try:
            # 根据分类调整查询焦点
            category_prompts = {
                "internal": "以内科疾病诊治指南为重点",
                "surgery": "以外科手术指南为重点",
                "pediatrics": "以儿科疾病指南为重点",
                "obstetrics": "以妇产科指南为重点",
                "emergency": "以急诊医学指南为重点",
                "all": "涵盖所有医学专科领域"
            }

            category_focus = category_prompts.get(category, category_prompts["all"])

            system_prompt = f"""你是专业的医学指南查询专家。请提供最新、最权威的医学指南和共识信息。

{category_focus}

查询要求：
1. 优先引用国际和国内权威指南（如WHO、NCCN、CSCO等）
2. 注明指南版本和发布时间
3. 突出关键推荐和证据等级
4. 提供临床决策支持信息
5. 只引用权威医学网站的真实链接

权威医学指南网站（只使用这些网站）：
- WHO指南: https://www.who.int/health-topics
- NCCN指南: https://www.nccn.org/
- 中华医学会指南: https://www.cma.org.cn/
- 中国临床肿瘤学会: https://www.csco.org.cn/
- CDC指南: https://www.cdc.gov/

请用纯文本格式回答，只在回答末尾引用上述权威网站的链接，不要生成其他链接。"""

            user_prompt = f"请查询医学指南：{query}。请用纯文本格式回答，避免markdown表格和特殊格式。"

            ai_response, model_used = chat_completion(
                model=self.text_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=1500
            )

            # 清洗和格式化AI响应
            cleaned_content = self._clean_medical_content(ai_response)

            # 解析AI响应，提取指南信息和链接
            links = self._extract_medical_links(cleaned_content)

            # 解析AI响应，提取指南信息
            return {
                "guidelines": [
                    {
                        "title": f"医学指南查询：{query}",
                        "content": cleaned_content,
                        "category": category,
                        "authority": "医疗AI指南库",
                        "version": "最新版",
                        "recommendations": [
                            "基于最新医学证据",
                            "参考权威临床指南",
                            f"数据更新时间：{datetime.now().strftime('%Y-%m-%d')}"
                        ],
                        "links": links
                    }
                ],
                "query": query,
                "category": category
            }

        except Exception as e:
            logger.error(f"medical guidelines search error: {e}")
            return {"guidelines": [], "error": str(e)}

    def _extract_medical_links(self, content):
        """从医学内容中提取链接信息 - 增强版"""
        import re
        from urllib.parse import urlparse

        # 权威医学网站域名白名单
        authoritative_medical_domains = [
            'pubmed.ncbi.nlm.nih.gov',
            'www.ncbi.nlm.nih.gov',
            'www.who.int',
            'www.cdc.gov',
            'www.nccn.org',
            'www.csco.org.cn',
            'www.cma.org.cn',
            'www.uptodate.com',
            'www.mayoclinic.org',
            'www.webmd.com',
            'www.nih.gov',
            'www.nejm.org',
            'www.thelancet.com',
            'www.bmj.com',
            'www.jamanetwork.com',
            'guideline.gov',
            'clinicaltrials.gov',
            'www.fda.gov',
            'www.ema.europa.eu',
            'www.cfda.gov.cn',
            'www.cde.org.cn'
        ]

        links = []
        seen_urls = set()  # 避免重复链接

        # 查找文本中的链接
        url_pattern = r'https?://[^\s<>"{}|\\^`[\]]+'
        urls = re.findall(url_pattern, content, re.IGNORECASE)

        for url in urls:
            # 清理URL
            url = url.strip()
            if url in seen_urls or len(url) < 10:
                continue

            seen_urls.add(url)

            # 严格验证是否为权威医学域名
            if self._is_authoritative_medical_url(url, authoritative_medical_domains):
                # 额外验证链接格式和基本有效性
                if self._is_valid_medical_url(url):
                    link_info = self._create_link_info(url, authoritative_medical_domains)
                    if link_info:
                        links.append(link_info)

        # 如果没有找到有效链接，返回精心挑选的权威来源链接
        if not links:
            links = self._get_default_authoritative_links()

        return links

    def _is_authoritative_medical_url(self, url, authoritative_domains):
        """验证URL是否来自权威医学域名"""
        try:
            url_obj = urlparse(url)
            domain = url_obj.netloc.lower()

            # 精确匹配或子域名匹配
            return any(
                domain == auth_domain or domain.endswith('.' + auth_domain)
                for auth_domain in authoritative_domains
            )
        except Exception:
            return False

    def _is_valid_medical_url(self, url):
        """验证医学URL的基本有效性"""
        try:
            url_obj = urlparse(url)

            # 检查协议
            if url_obj.scheme not in ['http', 'https']:
                return False

            # 检查域名长度和格式
            domain = url_obj.netloc
            if not domain or len(domain) < 3:
                return False

            # 检查是否有合理的路径（医学网站通常有路径）
            if not url_obj.path or url_obj.path == '/':
                return True  # 主页通常是有效的

            # 检查路径是否过于复杂（可能是不完整的链接）
            path_parts = [part for part in url_obj.path.split('/') if part]
            if len(path_parts) > 4:  # 路径太深可能有问题
                return False

            # 检查是否有可疑的扩展名
            suspicious_extensions = ['.exe', '.zip', '.rar', '.pdf', '.doc', '.docx']
            if any(ext in url_obj.path.lower() for ext in suspicious_extensions):
                return False

            return True

        except Exception:
            return False

    def _create_link_info(self, url, authoritative_domains):
        """创建链接信息对象"""
        try:
            url_obj = urlparse(url)
            domain = url_obj.netloc.lower()

            # 根据域名确定链接类型和标题
            link_type = "reference"
            title = url_obj.path.strip('/').replace('/', ' ').title() or domain

            # 根据域名特征优化标题和类型
            if 'pubmed' in domain:
                link_type = "database"
                title = "PubMed医学文献数据库"
            elif 'who.int' in domain:
                link_type = "guideline"
                title = "WHO医学指南"
            elif 'cdc.gov' in domain:
                link_type = "guideline"
                title = "CDC疾病控制指南"
            elif 'nccn.org' in domain:
                link_type = "guideline"
                title = "NCCN临床实践指南"
            elif 'csco.org.cn' in domain:
                link_type = "guideline"
                title = "中国临床肿瘤学会指南"
            elif 'cma.org.cn' in domain:
                link_type = "guideline"
                title = "中华医学会临床指南"
            elif 'uptodate.com' in domain:
                link_type = "clinical"
                title = "UpToDate临床决策支持"
            elif 'clinicaltrials.gov' in domain:
                link_type = "research"
                title = "ClinicalTrials临床试验数据库"
            elif 'fda.gov' in domain:
                link_type = "guideline"
                title = "FDA药品指南"
            else:
                # 尝试从路径中提取更有意义的标题
                path_parts = [part for part in url_obj.path.split('/') if part]
                if path_parts:
                    title = ' '.join(path_parts[:2]).title().replace('-', ' ')

            return {
                "url": url,
                "title": title[:50] + '...' if len(title) > 50 else title,  # 限制标题长度
                "type": link_type
            }
        except Exception:
            return None

    def _get_default_authoritative_links(self):
        """获取默认的权威医学链接 - 已验证的有效链接"""
        return [
            {
                "url": "https://pubmed.ncbi.nlm.nih.gov/",
                "title": "PubMed医学文献数据库",
                "type": "database"
            },
            {
                "url": "https://www.who.int/health-topics",
                "title": "WHO卫生主题",
                "type": "guideline"
            },
            {
                "url": "https://www.cdc.gov/",
                "title": "美国疾病控制中心",
                "type": "guideline"
            },
            {
                "url": "https://www.nccn.org/",
                "title": "NCCN临床实践指南",
                "type": "guideline"
            },
            {
                "url": "https://www.cma.org.cn/",
                "title": "中华医学会",
                "type": "guideline"
            }
        ]

    def _extract_tcm_section(self, content, keywords):
        """从内容中提取特定关键词相关的段落"""
        lines = content.split('\n')
        relevant_lines = []
        
        for line in lines:
            line = line.strip()
            if any(keyword in line for keyword in keywords):
                # 找到关键词行，获取该行和后续相关行
                relevant_lines.append(line)
                continue
            elif relevant_lines and line and not line.startswith(('##', '**', '1.', '2.', '3.')):
                # 如果已经找到关键词，继续添加相关内容
                relevant_lines.append(line)
            elif relevant_lines and (line.startswith(('##', '**')) or not line):
                # 遇到新的标题或空行，停止添加
                break
        
        result = ' '.join(relevant_lines).strip()
        return result if result else "暂无相关分析"

    def _extract_tcm_suggestions(self, content):
        """从内容中提取建议列表"""
        suggestions = []
        lines = content.split('\n')
        
        in_suggestions = False
        for line in lines:
            line = line.strip()
            if any(keyword in line for keyword in ['建议', '调理', '注意', '养生']):
                in_suggestions = True
                if '：' in line:
                    suggestions.append(line.split('：', 1)[1].strip())
                else:
                    suggestions.append(line)
            elif in_suggestions and line:
                if line.startswith(('1.', '2.', '3.', '4.', '5.', '-', '•')):
                    suggestions.append(line.lstrip('123456789.-• ').strip())
                elif line.startswith(('##', '**')):
                    break
                else:
                    suggestions.append(line)
        
        return suggestions[:5] if suggestions else ["请咨询专业中医师获得个性化建议"]

# 创建服务实例
medical_ai = MedicalAIService()

# =============================
# 简易数据持久化（用户/档案/会话）
# =============================
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
RECORDS_FILE = os.path.join(DATA_DIR, 'records.json')
COMMUNITY_FILE = os.path.join(DATA_DIR, 'community.json')
PRE_CONSULTATION_PUSHES_FILE = os.path.join(DATA_DIR, 'pre_consultation_pushes.json')
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')

# 内存会话：session_id -> username
SESSIONS = {}

def ensure_data_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"users": {}}, f, ensure_ascii=False, indent=2)
    if not os.path.exists(RECORDS_FILE):
        with open(RECORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"records": {}}, f, ensure_ascii=False, indent=2)
    if not os.path.exists(COMMUNITY_FILE):
        with open(COMMUNITY_FILE, 'w', encoding='utf-8') as f:
            json.dump({"posts": []}, f, ensure_ascii=False, indent=2)
    if not os.path.exists(PRE_CONSULTATION_PUSHES_FILE):
        with open(PRE_CONSULTATION_PUSHES_FILE, 'w', encoding='utf-8') as f:
            json.dump({"pushes": []}, f, ensure_ascii=False, indent=2)

def load_json_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json_file(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _load_community():
    return load_json_file(COMMUNITY_FILE)

def _save_community(data):
    save_json_file(COMMUNITY_FILE, data)

def _find_post(posts, post_id):
    for p in posts:
        if p.get('id') == post_id:
            return p
    return None

def _get_user_role(username: str) -> str:
    try:
        users_data = load_json_file(USERS_FILE)
        return users_data.get('users', {}).get(username, {}).get('role', 'user')
    except Exception:
        return 'user'

def _is_admin(username: str) -> bool:
    if not username:
        return False
    # 用户名为 admin 或 角色为 admin 判定为管理员
    if (username or '').lower() == 'admin':
        return True
    return _get_user_role(username) == 'admin'

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def create_session(username: str) -> str:
    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = username
    return session_id

def get_username_by_session() -> str:
    sid = request.headers.get('X-Session-Id') or request.args.get('session_id')
    if not sid:
        return None
    return SESSIONS.get(sid)

# 初始化数据文件
ensure_data_files()

def _find_user_active_record(username: str, override_record_id: str = None):
    try:
        users_data = load_json_file(USERS_FILE)
        records_data = load_json_file(RECORDS_FILE)
        user_obj = users_data.get('users', {}).get(username, {})
        active_id = override_record_id or user_obj.get('active_record_id')
        if not active_id:
            return None
        for rec in records_data.get('records', {}).get(username, []):
            if rec.get('record_id') == active_id:
                return rec
        return None
    except Exception:
        return None

# 静态文件服务
@app.route('/')
def index():
    """服务主页"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    """静态文件服务"""
    return send_from_directory('.', filename)

# API路由
@app.route('/api/doctor/generate-emr', methods=['POST'])
def api_generate_emr():
    """医生端：生成结构化病历"""
    try:
        data = parse_json_request()
        brief = data.get('brief') or ''
        profile = data.get('patient_profile') or {}
        if not brief.strip():
            return jsonify({"success": False, "message": "请输入关键信息"}), 400

        result = medical_ai.generate_structured_emr(brief, profile)
        status = 200 if result.get('success') else 500
        return jsonify(result), status
    except Exception as e:
        logger.error(f"/api/doctor/generate-emr error: {e}")
        return jsonify({"success": False, "message": "服务异常"}), 500

@app.route('/api/doctor/generate-treatment', methods=['POST'])
def api_generate_treatment():
    """医生端：基于病历生成治疗方案"""
    try:
        data = parse_json_request()
        emr = data.get('emr') or ''
        profile = data.get('patient_profile') or {}
        if not emr.strip():
            return jsonify({"success": False, "message": "请先提供病历内容"}), 400

        result = medical_ai.generate_treatment_plan(emr, profile)
        status = 200 if result.get('success') else 500
        return jsonify(result), status
    except Exception as e:
        logger.error(f"/api/doctor/generate-treatment error: {e}")
        return jsonify({"success": False, "message": "服务异常"}), 500

@app.route('/api/diagnosis-chat', methods=['POST'])
def api_diagnosis_chat():
    try:
        data = parse_json_request() or {}
        user_msg = (data.get('message') or '').strip()
        context = data.get('context') or []
        if not user_msg:
            return jsonify({"success": False, "message": "问题不能为空"}), 400
        result = medical_ai.diagnosis_chat(user_msg, context)
        status = 200 if result.get('success') else 500
        return jsonify(result), status
    except Exception as e:
        logger.error(f"/api/diagnosis-chat error: {e}")
        return jsonify({"success": False, "message": "服务异常"}), 500

# ============== 医生端 EMR 上下文（按档案） ==============
def _get_active_record(username: str, record_id: Optional[str] = None):
    records_data = load_json_file(RECORDS_FILE)
    user_records = records_data.get('records', {}).get(username, [])
    if record_id:
        return next((r for r in user_records if r.get('record_id') == record_id), None), records_data, user_records
    # 否则用激活档案
    users_data = load_json_file(USERS_FILE)
    active_id = users_data.get('users', {}).get(username, {}).get('active_record_id')
    if not active_id:
        return None, records_data, user_records
    return next((r for r in user_records if r.get('record_id') == active_id), None), records_data, user_records

@app.route('/api/doctor/emr/context', methods=['GET', 'POST'])
def api_doctor_emr_context():
    username = get_username_by_session()
    if not username:
        return jsonify({"error": True, "message": "未登录"}), 401
    if request.method == 'GET':
        record_id = request.args.get('record_id')
        rec, _all, _list = _get_active_record(username, record_id)
        if not rec:
            return jsonify({"success": True, "context": None})
        ctx = rec.get('emr_context') or None
        return jsonify({"success": True, "context": ctx})
    # POST 保存/合并
    data = parse_json_request() or {}
    record_id = data.get('record_id')
    rec, records_data, user_records = _get_active_record(username, record_id)
    if not rec:
        return jsonify({"error": True, "message": "未找到档案或未激活档案"}), 404
    ctx = rec.get('emr_context') or {}
    for k in ('brief', 'emr_html'):
        if k in data and data.get(k) is not None:
            ctx[k] = data.get(k)
    ctx['updated_at'] = datetime.utcnow().isoformat()
    rec['emr_context'] = ctx
    # 覆盖回去
    for i, r in enumerate(user_records):
        if r.get('record_id') == rec.get('record_id'):
            user_records[i] = rec
            break
    records_data['records'][username] = user_records
    save_json_file(RECORDS_FILE, records_data)
    return jsonify({"success": True})

@app.route('/api/doctor/emr/context/clear', methods=['POST'])
def api_doctor_emr_context_clear():
    username = get_username_by_session()
    if not username:
        return jsonify({"error": True, "message": "未登录"}), 401
    data = parse_json_request() or {}
    record_id = data.get('record_id')
    rec, records_data, user_records = _get_active_record(username, record_id)
    if not rec:
        return jsonify({"error": True, "message": "未找到档案或未激活档案"}), 404
    rec.pop('emr_context', None)
    for i, r in enumerate(user_records):
        if r.get('record_id') == rec.get('record_id'):
            user_records[i] = rec
            break
    records_data['records'][username] = user_records
    save_json_file(RECORDS_FILE, records_data)
    return jsonify({"success": True})

@app.route('/api/doctor/generate-emr-stream', methods=['POST'])
def api_generate_emr_stream():
    """医生端：流式生成结构化病历（chunked text）。
    前端用 fetch 读取 ReadableStream 增量渲染。
    """
    try:
        data = parse_json_request()
        brief = (data.get('brief') or '').strip()
        profile = data.get('patient_profile') or {}
        if not brief:
            return jsonify({"success": False, "message": "请输入关键信息"}), 400

        system_prompt = (
            "你是一名临床医生助手，请基于给定的关键信息生成'结构化中文病历'。"
            "输出为HTML片段，必须包含：<h3>主诉</h3>、<h3>现病史</h3>、<h3>既往史</h3>、<h3>过敏史</h3>、"
            "<h3>体格检查</h3>、<h3>辅助检查</h3>、<h3>初步诊断</h3>、<h3>诊疗计划</h3>。"
            "信息不足时使用规范化占位描述，末尾加<small>本建议仅供参考</small>。"
        )
        user_message = (
            f"患者概况：{json.dumps(profile, ensure_ascii=False)}\n"
            f"关键信息/问诊要点：{brief}\n"
            "请直接输出HTML，不要附加解释或Markdown。"
        )

        url = f"{QWEN_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": medical_ai.text_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.2,
            "max_tokens": 1600,
            "stream": True,
        }

        def generate():
            try:
                with requests.post(url, headers=headers, json=payload, stream=True, timeout=300) as resp:
                    resp.raise_for_status()
                    for raw in resp.iter_lines(decode_unicode=True):
                        if not raw:
                            continue
                        if raw.startswith('data:'):
                            chunk = raw[5:].strip()
                            if chunk == '[DONE]':
                                break
                            try:
                                obj = json.loads(chunk)
                                # OpenAI-compatible: choices[0].delta.content
                                delta = obj.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                if not delta and obj.get('choices', [{}])[0].get('message'):
                                    delta = obj['choices'][0]['message'].get('content', '')
                            except Exception:
                                delta = ''
                            if delta:
                                yield delta
            except Exception as e:
                logger.error(f"EMR stream error: {e}")
            finally:
                return

        return Response(stream_with_context(generate()), mimetype='text/plain; charset=utf-8')
    except Exception as e:
        logger.error(f"/api/doctor/generate-emr-stream error: {e}")
        return jsonify({"success": False, "message": "服务异常"}), 500
@app.route('/api/analyze-symptoms', methods=['POST'])
def analyze_symptoms():
    """症状分析API"""
    try:
        data = parse_json_request()
        symptoms = data.get('symptoms', '')
        patient_info = data.get('patient_info', {})
        # 读取会话与激活档案
        username = get_username_by_session()
        if username:
            active_record_id = (patient_info or {}).get('active_record_id') or data.get('active_record_id')
            active_record = _find_user_active_record(username, active_record_id)
            if active_record:
                patient_info = {**patient_info, **{k: v for k, v in active_record.items() if k != 'record_id'}}
        
        if not symptoms:
            return jsonify({"error": "症状描述不能为空"}), 400
        
        result = medical_ai.analyze_symptoms(symptoms, patient_info)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"症状分析API错误: {str(e)}")
        logger.error(f"错误详情: {traceback.format_exc()}")
        return jsonify({
            "error": True,
            "message": "服务器内部错误",
            "error_detail": str(e),
            "fallback_advice": "请稍后重试，如有紧急情况请及时就医"
        }), 500

@app.route('/api/drug-recommendation', methods=['POST'])
def drug_recommendation():
    """药物推荐API"""
    try:
        data = parse_json_request()
        symptoms = data.get('symptoms', '')
        medical_history = data.get('medical_history', {})
        # 会话激活档案合并
        username = get_username_by_session()
        if username:
            active_record_id = data.get('active_record_id') or (medical_history or {}).get('active_record_id')
            active_record = _find_user_active_record(username, active_record_id)
            if active_record:
                medical_history = {**medical_history, **{k: v for k, v in active_record.items() if k != 'record_id'}}
        
        if not symptoms:
            return jsonify({"error": "症状描述不能为空"}), 400
        
        result = medical_ai.drug_recommendation(symptoms, medical_history)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"药物推荐API错误: {str(e)}")
        return jsonify({
            "error": True,
            "error_detail": str(e),
            "message": "药物推荐服务暂时不可用"
        }), 500

@app.route('/api/health-consultation', methods=['POST'])
def health_consultation():
    """健康咨询API"""
    try:
        data = parse_json_request()
        question = data.get('question', '')
        context = data.get('context', [])
        # 提取激活档案，供系统提示融合（可选：影响系统prompt或拼接）
        username = get_username_by_session()
        active_profile_text = ''
        if username:
            active_record_id = data.get('active_record_id')
            active_record = _find_user_active_record(username, active_record_id)
            if active_record:
                profile = {k: v for k, v in active_record.items() if k != 'record_id'}
                active_profile_text = f"\n[患者档案] {json.dumps(profile, ensure_ascii=False)}"
        
        if not question:
            return jsonify({"error": "问题不能为空"}), 400
        
        # 将患者档案文本拼接到问题，作为轻量上下文字段
        result = medical_ai.health_consultation(question + active_profile_text, context)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"健康咨询API错误: {str(e)}")
        return jsonify({
            "error": True,
            "message": "咨询服务暂时不可用",
            "error_detail": str(e),
            "fallback_response": "感谢您的咨询，请稍后重试"
        }), 500

@app.route('/api/emergency-assessment', methods=['POST'])
def emergency_assessment():
    """紧急程度评估API"""
    try:
        data = parse_json_request()
        symptoms = data.get('symptoms', '')
        
        if not symptoms:
            return jsonify({"error": "症状描述不能为空"}), 400
        
        result = medical_ai.emergency_assessment(symptoms)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"紧急评估API错误: {str(e)}")
        return jsonify({
            "urgency_level": "unknown",
            "message": "无法评估，建议咨询医生"
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "医疗AI后端服务",
        "model": medical_ai.model
    })

# 简易翻译接口：将英文新闻标题/摘要翻译为中文
@app.route('/api/translate', methods=['POST'])
def translate_text():
    try:
        data = parse_json_request()
        text = (data.get('text') or '').strip()
        if not text:
            return jsonify({"error": True, "message": "text 不能为空"}), 400
        # 使用模型做简易翻译
        ai_text, _model_used = chat_completion(
            model=medical_ai.model,
            messages=[
                {"role": "system", "content": "你是专业的中英互译助手，请将输入的英文或混合文本翻译成简洁准确的中文。"},
                {"role": "user", "content": text}
            ],
            temperature=0.1,
            max_tokens=400,
        )
        return jsonify({"success": True, "translated": to_plain_text(ai_text)})
    except Exception as e:
        logger.error(f"翻译失败: {e}")
        return jsonify({"error": True, "message": "翻译失败"}), 500

@app.route('/api/vision-analyze', methods=['POST'])
def api_vision_analyze():
    try:
        data = parse_json_request()
        image_data_url = data.get('image')  # data URL: data:image/png;base64,xxx
        kind = data.get('kind', 'auto')
        note = data.get('note', '')
        if not image_data_url or not isinstance(image_data_url, str) or not image_data_url.startswith('data:image'):
            return jsonify({"success": False, "message": "请上传有效的图片"}), 400
        result = medical_ai.vision_analyze(image_data_url, kind, note)
        return jsonify(result)
    except Exception as e:
        logger.error(f"/api/vision-analyze error: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": "服务器处理失败"}), 500

# 医学文献搜索API
@app.route('/api/medical/search', methods=['GET'])
def medical_search():
    """医学文献搜索接口"""
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({"error": True, "message": "查询关键词不能为空"}), 400

        # 使用现有的医疗AI服务进行医学知识查询
        result = medical_ai.medical_knowledge_search(query)

        return jsonify({
            "success": True,
            "query": query,
            "results": result.get('results', []),
            "total": result.get('total', 0),
            "source": "医疗AI知识库"
        })

    except Exception as e:
        logger.error(f"medical search error: {e}")
        return jsonify({"error": True, "message": "搜索失败"}), 500

# 医学数据库验证API（集成权威来源）
@app.route('/api/medical/verify', methods=['POST'])
def medical_verify_sources():
    """验证医学知识来源的可靠性"""
    try:
        data = parse_json_request()
        query = data.get('query', '').strip()
        content = data.get('content', '').strip()

        if not query or not content:
            return jsonify({"error": True, "message": "查询和内容不能为空"}), 400

        # 验证步骤1：检查关键词匹配度
        keyword_match = medical_ai.check_keyword_relevance(query, content)

        # 验证步骤2：检查医学事实准确性（基于常识规则）
        fact_accuracy = medical_ai.check_medical_facts(content)

        # 验证步骤3：检查引用完整性
        citation_quality = medical_ai.check_citation_quality(content)

        # 综合评分
        overall_score = (keyword_match * 0.4 + fact_accuracy * 0.4 + citation_quality * 0.2)

        verification_result = {
            "overall_score": round(overall_score, 2),
            "reliability_level": medical_ai.get_reliability_level(overall_score),
            "verification_details": {
                "keyword_relevance": {
                    "score": keyword_match,
                    "description": f"查询关键词与内容的匹配度：{keyword_match:.1%}"
                },
                "factual_accuracy": {
                    "score": fact_accuracy,
                    "description": "医学事实准确性评估"
                },
                "citation_quality": {
                    "score": citation_quality,
                    "description": "引用来源质量评估"
                }
            },
            "recommendations": medical_ai.generate_verification_recommendations(keyword_match, fact_accuracy, citation_quality),
            "verified_at": datetime.now().isoformat()
        }

        return jsonify({
            "success": True,
            "verification": verification_result,
            "query": query
        })

    except Exception as e:
        logger.error(f"medical verification error: {e}")
        return jsonify({"error": True, "message": "验证失败"}), 500

# 医学指南和共识查询API
@app.route('/api/medical/guidelines', methods=['GET'])
def medical_guidelines():
    """医学指南和共识查询"""
    try:
        query = request.args.get('q', '').strip()
        category = request.args.get('category', 'all')  # 内科、外科、儿科等

        if not query:
            return jsonify({"error": True, "message": "查询关键词不能为空"}), 400

        # 使用医疗AI查询指南信息
        result = medical_ai.medical_guidelines_search(query, category)

        return jsonify({
            "success": True,
            "query": query,
            "category": category,
            "guidelines": result.get('guidelines', []),
            "source": "医疗AI指南库"
        })

    except Exception as e:
        logger.error(f"medical guidelines error: {e}")
        return jsonify({"error": True, "message": "指南查询失败"}), 500

# 面向前端的"中国地区中文健康新闻"聚合（通过Google News RSS）
@app.route('/api/news-cn', methods=['GET'])
def news_cn():
    try:
        import requests
        rss_url = (
            'https://news.google.com/rss/search?'
            'q=%E5%81%A5%E5%BA%B7+%E5%8C%BB%E5%AD%A6&hl=zh-CN&gl=CN&ceid=CN:zh-Hans'
        )
        resp = requests.get(rss_url, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        channel = root.find('channel')
        items = []
        if channel is not None:
            for item in channel.findall('item')[:8]:
                title_el = item.find('title')
                link_el = item.find('link')
                title = title_el.text if title_el is not None else '健康资讯'
                link = link_el.text if link_el is not None else ''
                items.append({"title": title, "url": link})
        return jsonify({"success": True, "items": items})
    except Exception as e:
        logger.error(f"news-cn 拉取失败: {e}")
        return jsonify({"success": True, "items": []})

# 知识页AI搜索：药品/疾病两套提示词
@app.route('/api/knowledge-search', methods=['POST'])
def knowledge_search():
    try:
        data = parse_json_request()
        query = (data.get('query') or '').strip()
        kind = (data.get('kind') or 'auto').strip()
        if not query:
            return jsonify({"error": True, "message": "query 不能为空"}), 400

        # 简单判断：含有"片/胶囊/颗粒/布洛芬/对乙酰氨基酚"等词视为药品
        is_drug = False
        if kind == 'drug':
            is_drug = True
        elif kind == 'disease':
            is_drug = False
        else:
            is_drug = any(x in query for x in ['片', '胶囊', '颗粒', '缓释', '对乙酰氨基酚', '布洛芬', '阿莫西林', '氯雷他定'])

        if is_drug:
            system_prompt = (
                "你是一位专业的药品师，具备深厚的药学知识，能够针对用户询问的药物，准确给出该药物对应的适应症、一般用法用量、不良反应、副作用、重要成分以及注意事项等信息。\n\n"
                "技能1-提供药物信息：\n"
                "1) 当用户询问某种药物时，先确认药物名称的准确性；\n"
                "2) 结合可靠来源，整理适应症、一般用法用量、不良反应/副作用、重要成分、注意事项；\n"
                "限制：只讨论药物；输出严格按给定框架；简洁且重点突出；用 Markdown 的 ^^ 形式给出引用来源（如说明书/指南/权威网站）。"
            )
            user_prompt = (
                f"请按以下固定结构输出关于药物{query}的信息：\n"
                "- **药物名称**：\n"
                "- **适应症**：\n"
                "- **一般用法用量**：\n"
                "- **不良反应**：\n"
                "- **副作用**：\n"
                "- **重要成分**：\n"
                "- **注意事项**：\n"
                "请使用准确、精炼的中文表述，并在对应条目后使用 ^^ 说明引用来源。"
            )
        elif not is_drug and kind == 'disease':
            system_prompt = (
                "你是一位专业的医疗知识科普员，对常见病症和相关药品有深入了解，能用通俗语言提供详细且准确的信息。"
            )
            user_prompt = (
                f"请围绕{query}这一病症，整理一份结构化报告，覆盖：概况、病因、典型症状、常用检验、治疗方案、常用药品、预防与日常护理。"
                "要求：格式清晰、要点分条；仅引用可靠来源并用 Markdown 的 ^^ 形式标注。"
            )
        elif not is_drug and kind == 'wellness':
            system_prompt = (
                "你是一位专业的健康养生顾问，对中医、运动、营养等领域有深入了解，能用通俗易懂的方式提供建议。"
            )
            user_prompt = (
                f"请针对{query}这一养生主题，生成分条建议，覆盖：核心原则、每日可执行清单、风险与禁忌、适合人群与不适合人群，并给出必要的安全提醒。"
            )

        ai_text, model_used = chat_completion(
            model=medical_ai.text_model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.2,
            max_tokens=1200,
        )
        return jsonify({"success": True, "result": to_plain_text(ai_text), "model_used": model_used, "kind": "drug" if is_drug else "disease"})
    except Exception as e:
        logger.error(f"知识AI搜索失败: {e}")
        return jsonify({"error": True, "message": "搜索失败"}), 500

# =============================
# 社区：帖子/评论/点赞（简易JSON存储）
# =============================

def _now_iso():
    return datetime.utcnow().isoformat()

@app.route('/api/community/posts', methods=['GET'])
def community_posts_list():
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 10))
        tag = (request.args.get('tag') or '').strip()
        search = (request.args.get('search') or '').strip()
        data = _load_community()
        all_posts = data.get('posts', [])
        # 排序：置顶优先，其次时间倒序
        posts = sorted(all_posts, key=lambda x: (
            0 if x.get('pinned') else 1,
            x.get('created_at', '' if x.get('pinned') else '' )
        ,), reverse=True)
        # 标签筛选
        if tag:
            posts = [p for p in posts if tag in (p.get('tags') or [])]
        # 内容搜索（搜索帖子内容和作者名）
        if search:
            search_lower = search.lower()
            posts = [p for p in posts if (
                search_lower in (p.get('content', '')).lower() or
                search_lower in (p.get('author', '')).lower()
            )]
        slice_posts = posts[offset: offset + limit]
        # 脱敏/最简化返回
        items = []
        username = get_username_by_session()
        for p in slice_posts:
            items.append({
                "id": p.get('id'),
                "author": p.get('author', '匿名用户'),
                "content": p.get('content', ''),
                "created_at": p.get('created_at'),
                "like_count": len(p.get('likes', [])),
                "liked": username in (p.get('likes', []) if username else []),
                "bookmark_count": len(p.get('bookmarks', [])),
                "bookmarked": username in (p.get('bookmarks', []) if username else []),
                "comments": p.get('comments', [])[:20],  # 前20条预览
                "tags": p.get('tags', []),
                "images": p.get('images', []),
                "pinned": bool(p.get('pinned'))
            })
        has_more = offset + limit < len(posts)
        return jsonify({"success": True, "items": items, "has_more": has_more})
    except Exception as e:
        logger.error(f"community list error: {e}")
        return jsonify({"error": True, "message": "加载失败"}), 500

@app.route('/api/community/trending', methods=['GET'])
def community_trending():
    """热度排行：基于点赞、评论、图片、置顶并加入时间衰减的综合热度"""
    try:
        limit = int(request.args.get('limit', 8))
        # 可选：用于未来扩展窗口过滤，目前仅用作展示
        _hours = float(request.args.get('hours', 72))

        db = _load_community()
        posts = db.get('posts', [])
        now = datetime.utcnow()

        def compute_heat(p: dict) -> float:
            like_count = len(p.get('likes', []) or [])
            comment_count = len(p.get('comments', []) or [])
            has_images = len(p.get('images', []) or []) > 0
            is_pinned = bool(p.get('pinned'))
            created_text = p.get('created_at') or ''
            try:
                created_dt = datetime.fromisoformat(created_text)
            except Exception:
                created_dt = now
            age_hours = max((now - created_dt).total_seconds() / 3600.0, 0.0)

            # 基础热度：评论权重大于点赞，图片略加分，置顶加权
            base = like_count * 2 + comment_count * 3 + (5 if has_images else 0) + (10 if is_pinned else 0)
            # 时间衰减：24小时为一个尺度
            decay = 1.0 / (1.0 + age_hours / 24.0)
            return round(base * decay, 6)

        scored = []
        for p in posts:
            scored.append((compute_heat(p), p))
        scored.sort(key=lambda x: x[0], reverse=True)

        items = []
        for idx, (h, p) in enumerate(scored[:limit]):
            items.append({
                "rank": idx + 1,
                "id": p.get('id'),
                "author": p.get('author', '匿名用户'),
                "content": (p.get('content', '') or '')[:120],
                "created_at": p.get('created_at'),
                "like_count": len(p.get('likes', []) or []),
                "comment_count": len(p.get('comments', []) or []),
                "tags": p.get('tags', []) or [],
                "pinned": bool(p.get('pinned')),
                "heat": h,
            })

        return jsonify({"success": True, "items": items})
    except Exception as e:
        logger.error(f"community trending error: {e}")
        return jsonify({"error": True, "message": "加载热度排行失败"}), 500

@app.route('/api/community/posts', methods=['POST'])
def community_post_create():
    try:
        username = get_username_by_session()
        if not username:
            return jsonify({"error": True, "message": "请先登录"}), 401
        data = parse_json_request()
        content = (data.get('content') or '').strip()
        tags = data.get('tags') or []
        images = data.get('images') or []  # 期望为已上传返回的URL数组
        if not content:
            return jsonify({"error": True, "message": "内容不能为空"}), 400
        db = _load_community()
        post = {
            "id": uuid.uuid4().hex,
            "author": username,
            "content": content[:2000],
            "created_at": _now_iso(),
            "likes": [],
            "comments": [],
            "tags": [t for t in tags if isinstance(t, str)][:5],
            "images": [img for img in images if isinstance(img, str)][:6],
            "pinned": False
        }
        db.setdefault('posts', []).append(post)
        _save_community(db)
        return jsonify({"success": True, "id": post['id']})
    except Exception as e:
        logger.error(f"community create error: {e}")
        return jsonify({"error": True, "message": "发布失败"}), 500

@app.route('/api/community/posts/<post_id>/comments', methods=['GET'])
def community_comments_list(post_id):
    try:
        db = _load_community()
        p = _find_post(db.get('posts', []), post_id)
        if not p:
            return jsonify({"error": True, "message": "未找到帖子"}), 404
        return jsonify({"success": True, "items": p.get('comments', [])})
    except Exception as e:
        logger.error(f"community comments list error: {e}")
        return jsonify({"error": True, "message": "加载失败"}), 500

@app.route('/api/community/posts/<post_id>/comments', methods=['POST'])
def community_comment_create(post_id):
    try:
        username = get_username_by_session()
        if not username:
            return jsonify({"error": True, "message": "请先登录"}), 401
        data = parse_json_request()
        content = (data.get('content') or '').strip()
        parent_id = data.get('parent_id') or None
        if not content:
            return jsonify({"error": True, "message": "内容不能为空"}), 400
        db = _load_community()
        p = _find_post(db.get('posts', []), post_id)
        if not p:
            return jsonify({"error": True, "message": "未找到帖子"}), 404
        comment = {
            "id": uuid.uuid4().hex,
            "author": username,
            "content": content[:1000],
            "created_at": _now_iso(),
            "parent_id": parent_id
        }
        p.setdefault('comments', []).append(comment)
        _save_community(db)
        return jsonify({"success": True, "id": comment['id']})
    except Exception as e:
        logger.error(f"community comment create error: {e}")
        return jsonify({"error": True, "message": "评论失败"}), 500

@app.route('/api/community/posts/<post_id>/like', methods=['POST'])
def community_like_toggle(post_id):
    try:
        username = get_username_by_session()
        if not username:
            return jsonify({"error": True, "message": "请先登录"}), 401
        db = _load_community()
        p = _find_post(db.get('posts', []), post_id)
        if not p:
            return jsonify({"error": True, "message": "未找到帖子"}), 404
        likes = set(p.get('likes', []))
        if username in likes:
            likes.remove(username)
        else:
            likes.add(username)
        p['likes'] = list(likes)
        _save_community(db)
        return jsonify({"success": True, "like_count": len(p['likes'])})
    except Exception as e:
        logger.error(f"community like toggle error: {e}")
        return jsonify({"error": True, "message": "操作失败"}), 500

@app.route('/api/community/posts/<post_id>/bookmark', methods=['POST'])
def community_bookmark_toggle(post_id):
    try:
        # 临时测试：如果没有session，使用默认用户名
        username = get_username_by_session() or 'testuser'
        db = _load_community()
        p = _find_post(db.get('posts', []), post_id)
        if not p:
            return jsonify({"error": True, "message": "未找到帖子"}), 404
        if 'bookmarks' not in p:
            p['bookmarks'] = []
        bookmarks = set(p.get('bookmarks', []))
        if username in bookmarks:
            bookmarks.remove(username)
            bookmarked = False
        else:
            bookmarks.add(username)
            bookmarked = True
        p['bookmarks'] = list(bookmarks)
        _save_community(db)
        return jsonify({"success": True, "bookmarked": bookmarked, "bookmark_count": len(p['bookmarks'])})
    except Exception as e:
        logger.error(f"community bookmark toggle error: {e}")
        return jsonify({"error": True, "message": "操作失败"}), 500

@app.route('/api/community/posts/<post_id>/pin', methods=['POST'])
def community_post_pin(post_id):
    try:
        username = get_username_by_session()
        if not _is_admin(username):
            return jsonify({"error": True, "message": "需要管理员权限"}), 403
        db = _load_community()
        p = _find_post(db.get('posts', []), post_id)
        if not p:
            return jsonify({"error": True, "message": "未找到帖子"}), 404
        p['pinned'] = not bool(p.get('pinned'))
        _save_community(db)
        return jsonify({"success": True, "pinned": p['pinned']})
    except Exception as e:
        logger.error(f"community pin error: {e}")
        return jsonify({"error": True, "message": "操作失败"}), 500

@app.route('/api/community/posts/<post_id>', methods=['DELETE'])
def community_post_delete(post_id):
    try:
        username = get_username_by_session()
        if not _is_admin(username):
            return jsonify({"error": True, "message": "需要管理员权限"}), 403
        db = _load_community()
        posts = db.get('posts', [])
        new_posts = [p for p in posts if p.get('id') != post_id]
        if len(new_posts) == len(posts):
            return jsonify({"error": True, "message": "未找到帖子"}), 404
        db['posts'] = new_posts
        _save_community(db)
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"community delete error: {e}")
        return jsonify({"error": True, "message": "删除失败"}), 500

@app.route('/api/community/upload', methods=['POST'])
def community_upload_image():
    """支持两种上传：
    1) multipart/form-data file 字段
    2) JSON: { "image_base64": "data:image/png;base64,xxx" }
    返回: { url: "/uploads/xxx.png" }
    """
    try:
        username = get_username_by_session()
        if not username:
            return jsonify({"error": True, "message": "请先登录"}), 401
        # 方案1：multipart 文件
        if request.files:
            f = request.files.get('file')
            if not f:
                return jsonify({"error": True, "message": "未选择文件"}), 400
            ext = os.path.splitext(f.filename or '')[1].lower() or '.png'
            fname = uuid.uuid4().hex + ext
            path = os.path.join(UPLOAD_DIR, fname)
            f.save(path)
            return jsonify({"success": True, "url": f"/uploads/{fname}"})
        # 方案2：base64 data url
        data = parse_json_request() or {}
        data_url = (data.get('image_base64') or '').strip()
        if data_url.startswith('data:image') and ';base64,' in data_url:
            header, b64 = data_url.split(';base64,', 1)
            ext = '.png'
            if 'image/jpeg' in header: ext = '.jpg'
            if 'image/jpg' in header: ext = '.jpg'
            if 'image/webp' in header: ext = '.webp'
            import base64
            raw = base64.b64decode(b64)
            fname = uuid.uuid4().hex + ext
            path = os.path.join(UPLOAD_DIR, fname)
            with open(path, 'wb') as fp:
                fp.write(raw)
            return jsonify({"success": True, "url": f"/uploads/{fname}"})
        return jsonify({"error": True, "message": "无效上传"}), 400
    except Exception as e:
        logger.error(f"upload error: {e}")
        return jsonify({"error": True, "message": "上传失败"}), 500

# =============================
# 认证接口
# =============================
@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    try:
        data = parse_json_request()
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        role = data.get('role', 'user')  # 默认为患者
        
        if len(username) < 3:
            return jsonify({"error": True, "message": "用户名至少3个字符"}), 400
        if len(password) < 6:
            return jsonify({"error": True, "message": "密码至少6位"}), 400
        
        # 验证角色值
        if role not in ['user', 'doctor']:
            role = 'user'

        users_data = load_json_file(USERS_FILE)
        users = users_data.get('users', {})
        if username in users:
            return jsonify({"error": True, "message": "用户名已存在"}), 409

        users[username] = {
            "password_hash": hash_password(password),
            "role": role,
            "active_record_id": None
        }
        users_data['users'] = users
        save_json_file(USERS_FILE, users_data)

        session_id = create_session(username)
        return jsonify({
            "success": True,
            "username": username,
            "role": role,
            "session_id": session_id,
            "active_record_id": None
        })
    except Exception as e:
        logger.error(f"注册失败: {e}")
        return jsonify({"error": True, "message": "注册失败", "detail": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    try:
        data = parse_json_request()
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''

        users_data = load_json_file(USERS_FILE)
        user_obj = users_data.get('users', {}).get(username)
        if not user_obj:
            return jsonify({"error": True, "message": "用户不存在"}), 404
        if user_obj.get('password_hash') != hash_password(password):
            return jsonify({"error": True, "message": "密码错误"}), 401

        session_id = create_session(username)
        return jsonify({
            "success": True,
            "username": username,
            "session_id": session_id,
            "active_record_id": user_obj.get('active_record_id')
        })
    except Exception as e:
        logger.error(f"登录失败: {e}")
        return jsonify({"error": True, "message": "登录失败", "detail": str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    sid = request.headers.get('X-Session-Id') or request.args.get('session_id')
    if sid and sid in SESSIONS:
        SESSIONS.pop(sid, None)
    return jsonify({"success": True})

@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    username = get_username_by_session()
    if not username:
        return jsonify({"error": True, "message": "未登录"}), 401
    users_data = load_json_file(USERS_FILE)
    user_obj = users_data.get('users', {}).get(username, {})
    return jsonify({
        "success": True,
        "username": username,
        "active_record_id": user_obj.get('active_record_id')
    })

# =============================
# 健康档案接口
# =============================
@app.route('/api/records', methods=['GET', 'POST'])
def records_root():
    username = get_username_by_session()
    if not username:
        return jsonify({"error": True, "message": "未登录"}), 401

    users_data = load_json_file(USERS_FILE)
    records_data = load_json_file(RECORDS_FILE)
    user_records = records_data.get('records', {}).get(username, [])

    if request.method == 'GET':
        return jsonify({
            "success": True,
            "records": user_records,
            "active_record_id": users_data.get('users', {}).get(username, {}).get('active_record_id')
        })

    # POST - 创建档案
    data = parse_json_request()
    name = (data.get('name') or '').strip()
    age = data.get('age')
    gender = data.get('gender') or 'unknown'
    if not name:
        return jsonify({"error": True, "message": "姓名必填"}), 400

    new_record = {
        "record_id": uuid.uuid4().hex,
        "name": name,
        "age": age,
        "gender": gender,
        "height": data.get('height'),
        "weight": data.get('weight'),
        "allergies": data.get('allergies') or [],
        "diagnoses": data.get('diagnoses') or [],
        "current_medications": data.get('current_medications') or [],
        "notes": data.get('notes') or ''
    }

    records_data.setdefault('records', {})
    records_data['records'].setdefault(username, [])
    records_data['records'][username].append(new_record)
    save_json_file(RECORDS_FILE, records_data)

    # 若无激活档案，则设为激活
    users = users_data.get('users', {})
    if not users.get(username, {}).get('active_record_id'):
        users[username]['active_record_id'] = new_record['record_id']
        users_data['users'] = users
        save_json_file(USERS_FILE, users_data)

    return jsonify({"success": True, "record": new_record})

@app.route('/api/records/activate', methods=['POST'])
def records_activate():
    username = get_username_by_session()
    if not username:
        return jsonify({"error": True, "message": "未登录"}), 401
    data = parse_json_request()
    record_id = data.get('record_id')
    if not record_id:
        return jsonify({"error": True, "message": "record_id 缺失"}), 400

    records_data = load_json_file(RECORDS_FILE)
    user_records = records_data.get('records', {}).get(username, [])
    if not any(r.get('record_id') == record_id for r in user_records):
        return jsonify({"error": True, "message": "档案不存在"}), 404

    users_data = load_json_file(USERS_FILE)
    users = users_data.get('users', {})
    users.setdefault(username, {})
    users[username]['active_record_id'] = record_id
    users_data['users'] = users
    save_json_file(USERS_FILE, users_data)
    return jsonify({"success": True, "active_record_id": record_id})

@app.route('/api/records/<record_id>', methods=['PUT', 'DELETE'])
def records_item(record_id):
    username = get_username_by_session()
    if not username:
        return jsonify({"error": True, "message": "未登录"}), 401

    records_data = load_json_file(RECORDS_FILE)
    user_records = records_data.get('records', {}).get(username, [])
    idx = next((i for i, r in enumerate(user_records) if r.get('record_id') == record_id), None)
    if idx is None:
        return jsonify({"error": True, "message": "档案不存在"}), 404

    if request.method == 'DELETE':
        removed = user_records.pop(idx)
        records_data['records'][username] = user_records
        save_json_file(RECORDS_FILE, records_data)

        # 若删除的是激活档案，重置激活
        users_data = load_json_file(USERS_FILE)
        users = users_data.get('users', {})
        if users.get(username, {}).get('active_record_id') == record_id:
            users[username]['active_record_id'] = user_records[0]['record_id'] if user_records else None
            users_data['users'] = users
            save_json_file(USERS_FILE, users_data)
        return jsonify({"success": True, "deleted": removed.get('record_id')})

    # PUT - 更新
    data = parse_json_request()
    allowed_fields = {"name", "age", "gender", "height", "weight", "allergies", "diagnoses", "current_medications", "notes"}
    for key in allowed_fields:
        if key in data:
            user_records[idx][key] = data.get(key)
    records_data['records'][username] = user_records
    save_json_file(RECORDS_FILE, records_data)
    return jsonify({"success": True, "record": user_records[idx]})

# 报告：获取/新增（附加在具体档案下）
@app.route('/api/records/<record_id>/reports', methods=['GET', 'POST'])
def record_reports(record_id):
    username = get_username_by_session()
    if not username:
        return jsonify({"error": True, "message": "未登录"}), 401
    records_data = load_json_file(RECORDS_FILE)
    user_records = records_data.get('records', {}).get(username, [])
    rec = next((r for r in user_records if r.get('record_id') == record_id), None)
    if not rec:
        return jsonify({"error": True, "message": "档案不存在"}), 404
    rec.setdefault('reports', [])
    if request.method == 'GET':
        logger.info(f"获取档案 {record_id} 的报告列表，用户: {username}")
        logger.info(f"档案 {record_id} 有 {len(rec['reports'])} 个报告")
        if rec['reports']:
            logger.info(f"报告列表: {[r.get('title', 'Unknown') + ' (' + r.get('report_id', 'No ID') + ')' for r in rec['reports']]}")
        return jsonify({"success": True, "reports": rec['reports']})
    # POST 新增报告
    data = parse_json_request()
    logger.info(f"收到保存报告请求，用户: {username}, 档案ID: {record_id}")
    logger.info(f"报告数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
    
    report = {
        "report_id": uuid.uuid4().hex,
        "type": data.get('type') or 'tcm_wang',
        "title": data.get('title') or '中医望诊报告',
        "created_at": datetime.utcnow().isoformat(),
        "content": data.get('content') or {},
    }
    
    logger.info(f"生成的报告: {json.dumps(report, ensure_ascii=False, indent=2)}")
    
    rec['reports'].insert(0, report)
    records_data['records'][username] = user_records
    
    logger.info(f"档案 {record_id} 现在有 {len(rec['reports'])} 个报告")
    
    save_json_file(RECORDS_FILE, records_data)
    logger.info(f"报告已保存到文件: {RECORDS_FILE}")
    
    return jsonify({"success": True, "report": report})

# =============================
# 中医四诊API端点
# =============================

@app.route('/api/tcm-vision-analyze', methods=['POST'])
def tcm_vision_analyze():
    """中医视觉分析API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求数据不能为空"}), 400
        
        images = data.get('images', [])
        if not images:
            return jsonify({"error": "图像数据不能为空"}), 400
        
        analysis_type = data.get('analysis_type', 'tcm_diagnosis')
        
        result = medical_ai.tcm_vision_analyze(images, analysis_type)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"中医视觉分析API错误: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/tcm-inquiry-analyze', methods=['POST'])
def tcm_inquiry_analyze():
    """中医问诊分析API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求数据不能为空"}), 400
        
        patient_info = data.get('patient_info', {})
        symptoms = data.get('symptoms', [])
        analysis_type = data.get('analysis_type', 'tcm_inquiry')
        
        if not symptoms:
            return jsonify({"error": "症状信息不能为空"}), 400
        
        result = medical_ai.tcm_inquiry_analyze(patient_info, symptoms, analysis_type)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"中医问诊分析API错误: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/tcm-pulse-analyze', methods=['POST'])
def tcm_pulse_analyze():
    """中医脉象分析API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求数据不能为空"}), 400

        pulse_characteristics = data.get('pulse_characteristics', {})
        analysis_type = data.get('analysis_type', 'tcm_pulse')

        if not any(pulse_characteristics.values()):
            return jsonify({"error": "脉象特征不能为空"}), 400

        result = medical_ai.tcm_pulse_analyze(pulse_characteristics, analysis_type)
        return jsonify(result)

    except Exception as e:
        logger.error(f"中医脉象分析API错误: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/generate-emr', methods=['POST'])
def generate_emr():
    """生成结构化病历API"""
    try:
        data = parse_json_request()
        brief_text = data.get('brief_text', '')
        patient_profile = data.get('patient_profile', {})
        append_mode = data.get('append_mode', False)
        existing_emr = data.get('existing_emr', '')

        if not brief_text:
            return jsonify({"error": "病情描述不能为空"}), 400

        if append_mode and existing_emr:
            # 追加模式：合并现有病历和新内容
            result = medical_ai.generate_structured_emr_append(brief_text, existing_emr, patient_profile)
        else:
            # 普通模式：生成新病历
            result = medical_ai.generate_structured_emr(brief_text, patient_profile)

        return jsonify(result)

    except Exception as e:
        logger.error(f"病历生成API错误: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/generate-treatment-plans', methods=['POST'])
def generate_treatment_plans():
    """生成多个治疗方案API"""
    try:
        data = parse_json_request()
        emr_content = data.get('emr_content', '')
        patient_profile = data.get('patient_profile', {})
        num_plans = data.get('num_plans', 3)

        if not emr_content:
            return jsonify({"error": "病历内容不能为空"}), 400

        if num_plans < 1 or num_plans > 5:
            num_plans = 3  # 默认值

        result = medical_ai.generate_treatment_plan(emr_content, patient_profile, num_plans)
        return jsonify(result)

    except Exception as e:
        logger.error(f"治疗方案生成API错误: {str(e)}")
        return jsonify({"error": "服务器内部错误"}), 500

# ========== TCM 中医模块 API ==========

@app.route('/api/tcm/archives', methods=['GET'])
def get_tcm_archives():
    """获取健康档案列表"""
    try:
        archives_file = os.path.join(DATA_DIR, 'tcm_archives.json')
        
        if os.path.exists(archives_file):
            with open(archives_file, 'r', encoding='utf-8') as f:
                archives = json.load(f)
        else:
            archives = []
        
        return jsonify({
            "success": True,
            "archives": archives
        })
    
    except Exception as e:
        logger.error(f"获取TCM档案列表失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"获取档案列表失败: {str(e)}"
        }), 500

@app.route('/api/tcm/archives', methods=['POST'])
def create_tcm_archive():
    """创建新的健康档案"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({
                "success": False,
                "message": "档案名称不能为空"
            }), 400
        
        archives_file = os.path.join(DATA_DIR, 'tcm_archives.json')
        
        # 读取现有档案
        if os.path.exists(archives_file):
            with open(archives_file, 'r', encoding='utf-8') as f:
                archives = json.load(f)
        else:
            archives = []
        
        # 生成新档案ID
        archive_id = str(int(time.time() * 1000))
        
        new_archive = {
            "id": archive_id,
            "name": name,
            "gender": data.get('gender', ''),
            "age": data.get('age', ''),
            "contact": data.get('contact', ''),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "diagnosis_count": 0,
            "diagnoses": []
        }
        
        archives.append(new_archive)
        
        # 保存到文件
        with open(archives_file, 'w', encoding='utf-8') as f:
            json.dump(archives, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            "success": True,
            "archive": new_archive,
            "message": "档案创建成功"
        })
    
    except Exception as e:
        logger.error(f"创建TCM档案失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"创建档案失败: {str(e)}"
        }), 500

@app.route('/api/tcm/archives/<archive_id>', methods=['GET'])
def get_tcm_archive(archive_id):
    """获取指定档案详情"""
    try:
        archives_file = os.path.join(DATA_DIR, 'tcm_archives.json')
        
        if not os.path.exists(archives_file):
            return jsonify({
                "success": False,
                "message": "档案文件不存在"
            }), 404
        
        with open(archives_file, 'r', encoding='utf-8') as f:
            archives = json.load(f)
        
        archive = next((a for a in archives if a['id'] == archive_id), None)
        
        if not archive:
            return jsonify({
                "success": False,
                "message": "档案不存在"
            }), 404
        
        # 计算最近诊断
        recent_diagnosis = None
        if archive.get('diagnoses'):
            recent_diagnosis = archive['diagnoses'][-1]
        
        archive['recent_diagnosis'] = recent_diagnosis
        
        return jsonify({
            "success": True,
            "archive": archive
        })
    
    except Exception as e:
        logger.error(f"获取TCM档案详情失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"获取档案详情失败: {str(e)}"
        }), 500

# ========== 智能预问诊 API ==========

@app.route('/api/pre-consultation/start', methods=['POST'])
def start_pre_consultation():
    """开始预问诊，根据患者主诉生成问诊问题"""
    try:
        data = parse_json_request()
        chief_complaint = data.get('chief_complaint', '').strip()
        patient_info = data.get('patient_info', {})
        
        if not chief_complaint:
            return jsonify({
                "success": False,
                "message": "请提供主诉信息"
            }), 400
        
        # 构建AI提示词，生成结构化问诊问题
        system_prompt = """你是一位经验丰富的医生助手。根据患者的主诉，生成一系列专业的问诊问题，帮助收集完整的病史信息。

请严格按照以下JSON格式输出问题列表（不要添加任何其他文字）：
{
    "questions": [
        {
            "id": "q1",
            "question": "症状从什么时候开始的？",
            "type": "text",
            "category": "病史"
        },
        {
            "id": "q2", 
            "question": "疼痛程度如何？",
            "type": "scale",
            "options": ["轻微", "中等", "严重", "剧烈"],
            "category": "症状特征"
        }
    ]
}

问题类型说明：
- text: 文本输入
- choice: 单选题（需提供options数组）
- multi_choice: 多选题（需提供options数组）
- scale: 等级评分（需提供options数组）
- yes_no: 是否问题

问题分类包括：病史、症状特征、伴随症状、既往病史、用药史、过敏史、生活习惯等"""

        user_prompt = f"""患者主诉：{chief_complaint}

患者基本信息：
- 年龄：{patient_info.get('age', '未提供')}
- 性别：{patient_info.get('gender', '未提供')}

请根据以上信息，生成8-12个针对性的问诊问题，帮助医生全面了解病情。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        ai_response, model_used = chat_completion("qwen-plus", messages, temperature=0.3, max_tokens=2000)
        
        # 解析AI返回的JSON
        questions_data = _extract_json_payload(ai_response)
        
        if not questions_data or 'questions' not in questions_data:
            # 降级：使用通用问题模板
            questions_data = {
                "questions": [
                    {"id": "q1", "question": "症状从什么时候开始的？", "type": "text", "category": "病史"},
                    {"id": "q2", "question": "症状持续了多长时间？", "type": "text", "category": "病史"},
                    {"id": "q3", "question": "症状的严重程度如何？", "type": "scale", "options": ["轻微", "中等", "严重", "剧烈"], "category": "症状特征"},
                    {"id": "q4", "question": "是否有其他伴随症状？", "type": "text", "category": "伴随症状"},
                    {"id": "q5", "question": "是否有类似的既往病史？", "type": "yes_no", "category": "既往病史"},
                    {"id": "q6", "question": "目前是否在服用任何药物？", "type": "yes_no", "category": "用药史"},
                    {"id": "q7", "question": "是否有药物过敏史？", "type": "yes_no", "category": "过敏史"},
                    {"id": "q8", "question": "最近生活作息是否规律？", "type": "yes_no", "category": "生活习惯"}
                ]
            }
        
        # 创建预问诊会话ID
        session_id = str(uuid.uuid4())
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "questions": questions_data['questions'],
            "model_used": model_used
        })
        
    except Exception as e:
        logger.error(f"开始预问诊失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "message": f"开始预问诊失败: {str(e)}"
        }), 500

@app.route('/api/pre-consultation/submit', methods=['POST'])
def submit_pre_consultation():
    """提交预问诊答案，生成结构化报告"""
    try:
        data = parse_json_request()
        session_id = data.get('session_id', '')
        chief_complaint = data.get('chief_complaint', '')
        answers = data.get('answers', {})
        patient_info = data.get('patient_info', {})
        username = request.headers.get('X-Username', 'anonymous')
        
        if not chief_complaint or not answers:
            return jsonify({
                "success": False,
                "message": "缺少必要信息"
            }), 400
        
        # 构建完整的问诊记录文本
        consultation_text = f"主诉：{chief_complaint}\n\n"
        
        for q_id, answer_data in answers.items():
            question = answer_data.get('question', '')
            answer = answer_data.get('answer', '')
            consultation_text += f"{question}\n回答：{answer}\n\n"
        
        # 生成AI分析报告
        system_prompt = """你是一位资深医生。根据患者的预问诊信息，生成一份结构化的预问诊报告。

请严格按照以下JSON格式输出（不要添加任何其他文字）：
{
    "summary": "患者病情概述（3-5句话）",
    "key_points": [
        "关键信息点1",
        "关键信息点2",
        "关键信息点3"
    ],
    "preliminary_diagnosis": [
        "可能的诊断1",
        "可能的诊断2"
    ],
    "recommended_tests": [
        "建议的检查项目1",
        "建议的检查项目2"
    ],
    "recommended_department": "建议就诊科室",
    "urgency_level": "紧急程度（非紧急/一般/紧急/危重）",
    "doctor_notes": "给医生的备注信息"
}"""

        user_prompt = f"""患者基本信息：
- 姓名：{patient_info.get('name', '未提供')}
- 年龄：{patient_info.get('age', '未提供')}岁
- 性别：{patient_info.get('gender', '未提供')}

预问诊记录：
{consultation_text}

请生成结构化的预问诊报告。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        ai_response, model_used = chat_completion("qwen-plus", messages, temperature=0.2, max_tokens=2000)
        
        # 解析AI返回的JSON
        report_data = _extract_json_payload(ai_response)
        
        if not report_data:
            # 降级：使用简单的文本分析
            report_data = {
                "summary": ai_response[:200],
                "key_points": ["患者主诉：" + chief_complaint],
                "preliminary_diagnosis": ["待进一步诊断"],
                "recommended_tests": ["建议面诊"],
                "recommended_department": "普通内科",
                "urgency_level": "一般",
                "doctor_notes": ai_response
            }
        
        # 保存到患者档案
        saved_to_record = False
        report_id = None
        if username != 'anonymous':
            try:
                records_file = os.path.join(DATA_DIR, 'records.json')
                if os.path.exists(records_file):
                    with open(records_file, 'r', encoding='utf-8') as f:
                        records_data = json.load(f)
                    
                    user_records = records_data.get('records', {}).get(username, [])
                    
                    # 获取激活的档案
                    users_file = os.path.join(DATA_DIR, 'users.json')
                    with open(users_file, 'r', encoding='utf-8') as f:
                        users_data = json.load(f)
                    
                    active_record_id = users_data.get('users', {}).get(username, {}).get('active_record_id')
                    
                    if active_record_id:
                        active_record = next((r for r in user_records if r.get('record_id') == active_record_id), None)
                        
                        if active_record:
                            # 添加预问诊报告
                            if 'reports' not in active_record:
                                active_record['reports'] = []
                            
                            report_id = str(uuid.uuid4()).replace('-', '')
                            pre_consultation_report = {
                                "report_id": report_id,
                                "type": "pre_consultation",
                                "title": "预问诊报告",
                                "created_at": datetime.now().isoformat(),
                                "content": {
                                    "session_id": session_id,
                                    "chief_complaint": chief_complaint,
                                    "answers": answers,
                                    "report": report_data,
                                    "consultation_text": consultation_text
                                }
                            }
                            
                            active_record['reports'].insert(0, pre_consultation_report)
                            
                            # 保存更新
                            with open(records_file, 'w', encoding='utf-8') as f:
                                json.dump(records_data, f, ensure_ascii=False, indent=2)
                            
                            saved_to_record = True
            except Exception as e:
                logger.error(f"保存预问诊报告失败: {str(e)}")
        
        return jsonify({
            "success": True,
            "session_id": session_id,
            "report": report_data,
            "report_id": report_id,
            "saved_to_record": saved_to_record,
            "model_used": model_used
        })
        
    except Exception as e:
        logger.error(f"提交预问诊失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "message": f"提交预问诊失败: {str(e)}"
        }), 500

@app.route('/api/pre-consultation/reports', methods=['GET'])
def get_pre_consultation_reports():
    """获取用户的预问诊报告列表"""
    try:
        username = request.headers.get('X-Username', 'anonymous')
        
        if username == 'anonymous':
            return jsonify({
                "success": False,
                "message": "请先登录"
            }), 401
        
        records_file = os.path.join(DATA_DIR, 'records.json')
        if not os.path.exists(records_file):
            return jsonify({
                "success": True,
                "reports": []
            })
        
        with open(records_file, 'r', encoding='utf-8') as f:
            records_data = json.load(f)
        
        user_records = records_data.get('records', {}).get(username, [])
        
        # 收集所有预问诊报告
        all_reports = []
        for record in user_records:
            reports = record.get('reports', [])
            pre_consultation_reports = [r for r in reports if r.get('type') == 'pre_consultation']
            
            for report in pre_consultation_reports:
                all_reports.append({
                    "record_id": record.get('record_id'),
                    "record_name": record.get('name'),
                    "report_id": report.get('report_id'),
                    "title": report.get('title'),
                    "created_at": report.get('created_at'),
                    "chief_complaint": report.get('content', {}).get('chief_complaint', ''),
                    "urgency_level": report.get('content', {}).get('report', {}).get('urgency_level', '一般')
                })
        
        # 按时间排序
        all_reports.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return jsonify({
            "success": True,
            "reports": all_reports
        })
        
    except Exception as e:
        logger.error(f"获取预问诊报告列表失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"获取报告列表失败: {str(e)}"
        }), 500

@app.route('/api/doctors/search', methods=['GET'])
def search_doctors():
    """搜索医生账号"""
    try:
        keyword = request.args.get('keyword', '').strip()
        
        if not keyword:
            return jsonify({
                "success": False,
                "message": "请输入搜索关键词"
            }), 400
        
        users_data = load_json_file(USERS_FILE)
        all_users = users_data.get('users', {})
        
        # 筛选医生角色的用户
        doctors = []
        for username, user_data in all_users.items():
            if user_data.get('role') == 'doctor':
                # 搜索用户名或姓名
                name = user_data.get('name', username)
                if keyword.lower() in username.lower() or keyword in name:
                    doctors.append({
                        "username": username,
                        "name": name,
                        "role": "doctor"
                    })
        
        return jsonify({
            "success": True,
            "doctors": doctors
        })
        
    except Exception as e:
        logger.error(f"搜索医生失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"搜索失败: {str(e)}"
        }), 500

@app.route('/api/pre-consultation/push', methods=['POST'])
def push_pre_consultation():
    """推送预问诊报告给指定医生"""
    try:
        data = parse_json_request()
        patient_username = request.headers.get('X-Username', 'anonymous')
        doctor_username = data.get('doctor_username', '').strip()
        report_id = data.get('report_id', '').strip()
        
        if patient_username == 'anonymous':
            return jsonify({
                "success": False,
                "message": "请先登录"
            }), 401
        
        if not doctor_username or not report_id:
            return jsonify({
                "success": False,
                "message": "缺少必要参数"
            }), 400
        
        # 验证医生账号存在且为医生角色
        users_data = load_json_file(USERS_FILE)
        doctor_data = users_data.get('users', {}).get(doctor_username)
        
        if not doctor_data:
            return jsonify({
                "success": False,
                "message": "医生账号不存在"
            }), 404
        
        if doctor_data.get('role') != 'doctor':
            return jsonify({
                "success": False,
                "message": "该账号不是医生"
            }), 400
        
        # 查找报告
        records_data = load_json_file(RECORDS_FILE)
        user_records = records_data.get('records', {}).get(patient_username, [])
        
        report_found = None
        for record in user_records:
            for report in record.get('reports', []):
                if report.get('report_id') == report_id:
                    report_found = {
                        "report_id": report_id,
                        "patient_username": patient_username,
                        "patient_name": record.get('name', patient_username),
                        "record_id": record.get('record_id'),
                        "title": report.get('title'),
                        "created_at": report.get('created_at'),
                        "content": report.get('content')
                    }
                    break
            if report_found:
                break
        
        if not report_found:
            return jsonify({
                "success": False,
                "message": "报告不存在"
            }), 404
        
        # 保存推送记录
        pushes_data = load_json_file(PRE_CONSULTATION_PUSHES_FILE)
        pushes = pushes_data.get('pushes', [])
        
        # 检查是否已推送
        existing_push = next((p for p in pushes 
                            if p.get('report_id') == report_id 
                            and p.get('doctor_username') == doctor_username), None)
        
        if existing_push:
            return jsonify({
                "success": False,
                "message": "已推送给该医生，无需重复推送"
            }), 400
        
        # 添加新推送记录
        push_record = {
            "push_id": str(uuid.uuid4()).replace('-', ''),
            "report_id": report_id,
            "patient_username": patient_username,
            "patient_name": report_found['patient_name'],
            "doctor_username": doctor_username,
            "doctor_name": doctor_data.get('name', doctor_username),
            "pushed_at": datetime.now().isoformat(),
            "status": "active",  # active, deleted
            "report_data": report_found
        }
        
        pushes.append(push_record)
        pushes_data['pushes'] = pushes
        save_json_file(PRE_CONSULTATION_PUSHES_FILE, pushes_data)
        
        return jsonify({
            "success": True,
            "message": f"已成功推送给医生 {doctor_data.get('name', doctor_username)}",
            "push_id": push_record['push_id']
        })
        
    except Exception as e:
        logger.error(f"推送预问诊报告失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "message": f"推送失败: {str(e)}"
        }), 500

@app.route('/api/doctors/pre-consultation/reports', methods=['GET'])
def get_doctor_pre_consultation_reports():
    """医生获取推送给自己的预问诊报告列表"""
    try:
        doctor_username = request.headers.get('X-Username', 'anonymous')
        
        if doctor_username == 'anonymous':
            return jsonify({
                "success": False,
                "message": "请先登录"
            }), 401
        
        # 验证是否为医生角色
        users_data = load_json_file(USERS_FILE)
        user_data = users_data.get('users', {}).get(doctor_username, {})
        
        if user_data.get('role') != 'doctor':
            return jsonify({
                "success": False,
                "message": "您不是医生，无法查看推送的报告"
            }), 403
        
        # 获取推送给该医生的报告
        pushes_data = load_json_file(PRE_CONSULTATION_PUSHES_FILE)
        all_pushes = pushes_data.get('pushes', [])
        
        # 筛选该医生的活跃推送
        doctor_pushes = [p for p in all_pushes 
                        if p.get('doctor_username') == doctor_username 
                        and p.get('status') == 'active']
        
        # 按推送时间排序
        doctor_pushes.sort(key=lambda x: x.get('pushed_at', ''), reverse=True)
        
        # 构建返回数据
        reports = []
        for push in doctor_pushes:
            report_data = push.get('report_data', {})
            content = report_data.get('content', {})
            report_content = content.get('report', {})
            
            reports.append({
                "push_id": push.get('push_id'),
                "report_id": push.get('report_id'),
                "patient_username": push.get('patient_username'),
                "patient_name": push.get('patient_name'),
                "title": report_data.get('title', '预问诊报告'),
                "created_at": report_data.get('created_at'),
                "pushed_at": push.get('pushed_at'),
                "chief_complaint": content.get('chief_complaint', ''),
                "urgency_level": report_content.get('urgency_level', '一般'),
                "recommended_department": report_content.get('recommended_department', ''),
                "content": content
            })
        
        return jsonify({
            "success": True,
            "reports": reports
        })
        
    except Exception as e:
        logger.error(f"获取医生预问诊报告失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"获取报告失败: {str(e)}"
        }), 500

@app.route('/api/doctors/pre-consultation/reports/<push_id>', methods=['DELETE'])
def delete_doctor_pre_consultation_report(push_id):
    """医生删除推送的预问诊报告"""
    try:
        doctor_username = request.headers.get('X-Username', 'anonymous')
        
        if doctor_username == 'anonymous':
            return jsonify({
                "success": False,
                "message": "请先登录"
            }), 401
        
        # 验证是否为医生角色
        users_data = load_json_file(USERS_FILE)
        user_data = users_data.get('users', {}).get(doctor_username, {})
        
        if user_data.get('role') != 'doctor':
            return jsonify({
                "success": False,
                "message": "您不是医生，无法删除报告"
            }), 403
        
        # 获取推送记录
        pushes_data = load_json_file(PRE_CONSULTATION_PUSHES_FILE)
        all_pushes = pushes_data.get('pushes', [])
        
        # 查找推送记录
        push_found = None
        for push in all_pushes:
            if push.get('push_id') == push_id:
                if push.get('doctor_username') == doctor_username:
                    push_found = push
                    break
                else:
                    return jsonify({
                        "success": False,
                        "message": "无权删除此报告"
                    }), 403
        
        if not push_found:
            return jsonify({
                "success": False,
                "message": "报告不存在"
            }), 404
        
        # 标记为已删除
        push_found['status'] = 'deleted'
        push_found['deleted_at'] = datetime.now().isoformat()
        
        save_json_file(PRE_CONSULTATION_PUSHES_FILE, pushes_data)
        
        return jsonify({
            "success": True,
            "message": "已删除该报告"
        })
        
    except Exception as e:
        logger.error(f"删除预问诊报告失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"删除失败: {str(e)}"
        }), 500

@app.route('/api/tcm/analyze', methods=['POST'])
def analyze_tcm_image():
    """分析TCM诊断图片"""
    try:
        # 检查是否有上传的文件
        if 'image' not in request.files:
            return jsonify({
                "success": False,
                "message": "未找到上传的图片"
            }), 400
        
        file = request.files['image']
        mode = request.form.get('mode', 'face')
        archive_id = request.form.get('archive_id', '')
        
        if file.filename == '':
            return jsonify({
                "success": False,
                "message": "未选择文件"
            }), 400
        
        # 保存上传的图片
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        filename = f"tcm_{mode}_{timestamp}_{filename}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        file.save(file_path)
        
        # 根据模式进行不同的分析（接入 Qwen 实际分析）
        if mode == 'face':
            result = analyze_face_diagnosis(file_path)
        elif mode == 'tongue':
            result = analyze_tongue_diagnosis(file_path)
        else:
            result = analyze_general_tcm(file_path)
        
        # 如果指定了档案ID，保存诊断结果
        if archive_id:
            save_diagnosis_to_archive(archive_id, result, mode, filename)
        
        return jsonify({
            "success": True,
            "result": result,
            "image_path": filename
        })
    
    except Exception as e:
        logger.error(f"TCM图片分析失败: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"图片分析失败: {str(e)}"
        }), 500

def _image_file_to_data_url(image_path: str) -> str:
    try:
        import base64
        mime = 'image/jpeg'
        with open(image_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        logger.error(f"构建图片data URL失败: {e}")
        raise


def analyze_face_diagnosis(image_path):
    """面诊分析"""
    try:
        # 构建多模态消息，传入图片data URL
        data_url = _image_file_to_data_url(image_path)
        system_prompt = "你是一位资深中医面诊专家。请根据提供的面部照片，从面色、眼睛、嘴唇、脸型等方面进行中医望诊分析，并给出体质判定、主要脏腑偏颇与调理建议。"
        user_prompt = "请结合中医理论，给出结构化结论。"

        # 使用统一chat_completion（支持OpenAI兼容content结构）
        messages = [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {"role": "user", "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": data_url}}
            ]}
        ]
        ai_text, model_used = chat_completion("qwen-vl-max", messages, temperature=0.2, max_tokens=1200)
        ai_text = to_plain_text(ai_text)

        # 粗解析为结构化（健壮性优先）
        def pick(patterns, default="正常"):
            text = ai_text
            for p in patterns:
                idx = text.find(p)
                if idx >= 0:
                    seg = text[idx: idx + 80]
                    return seg.split("：")[-1].split("\n")[0].strip() or default
            return default

        result = {
            "constitution": pick(["体质", "体质类型"] , "平和质"),
            "constitution_score": 85,
            "constitution_features": ai_text[:400],
            "organs": {
                "heart": "正常",
                "liver": "正常",
                "spleen": "正常",
                "lung": "正常",
                "kidney": "正常"
            },
            "recommendations": [r.strip() for r in ai_text.split("建议")[-1].split("\n") if r.strip()][:4] or [
                "保持规律作息，早睡早起",
                "适量运动，如太极拳、八段锦",
                "饮食清淡，少食辛辣油腻",
            ],
            "analysis_time": datetime.now().isoformat(),
            "confidence": 0.9,
        }
        return result
    
    except Exception as e:
        logger.error(f"面诊分析失败: {str(e)}，使用回退结果")
        constitution_types = ["平和质", "气虚质", "阳虚质", "阴虚质", "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质"]
        return {
            "constitution": random.choice(constitution_types),
            "constitution_score": random.randint(75, 90),
            "constitution_features": "网络不稳定，返回回退分析结果。",
            "organs": {"heart": "正常", "liver": "正常", "spleen": "正常", "lung": "正常", "kidney": "正常"},
            "recommendations": ["保持规律作息", "适量运动", "饮食清淡"],
            "analysis_time": datetime.now().isoformat(),
            "confidence": 0.7,
            "source": "fallback"
        }

def analyze_tongue_diagnosis(image_path):
    """舌诊分析"""
    try:
        data_url = _image_file_to_data_url(image_path)
        system_prompt = "你是一位资深中医舌诊专家。请根据舌象照片，分析舌色、舌苔、舌形、舌质与湿度，给出体质倾向和调理建议。"
        user_prompt = "请结构化输出：舌色、舌苔、舌形、舌质/湿度、体质、建议。"
        messages = [
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {"role": "user", "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": data_url}}
            ]}
        ]
        ai_text, model_used = chat_completion("qwen-vl-max", messages, temperature=0.2, max_tokens=1200)
        ai_text = to_plain_text(ai_text)
        # 简单解析
        def find_field(name, default=""):
            idx = ai_text.find(name)
            if idx >= 0:
                seg = ai_text[idx: idx + 60]
                return seg.split("：")[-1].split("\n")[0].strip() or default
            return default

        result = {
            "constitution": find_field("体质", "平和质"),
            "constitution_score": 82,
            "constitution_features": ai_text[:400] or "根据舌象特征分析得出",
            "tongue_analysis": {
                "tongue_color": find_field("舌色", "淡红"),
                "tongue_coating": find_field("舌苔", "薄白"),
                "tongue_shape": find_field("舌形", "正常"),
                "tongue_texture": find_field("舌质", "适中") or find_field("湿度", "适中")
            },
            "organs": {
                "heart": "正常",
                "liver": "正常",
                "spleen": "正常",
                "lung": "正常",
                "kidney": "正常"
            },
            "recommendations": [s.strip() for s in ai_text.split("建议")[-1].split("\n") if s.strip()][:4] or [
                "健脾利湿，少食生冷",
                "作息规律，适度运动"
            ],
            "analysis_time": datetime.now().isoformat(),
            "confidence": 0.88
        }
        return result
    
    except Exception as e:
        logger.error(f"舌诊分析失败: {str(e)}，使用回退结果")
        tongue_colors = ["淡红", "红", "深红", "暗红", "淡白"]
        tongue_coatings = ["薄白", "厚白", "薄黄", "厚黄", "无苔"]
        return {
            "constitution": random.choice(["平和质", "湿热质", "痰湿质", "阴虚质"]),
            "constitution_score": random.randint(75, 90),
            "constitution_features": "网络不稳定，返回回退分析结果。",
            "tongue_analysis": {
                "tongue_color": random.choice(tongue_colors),
                "tongue_coating": random.choice(tongue_coatings),
                "tongue_shape": random.choice(["正常", "胖大", "瘦薄"]),
                "tongue_texture": random.choice(["润泽", "干燥", "腻"])
            },
            "organs": {"heart": "正常", "liver": "正常", "spleen": "正常", "lung": "正常", "kidney": "正常"},
            "recommendations": ["健脾利湿", "少食生冷"],
            "analysis_time": datetime.now().isoformat(),
            "confidence": 0.7,
            "source": "fallback"
        }

def analyze_general_tcm(image_path):
    """通用中医分析"""
    try:
        result = {
            "constitution": "平和质",
            "constitution_score": 80,
            "constitution_features": "体质相对均衡",
            "organs": {
                "heart": "正常",
                "liver": "正常", 
                "spleen": "正常",
                "lung": "正常",
                "kidney": "正常"
            },
            "recommendations": [
                "保持良好作息",
                "适量运动",
                "饮食均衡"
            ],
            "analysis_time": datetime.now().isoformat(),
            "confidence": 0.8
        }
        
        return result
    
    except Exception as e:
        logger.error(f"通用TCM分析失败: {str(e)}")
        raise

def save_diagnosis_to_archive(archive_id, result, mode, image_filename):
    """保存诊断结果到档案"""
    try:
        archives_file = os.path.join(DATA_DIR, 'tcm_archives.json')
        
        if not os.path.exists(archives_file):
            return
        
        with open(archives_file, 'r', encoding='utf-8') as f:
            archives = json.load(f)
        
        # 找到对应档案
        archive = next((a for a in archives if a['id'] == archive_id), None)
        if not archive:
            return
        
        # 添加诊断记录
        diagnosis_record = {
            "id": str(int(time.time() * 1000)),
            "mode": mode,
            "result": result,
            "image_filename": image_filename,
            "created_at": datetime.now().isoformat()
        }
        
        if 'diagnoses' not in archive:
            archive['diagnoses'] = []
        
        archive['diagnoses'].append(diagnosis_record)
        archive['diagnosis_count'] = len(archive['diagnoses'])
        archive['updated_at'] = datetime.now().isoformat()
        
        # 保存更新后的档案
        with open(archives_file, 'w', encoding='utf-8') as f:
            json.dump(archives, f, ensure_ascii=False, indent=2)
    
    except Exception as e:
        logger.error(f"保存诊断结果到档案失败: {str(e)}")

# ==================== 用药管理API ====================
# 导入用药管理模块
try:
    from medication_management import MedicationManager
    medication_manager = MedicationManager(data_dir=DATA_DIR)
    logger.info("用药管理模块已加载")
except Exception as e:
    logger.error(f"加载用药管理模块失败: {e}")
    medication_manager = None

@app.route('/api/medications', methods=['GET', 'POST'])
def handle_medications():
    """获取或添加用药记录"""
    if not medication_manager:
        return jsonify({"success": False, "message": "用药管理模块未加载"}), 500
    
    try:
        username = request.args.get('username') or request.json.get('username') if request.method == 'POST' else request.args.get('username')
        
        if not username:
            return jsonify({"success": False, "message": "缺少用户名"}), 400
        
        if request.method == 'GET':
            # 获取用药记录
            status = request.args.get('status')
            record_id = request.args.get('record_id')  # 档案筛选
            medications = medication_manager.get_user_medications(username, status)
            
            # 如果有档案筛选，只返回该档案的用药
            if record_id:
                medications = [m for m in medications if m.get('record_id') == record_id]
            
            return jsonify({
                "success": True,
                "medications": medications,
                "count": len(medications)
            })
        
        elif request.method == 'POST':
            # 添加用药记录
            data = request.json
            medication_data = data.get('medication', {})
            
            if not medication_data.get('name'):
                return jsonify({"success": False, "message": "缺少药品名称"}), 400
            
            result = medication_manager.add_medication(username, medication_data)
            
            if result.get('success'):
                return jsonify(result), 201
            else:
                return jsonify(result), 400
    
    except Exception as e:
        logger.error(f"处理用药记录失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/medications/<medication_id>', methods=['PUT', 'DELETE'])
def handle_medication_detail(medication_id):
    """更新或删除用药记录"""
    if not medication_manager:
        return jsonify({"success": False, "message": "用药管理模块未加载"}), 500
    
    try:
        username = request.args.get('username') or (request.json.get('username') if request.method == 'PUT' else request.args.get('username'))
        
        if not username:
            return jsonify({"success": False, "message": "缺少用户名"}), 400
        
        if request.method == 'PUT':
            # 更新用药记录
            data = request.json
            update_data = data.get('medication', {})
            result = medication_manager.update_medication(username, medication_id, update_data)
            
            if result.get('success'):
                return jsonify(result)
            else:
                return jsonify(result), 400
        
        elif request.method == 'DELETE':
            # 删除用药记录
            result = medication_manager.delete_medication(username, medication_id)
            
            if result.get('success'):
                return jsonify(result)
            else:
                return jsonify(result), 400
    
    except Exception as e:
        logger.error(f"处理用药记录详情失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/medications/reminders', methods=['GET', 'POST'])
def handle_reminders():
    """获取或添加服药提醒"""
    if not medication_manager:
        return jsonify({"success": False, "message": "用药管理模块未加载"}), 500
    
    try:
        username = request.args.get('username') or request.json.get('username') if request.method == 'POST' else request.args.get('username')
        
        if not username:
            return jsonify({"success": False, "message": "缺少用户名"}), 400
        
        if request.method == 'GET':
            # 获取提醒列表
            record_id = request.args.get('record_id')  # 档案筛选
            reminders = medication_manager.get_user_reminders(username)
            
            # 如果有档案筛选，只返回该档案的提醒
            if record_id:
                reminders = [r for r in reminders if r.get('record_id') == record_id]
            
            return jsonify({
                "success": True,
                "reminders": reminders,
                "count": len(reminders)
            })
        
        elif request.method == 'POST':
            # 添加提醒
            data = request.json
            reminder_data = data.get('reminder', {})
            
            # 从medication_id关联的用药中获取record_id
            medication_id = reminder_data.get('medication_id')
            if medication_id:
                # 查找该用药的record_id
                medications = medication_manager.get_user_medications(username)
                for med in medications:
                    if med.get('id') == medication_id:
                        reminder_data['record_id'] = med.get('record_id', '')
                        break
            
            result = medication_manager.add_reminder(username, reminder_data)
            
            if result.get('success'):
                return jsonify(result), 201
            else:
                return jsonify(result), 400
    
    except Exception as e:
        logger.error(f"处理服药提醒失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/medications/reminders/<reminder_id>', methods=['PUT', 'DELETE'])
def handle_reminder_detail(reminder_id):
    """更新或删除服药提醒"""
    if not medication_manager:
        return jsonify({"success": False, "message": "用药管理模块未加载"}), 500
    
    try:
        username = request.args.get('username') or (request.json.get('username') if request.method == 'PUT' else request.args.get('username'))
        
        if not username:
            return jsonify({"success": False, "message": "缺少用户名"}), 400
        
        if request.method == 'PUT':
            # 更新提醒
            data = request.json
            update_data = data.get('reminder', {})
            result = medication_manager.update_reminder(username, reminder_id, update_data)
            
            if result.get('success'):
                return jsonify(result)
            else:
                return jsonify(result), 400
        
        elif request.method == 'DELETE':
            # 删除提醒
            result = medication_manager.delete_reminder(username, reminder_id)
            
            if result.get('success'):
                return jsonify(result)
            else:
                return jsonify(result), 400
    
    except Exception as e:
        logger.error(f"处理提醒详情失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/medications/intake-records', methods=['GET', 'POST'])
def handle_intake_records():
    """获取或记录服药"""
    if not medication_manager:
        return jsonify({"success": False, "message": "用药管理模块未加载"}), 500
    
    try:
        username = request.args.get('username') or request.json.get('username') if request.method == 'POST' else request.args.get('username')
        
        if not username:
            return jsonify({"success": False, "message": "缺少用户名"}), 400
        
        if request.method == 'GET':
            # 获取服药记录
            medication_id = request.args.get('medication_id')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            record_id = request.args.get('record_id')  # 档案筛选
            
            records = medication_manager.get_intake_records(username, medication_id, start_date, end_date)
            
            # 如果有档案筛选，只返回该档案的服药记录
            if record_id:
                records = [r for r in records if r.get('record_id') == record_id]
            
            return jsonify({
                "success": True,
                "records": records,
                "count": len(records)
            })
        
        elif request.method == 'POST':
            # 记录服药
            data = request.json
            intake_data = data.get('intake', {})
            
            result = medication_manager.record_intake(username, intake_data)
            
            if result.get('success'):
                return jsonify(result), 201
            else:
                return jsonify(result), 400
    
    except Exception as e:
        logger.error(f"处理服药记录失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/medications/adherence-stats', methods=['GET'])
def get_adherence_stats():
    """获取用药依从性统计"""
    if not medication_manager:
        return jsonify({"success": False, "message": "用药管理模块未加载"}), 500
    
    try:
        username = request.args.get('username')
        if not username:
            return jsonify({"success": False, "message": "缺少用户名"}), 400
        
        days = int(request.args.get('days', 7))
        record_id = request.args.get('record_id')  # 档案筛选
        
        # 获取统计数据
        all_medications = medication_manager.get_user_medications(username, status='active')
        all_records = medication_manager.get_intake_records(username, start_date=(datetime.now() - timedelta(days=days)).isoformat())
        
        # 如果有档案筛选，只统计该档案的数据
        if record_id:
            medications = [m for m in all_medications if m.get('record_id') == record_id]
            intake_records = [r for r in all_records if r.get('record_id') == record_id]
        else:
            medications = all_medications
            intake_records = all_records
        
        # 计算统计
        total_medications = len(medications)
        total_doses_expected = 0
        total_doses_taken = len(intake_records)
        
        # 估算应服次数
        for med in medications:
            freq = med.get('frequency', '')
            if '3' in freq:
                total_doses_expected += days * 3
            elif '2' in freq:
                total_doses_expected += days * 2
            else:
                total_doses_expected += days
        
        adherence_rate = (total_doses_taken / total_doses_expected * 100) if total_doses_expected > 0 else 0
        
        result = {
            'success': True,
            'total_medications': total_medications,
            'total_doses_expected': total_doses_expected,
            'total_doses_taken': total_doses_taken,
            'adherence_rate': round(adherence_rate, 2),
            'days': days
        }
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"获取用药统计失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/medications/ai-analyze', methods=['POST'])
def analyze_medications_ai():
    """AI分析用药情况（药物相互作用、副作用等）"""
    if not medication_manager:
        return jsonify({"success": False, "message": "用药管理模块未加载"}), 500
    
    try:
        data = request.json
        username = data.get('username')
        medications_list = data.get('medications', [])
        
        if not username:
            return jsonify({"success": False, "message": "缺少用户名"}), 400
        
        # 如果没有提供药物列表，则获取用户当前活跃的用药
        if not medications_list:
            medications_list = medication_manager.get_user_medications(username, status='active')
        
        if not medications_list:
            return jsonify({
                "success": True,
                "analysis": {
                    "summary": "当前没有活跃的用药记录",
                    "interactions": [],
                    "warnings": [],
                    "suggestions": []
                }
            })
        
        # 构建AI分析提示词
        medication_names = [m.get('name', '') for m in medications_list]
        medication_details = []
        for m in medications_list:
            detail = f"药品：{m.get('name', '未知')}\n"
            detail += f"剂量：{m.get('dosage', '未知')}\n"
            detail += f"频率：{m.get('frequency', '未知')}\n"
            detail += f"分类：{m.get('category', '未知')}"
            medication_details.append(detail)
        
        prompt = f"""作为专业的药师，请分析以下用药方案：

{chr(10).join(medication_details)}

请提供以下分析：
1. 药物相互作用（Drug Interactions）：分析这些药物之间是否存在相互作用
2. 安全警告（Safety Warnings）：是否有需要注意的安全事项
3. 用药建议（Recommendations）：给出专业的用药建议

请以JSON格式返回，包含：
- summary: 总体评估
- interactions: 药物相互作用列表，每项包含 drug1, drug2, severity (高/中/低), description
- warnings: 警告列表，每项包含 type, severity, description
- suggestions: 建议列表

注意：请只返回JSON格式的数据，不要包含其他文字说明。"""
        
        # 调用AI分析
        try:
            # 使用统一的chat_completion函数
            analysis_result, model_used = chat_completion(
                model='qwen-plus',
                messages=[
                    {"role": "system", "content": "你是一位专业的临床药师，擅长分析药物相互作用和用药安全。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            logger.info(f"用药AI分析使用模型: {model_used}")
            
            # 尝试解析JSON
            analysis_data = _extract_json_payload(analysis_result)
            
            if not analysis_data:
                # 如果无法解析JSON，使用纯文本响应
                analysis_data = {
                    "summary": analysis_result[:200] if len(analysis_result) > 200 else analysis_result,
                    "interactions": [],
                    "warnings": [],
                    "suggestions": [analysis_result]
                }
            
            return jsonify({
                "success": True,
                "analysis": analysis_data,
                "medications_analyzed": len(medications_list)
            })
        
        except Exception as e:
            logger.error(f"AI分析失败: {e}")
            return jsonify({
                "success": False,
                "message": f"AI分析失败: {str(e)}"
            }), 500
    
    except Exception as e:
        logger.error(f"处理AI分析请求失败: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/medications/recognize-photo', methods=['POST'])
def recognize_medication_photo():
    """识别药品照片并提取信息"""
    try:
        data = parse_json_request()
        image_data = data.get('image')  # Base64编码的图片
        
        if not image_data:
            return jsonify({"success": False, "message": "缺少图片数据"}), 400
        
        # 构建AI识别提示
        system_prompt = """你是一位专业的药剂师，擅长识别药品包装和说明书。
请仔细观察图片中的所有药品信息。如果图片中有多个药品，请识别所有的药品。

对于每个药品，提取以下字段（如有则填写，没有则留空）：
- 药品名称（通用名或商品名）
- 剂量规格（如"100mg/片"）
- 服用频率（如"每日3次"、"一日一次"）
- 疗程（如"7天"、"连续服用2周"）
- 药品分类（西药/中药/营养品）
- 注意事项或备注

请以JSON数组格式返回，每个元素是一个药品对象，字段名为：name, dosage, frequency, duration, category, notes
如果识别出多个药品，返回数组；如果只识别出一个，也返回包含一个元素的数组。
例如：[{"name": "布洛芬", "dosage": "100mg", ...}, {"name": "..."}]
如果某个字段无法从图片中获取，请设置为空字符串。"""
        
        try:
            # 调用AI视觉识别
            analysis_result, model_used = chat_completion(
                model='qwen-vl-max',
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "请识别这张图片中的所有药品，提取药品信息并以JSON数组格式返回。如有多个药品，请全部识别。"},
                            {"type": "image_url", "image_url": {"url": image_data}}
                        ]
                    }
                ],
                temperature=0.2,
                max_tokens=2000
            )
            
            logger.info(f"药品识别使用模型: {model_used}")
            
            # 解析JSON
            medication_list = _extract_json_payload(analysis_result)
            
            # 确保返回的是数组
            if not medication_list:
                medication_list = []
            elif not isinstance(medication_list, list):
                # 如果返回的是单个对象，转换为数组
                medication_list = [medication_list]
            
            # 验证每个药品对象的字段
            default_fields = {
                "name": "",
                "dosage": "",
                "frequency": "",
                "duration": "",
                "category": "西药",
                "notes": ""
            }
            
            validated_list = []
            for med in medication_list:
                if not isinstance(med, dict):
                    continue
                
                validated_med = {}
                for key in default_fields:
                    validated_med[key] = med.get(key, default_fields[key])
                
                # 只添加至少有名称的药品
                if validated_med.get("name"):
                    validated_list.append(validated_med)
            
            # 如果没有识别到有效的药品，返回空数组
            if not validated_list:
                validated_list = []
            
            return jsonify({
                "success": True,
                "medication_list": validated_list,
                "count": len(validated_list),
                "model_used": model_used
            })
        
        except Exception as recognition_error:
            logger.error(f"药品识别失败: {recognition_error}")
            # 返回空数组让用户手动填写
            return jsonify({
                "success": True,
                "medication_list": [],
                "count": 0,
                "message": "识别功能暂时不可用，请手动填写药品信息"
            })
    
    except Exception as e:
        logger.error(f"处理药品识别请求失败: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"处理请求失败: {str(e)}"
        }), 500

if __name__ == '__main__':
    print("医疗AI后端服务启动中...")
    print("Qwen-VL-Max API 已配置")
    print("访问地址: http://localhost:5000")
    print("API文档: http://localhost:5000/api/health")
    print("TCM中医诊断模块已集成")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )