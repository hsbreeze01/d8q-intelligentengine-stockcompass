import logging
from flask import Blueprint, request, jsonify
import urllib.request
import json

bp = Blueprint('market_data', __name__)
logger = logging.getLogger('compass.market_data')

def get_dataagent(url):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f'DataAgent API failed: {e}')
        return []

@bp.route('/api/market/heat', methods=['GET'])
def get_heat_index():
    """Get heat index for all tracks"""
    try:
        tracks = get_dataagent('http://localhost:8000/api/tracks')
        heat_data = get_dataagent('http://localhost:8000/api/tracks/heat')
        
        result = []
        for track in tracks:
            track_heat = [h for h in heat_data if h.get('track_id') == track['id']]
            latest = track_heat[-1] if track_heat else None
            result.append({
                'id': track['id'],
                'name': track['name'],
                'color': track.get('color', '#1890ff'),
                'heat': latest.get('score', 0) if latest else 0,
                'news_count': latest.get('news_count', 0) if latest else 0,
                'policy_count': latest.get('policy_count', 0) if latest else 0,
                'report_count': latest.get('report_count', 0) if latest else 0,
                'funding_count': latest.get('funding_count', 0) if latest else 0,
                'trend': [h.get('score', 0) for h in track_heat[-7:]]
            })
        
        return jsonify({'tracks': result, 'success': True})
    except Exception as e:
        logger.error(f'Heat index failed: {e}')
        return jsonify({'error': str(e), 'success': False}), 500

@bp.route('/api/market/heat/<int:track_id>', methods=['GET'])
def get_track_heat(track_id):
    """Get heat data for a specific track"""
    try:
        heat_data = get_dataagent(f'http://localhost:8000/api/tracks/{track_id}/news')
        return jsonify({'news': heat_data, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500
