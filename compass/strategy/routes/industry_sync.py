"""行业数据同步路由"""
import logging

from fastapi import APIRouter, BackgroundTasks

from compass.strategy.services.industry_sync import (
    get_industry_stats,
    get_industry_status,
    get_sync_status,
    sync_industry_data,
)

logger = logging.getLogger("compass.strategy.routes.industry_sync")

router = APIRouter()


@router.post("/admin/industry/sync", status_code=202)
def trigger_industry_sync(background_tasks: BackgroundTasks):
    """触发行业数据同步（后台执行）"""
    status = get_sync_status()
    if status.get("running"):
        return {"message": "同步正在进行中", "status": status}

    background_tasks.add_task(sync_industry_data)
    return {"message": "同步任务已启动"}


@router.get("/admin/industry/sync/status")
def industry_sync_status():
    """查询同步进度"""
    return get_sync_status()


@router.get("/admin/industry/stats")
def industry_stats():
    """查询行业分布统计"""
    return get_industry_stats()


@router.get("/admin/industry/status")
def industry_completion_status():
    """查询行业补全状态"""
    return get_industry_status()
