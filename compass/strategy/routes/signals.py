"""信号查询 + 扫描触发 + SSE 路由"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from compass.strategy import db
from compass.strategy.models import ScanResult

logger = logging.getLogger("compass.strategy.routes.signals")

router = APIRouter()


@router.post("/strategy/{group_id}/scan")
def trigger_scan(group_id: int):
    """手动触发单个策略组扫描"""
    from compass.strategy.services.scanner import Scanner

    try:
        scanner = Scanner()
        result = scanner.scan(group_id, trigger_type="manual")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("扫描失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    return ScanResult(
        scan_run_id=result["run_id"],
        signals_found=result["matched_count"],
        events_created=result.get("events_created", 0),
        duration_seconds=result["duration_seconds"],
    )


@router.get("/signals")
def query_signals(
    group_id: Optional[int] = Query(None, alias="strategy_group_id"),
    stock_code: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """查询信号列表"""
    result = db.query_signals(
        strategy_group_id=group_id,
        stock_code=stock_code,
        limit=limit,
        offset=offset,
    )
    return result


@router.get("/signals/stream")
async def signal_stream():
    """SSE 实时信号推送"""
    import asyncio
    import json

    async def event_generator():
        # 简单的 SSE 心跳实现
        # 实际信号推送需要集成到扫描器中
        while True:
            yield {"event": "ping", "data": json.dumps({"ts": "heartbeat"})}
            await asyncio.sleep(30)

    return EventSourceResponse(event_generator())
