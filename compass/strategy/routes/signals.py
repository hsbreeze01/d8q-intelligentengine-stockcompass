"""信号查询 + 扫描触发 + SSE 路由"""
import json
import logging
import time

from flask import Blueprint, Response, jsonify, request, stream_with_context

from compass.strategy import db
from compass.strategy.models import ScanResult

logger = logging.getLogger("compass.strategy.routes.signals")

bp = Blueprint("strategy_signals", __name__, url_prefix="/api")


@bp.route("/strategy/<int:group_id>/scan", methods=["POST"])
def trigger_scan(group_id):
    """手动触发单个策略组扫描"""
    from compass.strategy.services.scanner import Scanner

    try:
        scanner = Scanner()
        result = scanner.scan(group_id, trigger_type="manual")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.error("扫描失败: %s", exc, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

    scan_result = ScanResult(
        scan_run_id=result["run_id"],
        signals_found=result["matched_count"],
        events_created=result.get("events_created", 0),
        duration_seconds=result["duration_seconds"],
    )
    return jsonify(scan_result.model_dump())


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
