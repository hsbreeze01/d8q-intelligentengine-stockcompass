"""群体事件查询路由"""
import logging

from flask import Blueprint, request, jsonify, session

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


@bp.route("/events/<int:event_id>/close", methods=["POST"])
def close_event(event_id):
    """手动关闭事件 — 记录 closed_at + closed_by"""
    event = db.get_group_event(event_id)
    if not event:
        return jsonify({"error": "事件不存在"}), 404

    # 检查 lifecycle 状态
    lifecycle = event.get("lifecycle")
    if lifecycle == "closed":
        return jsonify({"error": "事件已关闭"}), 400

    # 获取当前登录用户 ID
    closed_by = session.get("uid")

    # 更新 lifecycle
    db.update_event_lifecycle(
        event_id,
        lifecycle="closed",
        closed_by=closed_by,
    )

    # 返回更新后的事件
    event = db.get_group_event(event_id)
    return jsonify(event)


@bp.route("/events/<int:event_id>/trend", methods=["GET"])
def get_event_trend(event_id):
    """获取事件趋势跟踪历史数据"""
    event = db.get_group_event(event_id)
    if not event:
        return jsonify({"error": "事件不存在"}), 404

    history = db.get_trend_tracking_history(event_id)
    return jsonify({
        "event_id": event_id,
        "records": history,
        "total": len(history),
    })


# ---------------------------------------------------------------------------
# 事件详情数据端点 — 微观/宏观/信息
# ---------------------------------------------------------------------------


@bp.route("/events/<int:event_id>/micro", methods=["GET"])
def get_event_micro(event_id):
    """获取事件微观数据：触发个股的指标快照 + buy 值"""
    data = db.get_event_micro_data(event_id)
    if data is None:
        return jsonify({"error": "事件不存在"}), 404
    return jsonify(data)


@bp.route("/events/<int:event_id>/macro", methods=["GET"])
def get_event_macro(event_id):
    """获取事件宏观数据：行业趋势聚合 + 板块走势"""
    data = db.get_event_macro_data(event_id)
    if data is None:
        return jsonify({"error": "事件不存在"}), 404
    return jsonify(data)


@bp.route("/events/<int:event_id>/info", methods=["GET"])
def get_event_info(event_id):
    """获取事件信息关联数据"""
    info = db.get_event_info_data(event_id)
    if info is None:
        return jsonify({"error": "事件不存在"}), 404

    # 尝试通过 DataGateway 获取关联资讯
    matched_stocks = info.get("matched_stocks", [])
    news = []
    try:
        from compass.services.data_gateway import DataGateway
        gateway = DataGateway()
        for code in matched_stocks[:5]:
            stock_news = gateway.agent.get_news_by_code(code, limit=5)
            if stock_news:
                news.extend(stock_news)
    except Exception as exc:
        logger.warning("获取资讯失败: %s", exc)

    info["news"] = news
    return jsonify(info)
