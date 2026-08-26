"""缠论知识图谱代理路由

代理转发到 d8q-intelligentengine-ontology 服务的工具端点，
供前端/Agent 直接调用，无需知道 ontology 服务地址。
"""
import os
import json
import logging
import requests
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

ontology_bp = Blueprint("ontology", __name__, url_prefix="/ontology")

ONTOLOGY_URL = os.environ.get("ONTOLOGY_SERVICE_URL", "http://127.0.0.1:8080")
TIMEOUT = 10


def _proxy(endpoint: str, payload: dict) -> dict:
    """转发请求到 ontology 服务"""
    url = f"{ONTOLOGY_URL}/tools/{endpoint}"
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": f"ontology service unreachable: {ONTOLOGY_URL}"}
    except Exception as e:
        return {"error": str(e)}


@ontology_bp.route("/structure/<symbol>", methods=["GET"])
def get_structure(symbol):
    """获取缠论结构（笔/线段/中枢）"""
    return jsonify(_proxy("get_chan_structure", {"symbol": symbol}))


@ontology_bp.route("/verify/<symbol>", methods=["GET"])
def verify_buy_points(symbol):
    """验证买卖点有效性"""
    return jsonify(_proxy("verify_buy_points", {"symbol": symbol}))


@ontology_bp.route("/explain/<signal_id>", methods=["GET"])
def explain_buy_point(signal_id):
    """解释买卖点逻辑"""
    return jsonify(_proxy("explain_buy_point", {"signal_id": signal_id}))


@ontology_bp.route("/summary/<symbol>", methods=["GET"])
def get_level_summary(symbol):
    """获取多级别联立摘要"""
    return jsonify(_proxy("get_level_summary", {"symbol": symbol}))


@ontology_bp.route("/health", methods=["GET"])
def ontology_health():
    """检查 ontology 服务健康状态"""
    try:
        resp = requests.get(f"{ONTOLOGY_URL}/healthz", timeout=5)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"status": "unreachable", "error": str(e)}), 503


def add_ontology_routes(app):
    """注册知识图谱路由到 Flask app"""
    app.register_blueprint(ontology_bp)
