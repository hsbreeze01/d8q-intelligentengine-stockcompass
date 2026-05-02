import logging
from flask import Blueprint, request, jsonify
import pymysql

bp = Blueprint('subscription', __name__)
logger = logging.getLogger('compass.subscription')

def get_db():
    return pymysql.connect(host='localhost', user='root', password='password', database='stock_analysis_system')

@bp.route('/api/user/tracks', methods=['GET'])
def get_user_tracks():
    """Get user subscribed tracks"""
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'username required'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM user WHERE username=%s', (username,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    cursor.execute('SELECT t.id, t.name FROM tracks t JOIN user_tracks ut ON t.id = ut.track_id WHERE ut.user_id = %s', (user[0],))
    tracks = [{'id': r[0], 'name': r[1]} for r in cursor.fetchall()]
    conn.close()
    return jsonify({'tracks': tracks})

@bp.route('/api/user/tracks', methods=['POST'])
def add_user_track():
    """Subscribe to a track"""
    data = request.json
    username = data.get('username')
    track_id = data.get('track_id')
    if not username or not track_id:
        return jsonify({'error': 'username and track_id required'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM user WHERE username=%s', (username,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    try:
        cursor.execute('INSERT INTO user_tracks (user_id, track_id) VALUES (%s, %s)', (user[0], track_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Track subscribed'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

@bp.route('/api/user/tracks/<int:track_id>', methods=['DELETE'])
def remove_user_track(track_id):
    """Unsubscribe from a track"""
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'username required'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM user WHERE username=%s', (username,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    cursor.execute('DELETE FROM user_tracks WHERE user_id=%s AND track_id=%s', (user[0], track_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Track unsubscribed'})
