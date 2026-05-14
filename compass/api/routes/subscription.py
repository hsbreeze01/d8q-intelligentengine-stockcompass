import logging
from flask import Blueprint, request, jsonify
from compass.data.database import Database

bp = Blueprint('subscription', __name__)
logger = logging.getLogger('compass.subscription')


@bp.route('/api/user/tracks', methods=['GET'])
def get_user_tracks():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'username required'}), 400
    with Database() as db:
        _, user = db.select_one('SELECT id FROM user WHERE username=%s', (username,))
        if not user:
            return jsonify({'error': 'User not found'}), 404
        count, tracks = db.select_many(
            'SELECT t.id, t.name FROM tracks t JOIN user_tracks ut ON t.id = ut.track_id WHERE ut.user_id = %s',
            (user['id'],)
        )
    return jsonify({'tracks': [{'id': r['id'], 'name': r['name']} for r in tracks]})


@bp.route('/api/user/tracks', methods=['POST'])
def add_user_track():
    data = request.json
    username = data.get('username')
    track_id = data.get('track_id')
    if not username or not track_id:
        return jsonify({'error': 'username and track_id required'}), 400
    with Database() as db:
        _, user = db.select_one('SELECT id FROM user WHERE username=%s', (username,))
        if not user:
            return jsonify({'error': 'User not found'}), 404
        db.execute('INSERT INTO user_tracks (user_id, track_id) VALUES (%s, %s)', (user['id'], track_id))
    return jsonify({'success': True, 'message': 'Track subscribed'})


@bp.route('/api/user/tracks/<int:track_id>', methods=['DELETE'])
def remove_user_track(track_id):
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'username required'}), 400
    with Database() as db:
        _, user = db.select_one('SELECT id FROM user WHERE username=%s', (username,))
        if not user:
            return jsonify({'error': 'User not found'}), 404
        db.execute('DELETE FROM user_tracks WHERE user_id=%s AND track_id=%s', (user['id'], track_id))
    return jsonify({'success': True, 'message': 'Track unsubscribed'})
