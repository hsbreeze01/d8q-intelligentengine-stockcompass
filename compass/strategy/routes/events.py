"""群体事件查询路由"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from compass.strategy import db

logger = logging.getLogger("compass.strategy.routes.events")

router = APIRouter()


@router.get("/events")
def query_events(
    group_id: Optional[int] = Query(None, alias="strategy_group_id"),
    dimension_value: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """查询群体事件列表"""
    result = db.query_group_events(
        strategy_group_id=group_id,
        dimension_value=dimension_value,
        status=status,
        limit=limit,
        offset=offset,
    )
    return result


@router.get("/events/{event_id}")
def get_event(event_id: int):
    """获取事件详情"""
    event = db.get_group_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    return event


@router.patch("/events/{event_id}/close")
def close_event(event_id: int):
    """手动关闭事件"""
    event = db.get_group_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    db.update_group_event(event_id, status="closed")
    event = db.get_group_event(event_id)
    return event
