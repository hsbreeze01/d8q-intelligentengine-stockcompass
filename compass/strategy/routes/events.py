"""群体事件查询路由"""
import logging

from flask import Blueprint, request, jsonify

from compass.strategy import db

logger = logging.getLogger("compass.strategy.routes.events")

bp = Blueprint("strategy_events", __name__, url_prefix="/api")


@bp.route("/events", methods=["GET"])
def query_events():
    """查询群体事件列表"""
    group_id = request.args.get("strategy_group_id", type=int)
    dimension_value = request.args.get("dimension_value")
    status = request.args.get("status")
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)

    # Clamp values
    limit = max(1, min(100, limit))
    offset = max(0, offset)

    result = db.query_group_events(
        strategy_group_id=group_id,
        dimension_value=dimension_value,
        status=status,
        limit=limit,
        offset=offset,
    )
    return jsonify(result)


@bp.route("/events/<int:event_id>", methods=["GET"])
def get_event(event_id):
    """获取事件详情"""
    event = db.get_group_event(event_id)
    if not event:
        return jsonify({"error": "事件不存在"}), 404
    return jsonify(event)


@bp.route("/events/<int:event_id>/close", methods=["PATCH"])
def close_event(event_id):
    """手动关闭事件"""
    event = db.get_group_event(event_id)
    if not event:
        return jsonify({"error": "事件不存在"}), 404

    db.update_group_event(event_id, status="closed")
    event = db.get_group_event(event_id)
    return jsonify(event)
