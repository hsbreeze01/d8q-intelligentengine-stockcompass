"""策略组 CRUD 路由"""
import logging

from flask import Blueprint, request, jsonify

from compass.strategy.models import (
    StrategyGroupCreate,
    StrategyGroupStatusUpdate,
    StrategyGroupUpdate,
)
from compass.strategy import db

logger = logging.getLogger("compass.strategy.routes.strategy_groups")

bp = Blueprint("strategy_groups", __name__, url_prefix="/api/strategy")


@bp.route("/groups", methods=["POST"])
def create_group():
    """创建策略组"""
    data = request.json or {}
    try:
        body = StrategyGroupCreate(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    group_id = db.insert_strategy_group(
        name=body.name,
        indicators=body.indicators,
        signal_logic=body.signal_logic,
        conditions=[c.model_dump() for c in body.conditions],
        aggregation=body.aggregation.model_dump(),
        scan_cron=body.scan_cron,
        scoring_threshold=body.scoring_threshold,
    )
    group = db.get_strategy_group(group_id)
    return jsonify(_to_response(group)), 201


@bp.route("/groups/<int:group_id>", methods=["PUT"])
def update_group(group_id):
    """更新策略组"""
    existing = db.get_strategy_group(group_id)
    if not existing:
        return jsonify({"error": "策略组不存在"}), 404

    data = request.json or {}
    try:
        body = StrategyGroupUpdate(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    fields = body.model_dump(exclude_none=True)
    if not fields:
        return jsonify(_to_response(existing))

    # 序列化嵌套结构
    if "conditions" in fields and fields["conditions"]:
        fields["conditions"] = [
            c.model_dump() if hasattr(c, "model_dump") else c
            for c in fields["conditions"]
        ]
    if "aggregation" in fields and fields["aggregation"]:
        fields["aggregation"] = (
            fields["aggregation"].model_dump()
            if hasattr(fields["aggregation"], "model_dump")
            else fields["aggregation"]
        )

    db.update_strategy_group(group_id, **fields)

    # 如果 scan_cron 变了，重新加载调度器
    if "scan_cron" in fields or "status" in fields:
        try:
            from compass.strategy.scheduler import reload_scheduler
            reload_scheduler()
        except Exception as exc:
            logger.warning("重新加载调度器失败: %s", exc)

    group = db.get_strategy_group(group_id)
    return jsonify(_to_response(group))


@bp.route("/groups/<int:group_id>", methods=["DELETE"])
def delete_group(group_id):
    """软删除策略组"""
    db.soft_delete_strategy_group(group_id)
    group = db.get_strategy_group(group_id)
    if not group:
        return jsonify({"error": "策略组不存在"}), 404

    try:
        from compass.strategy.scheduler import reload_scheduler
        reload_scheduler()
    except Exception as exc:
        logger.warning("重新加载调度器失败: %s", exc)

    return jsonify(_to_response(group))


@bp.route("/groups/<int:group_id>/status", methods=["PATCH"])
def toggle_status(group_id):
    """切换策略组启停状态"""
    existing = db.get_strategy_group(group_id)
    if not existing:
        return jsonify({"error": "策略组不存在"}), 404

    data = request.json or {}
    try:
        body = StrategyGroupStatusUpdate(**data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    if body.status not in ("active", "paused"):
        return jsonify({"error": "合法取值为 active/paused"}), 400

    db.update_strategy_group_status(group_id, body.status)

    try:
        from compass.strategy.scheduler import reload_scheduler
        reload_scheduler()
    except Exception as exc:
        logger.warning("重新加载调度器失败: %s", exc)

    group = db.get_strategy_group(group_id)
    return jsonify(_to_response(group))


@bp.route("/groups", methods=["GET"])
def list_groups():
    """查询策略组列表"""
    status = request.args.get("status")
    groups = db.list_strategy_groups(status=status)
    return jsonify([_to_response(g) for g in groups])


@bp.route("/groups/<int:group_id>", methods=["GET"])
def get_group(group_id):
    """获取策略组详情"""
    group = db.get_strategy_group(group_id)
    if not group:
        return jsonify({"error": "策略组不存在"}), 404
    return jsonify(_to_response(group))


def _to_response(row: dict) -> dict:
    """将数据库行转为响应格式"""
    return {
        "id": row["id"],
        "name": row["name"],
        "indicators": row.get("indicators", []),
        "signal_logic": row.get("signal_logic", "AND"),
        "conditions": row.get("conditions", []),
        "scoring_threshold": row.get("scoring_threshold"),
        "aggregation": row.get("aggregation", {}),
        "scan_cron": row.get("scan_cron"),
        "status": row.get("status", "active"),
        "created_at": _fmt(row.get("created_at")),
        "updated_at": _fmt(row.get("updated_at")),
    }


def _fmt(val):
    """格式化日期时间"""
    if val is None:
        return None
    return str(val)
