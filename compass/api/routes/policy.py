import logging
from flask import Blueprint, request, jsonify, render_template
from compass.llm import DeepSeekLLM
import json
import urllib.request

bp = Blueprint('policy', __name__)
logger = logging.getLogger('compass.policy')

def get_dataagent(url):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f'DataAgent API failed: {e}')
        return []

@bp.route('/api/policy/classify', methods=['POST'])
def classify_policy():
    """使用 LLM 识别资讯中的政策/监管类内容"""
    data = request.json
    news_content = data.get('content', '')
    
    if not news_content:
        return jsonify({'success': False, 'error': '缺少内容'}), 400
    
    prompt = f"""请分析以下新闻内容，判断是否为政策/监管类资讯，并给出简要分析。

新闻内容：
{news_content}

请按以下 JSON 格式返回：
{{
    "is_policy": true/false,
    "category": "政策类型（如：国内政策、海外政策、行业监管、财政政策等）",
    "summary": "政策要点摘要（50字以内）",
    "impact": "对相关行业的影响（利好/利空/中性）"
}}
"""
    
    try:
        llm = DeepSeekLLM()
        messages = [
            {'role': 'system', 'content': '你是专业的政策分析师，擅长识别和分析政策新闻。'},
            {'role': 'user', 'content': prompt}
        ]
        result = llm.standard_request(messages)
        
        if result:
            # 尝试解析 JSON
            try:
                # 提取 JSON 部分
                import re
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    policy_info = json.loads(json_match.group())
                    return jsonify({'success': True, 'policy': policy_info})
            except:
                pass
            return jsonify({'success': True, 'raw_result': result})
        else:
            return jsonify({'success': False, 'error': 'LLM 分析失败'}), 500
    except Exception as e:
        logger.error(f'Policy classification failed: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/policy/analysis', methods=['GET'])
def policy_analysis():
    """获取政策分析概览"""
    try:
        # 从 DataAgent 获取所有新闻
        tracks = get_dataagent('http://localhost:8000/api/tracks')
        
        # 获取赛道新闻并统计政策类
        policy_stats = []
        for track in tracks[:5]:  # 只看前5个赛道
            news = get_dataagent(f'http://localhost:8000/api/tracks/{track["id"]}/news')
            policy_count = sum(1 for n in news if '政策' in n.get('title', '') or '监管' in n.get('title', ''))
            policy_stats.append({
                'track_id': track['id'],
                'track_name': track['name'],
                'total_news': len(news),
                'policy_count': policy_count
            })
        
        return jsonify({'success': True, 'stats': policy_stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/policy')
def policy_page():
    """政策分析页面"""
    return render_template('policy.html')
