import logging
import os
import sys
import json
import urllib.request
from flask import Blueprint, request, jsonify, render_template

from compass.llm import DeepSeekLLM

bp = Blueprint('report', __name__)
logger = logging.getLogger('compass.report')

# Prompt 管理器
COMPASS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, COMPASS_ROOT)
from prompt_loader import PromptManager
_pm = PromptManager(os.path.join(COMPASS_ROOT, 'prompts'))

TEMPLATES_FILE = '/var/log/d8q/report_templates.json'

def get_default_template():
    return {
        'name': '默认周报模板',
        'sections': [
            {'title': '本周赛道概览', 'subsections': ['热度变化（对比上周）', '关键事件摘要（3-5条）']},
            {'title': '政策与监管动态', 'subsections': ['国内政策', '海外政策']},
            {'title': '融资与并购', 'subsections': ['本周重要融资事件', '并购/IPO 动态']},
            {'title': '技术与产品进展', 'subsections': ['重要产品发布', '技术突破']},
            {'title': '投资观点', 'subsections': ['机构观点汇总', 'AI 综合研判']},
            {'title': '下周关注', 'subsections': ['即将发布的数据/事件', '建议关注的方向']}
        ]
    }

def load_templates():
    try:
        if os.path.exists(TEMPLATES_FILE):
            with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {'templates': [get_default_template()]}

def save_templates(data):
    os.makedirs(os.path.dirname(TEMPLATES_FILE), exist_ok=True)
    with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_track_data(track_id):
    """从 DataAgent 获取赛道数据"""
    try:
        url = f'http://localhost:8000/api/tracks/{track_id}/news'
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f'Failed to get track data: {e}')
        return []

@bp.route('/api/report/templates', methods=['GET'])
def get_templates():
    """获取周报模板列表"""
    data = load_templates()
    return jsonify({'success': True, 'templates': data.get('templates', [])})

@bp.route('/api/report/templates', methods=['POST'])
def save_template():
    """保存周报模板"""
    data = request.json
    templates_data = load_templates()
    templates_data['templates'] = templates_data.get('templates', [])
    
    new_template = data.get('template')
    if new_template:
        templates_data['templates'].append(new_template)
        save_templates(templates_data)
        return jsonify({'success': True, 'message': '模板保存成功'})
    
    return jsonify({'success': False, 'error': '无效的模板数据'}), 400

@bp.route('/api/report/generate', methods=['POST'])
def generate_report():
    """生成周报"""
    data = request.json
    track_id = data.get('track_id')
    track_name = data.get('track_name', '未知赛道')
    time_range = data.get('time_range', '本周')
    
    if not track_id:
        return jsonify({'success': False, 'error': '缺少 track_id'}), 400
    
    news_data = get_track_data(track_id)
    
    # 从 prompt 配置加载模板
    prompt = _pm.get_template("weekly_report", track_name=track_name, time_range=time_range, news_count=str(len(news_data)))
    system = _pm.get_system("weekly_report")
    
    try:
        llm = DeepSeekLLM()
        messages = [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': prompt}
        ]
        report_content = llm.standard_request(messages)
        
        if report_content:
            return jsonify({
                'success': True,
                'report': report_content,
                'track_name': track_name,
                'time_range': time_range
            })
        else:
            return jsonify({'success': False, 'error': 'LLM 生成失败'}), 500
    except Exception as e:
        logger.error(f'Report generation failed: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/report')
def report_page():
    """周报页面"""
    return render_template('report.html')
