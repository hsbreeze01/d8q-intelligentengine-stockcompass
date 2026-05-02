"""Compass Prompt 管理 API"""
import os
import sys
from flask import Blueprint, request, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from prompt_loader import PromptManager

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'prompts')
pm = PromptManager(PROMPTS_DIR)

bp = Blueprint('prompts', __name__)


@bp.route('/api/prompts', methods=['GET'])
def list_prompts():
    return jsonify({"success": True, "prompts": pm.list_all(), "service": "compass"})


@bp.route('/api/prompts/<path:prompt_id>', methods=['GET'])
def get_prompt(prompt_id):
    p = pm.get(prompt_id)
    if p:
        return jsonify({"success": True, "prompt": p})
    return jsonify({"success": False, "error": "Prompt not found"}), 404


@bp.route('/api/prompts/<path:prompt_id>', methods=['PUT'])
def update_prompt(prompt_id):
    body = request.json or {}
    if pm.save(prompt_id, body):
        return jsonify({"success": True, "message": "Prompt updated"})
    return jsonify({"success": False, "error": "Save failed"}), 500
