"""策略组订阅 API 路由"""
import logging

from flask import Blueprint, request, jsonify, session

from compass.strategy import db

logger = logging.getLogger("compass.strategy.routes.subscription")

bp = Blueprint("strategy_subscription", __name__, url_prefix="/api/strategy")


def _require_login():
    """检查登录状态，返回 uid 或 None"""
    return session.get("uid")


@bp.route("/subscription", methods=["POST"])
def subscribe():
    """订阅策略组"""
    uid = _require_login()
    if not uid:
        return jsonify({"error": "未登录"}), 401

    data = request.json or {}
    group_id = data.get("strategy_group_id")
    if not group_id:
        return jsonify({"error": "strategy_group_id required"}), 400

    # 检查策略组存在且 active
    group = db.get_strategy_group(group_id)
    if not group:
        return jsonify({"error": "策略组不存在"}), 404
    if group.get("status") != "active":
        return jsonify({"error": "该策略组不可订阅"}), 400

    # 尝试订阅
    sub = db.insert_subscription(uid, group_id)
    if sub is None:
        return jsonify({"error": "已订阅该策略"}), 409

    return jsonify({
        "id": sub["id"],
        "user_id": sub["user_id"],
        "strategy_group_id": sub["strategy_group_id"],
        "subscribed_at": str(sub["subscribed_at"]),
    }), 201


@bp.route("/subscription/<int:group_id>", methods=["DELETE"])
def unsubscribe(group_id):
    """取消订阅策略组"""
    uid = _require_login()
    if not uid:
        return jsonify({"error": "未登录"}), 401

    deleted = db.delete_subscription(uid, group_id)
    if not deleted:
        return jsonify({"error": "未订阅该策略"}), 404

    return jsonify({"message": "已取消订阅"}), 200


@bp.route("/subscription/mine", methods=["GET"])
def my_subscriptions():
    """查询当前用户的订阅列表"""
    uid = _require_login()
    if not uid:
        return jsonify({"error": "未登录"}), 401

    subs = db.list_user_subscriptions(uid)
    result = []
    for s in subs:
        result.append({
            "id": s["id"],
            "strategy_group_id": s["strategy_group_id"],
            "subscribed_at": str(s["subscribed_at"]),
            "group": {
                "id": s["strategy_group_id"],
                "name": s.get("name", ""),
                "indicators": s.get("indicators", []),
                "signal_logic": s.get("signal_logic", "AND"),
                "conditions": s.get("conditions", []),
                "status": s.get("group_status", ""),
            },
        })
    return jsonify(result), 200
