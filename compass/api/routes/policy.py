import logging
from flask import Blueprint, request, jsonify, render_template
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
    """使用 LLM 识别资讯中的政策/监管类内容（委托 Agent 服务）"""
    data = request.json
    news_content = data.get('content', '')
    
    if not news_content:
        return jsonify({'success': False, 'error': '缺少内容'}), 400
    
    try:
        req = urllib.request.Request(
            'http://localhost:8000/api/llm/policy/classify',
            data=json.dumps({'content': news_content}).encode(),
            method='POST',
            headers={'Content-Type': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        return jsonify(result)
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode())
        return jsonify(body), e.code
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
