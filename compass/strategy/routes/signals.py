"""信号查询 + 扫描触发 + SSE 路由"""
import json
import logging
import threading
import time

from flask import Blueprint, Response, jsonify, request, stream_with_context

from compass.strategy import db
from compass.strategy import db as db_helpers
from compass.strategy.models import ScanResult

logger = logging.getLogger("compass.strategy.routes.signals")

bp = Blueprint("strategy_signals", __name__, url_prefix="/api")


@bp.route("/strategy/<int:group_id>/scan", methods=["POST"])
def trigger_scan(group_id):
    """手动触发单个策略组扫描 — 异步模式：立即返回 202 + run_id"""
    # 校验策略组存在且 active
    group = db_helpers.get_strategy_group(group_id)
    if not group:
        return jsonify({"error": f"策略组 {group_id} 不存在"}), 400
    if group["status"] != "active":
        return jsonify({"error": f"策略组 {group_id} 未处于 active 状态"}), 400

    # 创建 run 记录
    run_id = db_helpers.create_run(group_id, trigger_type="manual")

    # 启动后台线程执行扫描
    thread = threading.Thread(
        target=_run_scan_background,
        args=(group_id, run_id),
        daemon=True,
    )
    thread.start()

    return jsonify({"run_id": run_id, "status": "running"}), 202


def _run_scan_background(group_id: int, run_id: int):
    """后台线程：执行扫描 + 聚合，更新 run 状态"""
    import datetime

    from compass.strategy.services.scanner import Scanner

    try:
        scanner = Scanner()
        result = scanner.scan(group_id, run_id=run_id, skip_llm=True)
        db_helpers.update_run(
            run_id,
            status="completed",
            total_stocks=result.get("total_stocks", 0),
            matched_stocks=result.get("matched_count", 0),
            duration_seconds=result.get("duration_seconds", 0),
            finished_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    except Exception as exc:
        logger.error("后台扫描失败 group=%d run=%d: %s", group_id, run_id, exc, exc_info=True)
        try:
            import datetime
            db_helpers.update_run(
                run_id,
                status="failed",
                error_message=str(exc),
                finished_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        except Exception:
            logger.error("更新 run 失败状态也失败 run=%d", run_id, exc_info=True)


@bp.route("/strategy/<int:group_id>/runs/latest", methods=["GET"])
def get_latest_run(group_id):
    """查询策略组最新扫描运行状态"""
    group = db_helpers.get_strategy_group(group_id)
    if not group:
        return jsonify({"error": f"策略组 {group_id} 不存在"}), 404

    run = db_helpers.get_latest_run(group_id)
    if run is None:
        return jsonify(None), 200

    # Serialize datetime fields
    result = dict(run)
    for key in ("started_at", "finished_at"):
        val = result.get(key)
        if val is not None:
            result[key] = str(val)
    return jsonify(result), 200


@bp.route("/signals", methods=["GET"])
def query_signals():
    """查询信号列表"""
    group_id = request.args.get("strategy_group_id", type=int)
    stock_code = request.args.get("stock_code")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    # Clamp values
    limit = max(1, min(200, limit))
    offset = max(0, offset)

    result = db.query_signals(
        strategy_group_id=group_id,
        stock_code=stock_code,
        limit=limit,
        offset=offset,
    )
    return jsonify(result)


@bp.route("/signals/stream", methods=["GET"])
def signal_stream():
    """SSE 实时信号推送"""
    def event_generator():
        while True:
            data = json.dumps({"ts": "heartbeat"})
            yield f"event: ping\ndata: {data}\n\n"
            time.sleep(30)

    return Response(
        stream_with_context(event_generator()),
        content_type="text/event-stream",
    )
