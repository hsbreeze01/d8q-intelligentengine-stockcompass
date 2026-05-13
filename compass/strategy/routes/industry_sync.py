"""行业数据同步路由"""
import logging
import threading

from flask import Blueprint, jsonify

from compass.strategy.services.industry_sync import (
    get_industry_stats,
    get_industry_status,
    get_sync_status,
    sync_industry_data,
)

logger = logging.getLogger("compass.strategy.routes.industry_sync")

bp = Blueprint("strategy_industry_sync", __name__, url_prefix="/api")


@bp.route("/admin/industry/sync", methods=["POST"])
def trigger_industry_sync():
    """触发行业数据同步（后台执行）"""
    status = get_sync_status()
    if status.get("running"):
        return jsonify({"message": "同步正在进行中", "status": status})

    thread = threading.Thread(target=sync_industry_data, daemon=True)
    thread.start()
    return jsonify({"message": "同步任务已启动"}), 202


@bp.route("/admin/industry/sync/status", methods=["GET"])
def industry_sync_status():
    """查询同步进度"""
    return jsonify(get_sync_status())


@bp.route("/admin/industry/stats", methods=["GET"])
def industry_stats():
    """查询行业分布统计"""
    return jsonify(get_industry_stats())


@bp.route("/admin/industry/status", methods=["GET"])
def industry_completion_status():
    """查询行业补全状态"""
    return jsonify(get_industry_status())
