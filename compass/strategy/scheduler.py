"""策略组引擎 — APScheduler 封装"""
import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from compass.strategy.db import list_active_groups

logger = logging.getLogger("compass.strategy.scheduler")

_scheduler: Optional[BackgroundScheduler] = None


def start_scheduler():
    """启动调度器，加载所有 active 策略组的定时任务"""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler()
    _load_cron_jobs()
    _scheduler.start()
    logger.info("APScheduler 已启动")


def shutdown_scheduler():
    """优雅关闭调度器"""
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("APScheduler 已关闭")


def reload_scheduler():
    """重新加载所有 cron 任务（策略组变更后调用）"""
    if _scheduler is None:
        return
    # 清除所有现有任务
    _scheduler.remove_all_jobs()
    _load_cron_jobs()
    logger.info("调度器已重新加载")


def _load_cron_jobs():
    """从数据库加载 active 策略组的 scan_cron，注册定时任务"""
    try:
        groups = list_active_groups()
    except Exception as exc:
        logger.error("加载策略组失败: %s", exc)
        return

    for g in groups:
        cron = g.get("scan_cron")
        if not cron:
            continue
        try:
            parts = cron.split()
            if len(parts) != 5:
                logger.warning("策略组 %d cron 格式无效: %s", g["id"], cron)
                continue

            _scheduler.add_job(
                _run_scan,
                "cron",
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
                args=[g["id"]],
                id=f"scan_group_{g['id']}",
                replace_existing=True,
            )
            logger.info("策略组 %d cron 任务已注册: %s", g["id"], cron)
        except Exception as exc:
            logger.error("注册策略组 %d cron 失败: %s", g["id"], exc)

    # 注册每日趋势跟踪任务（工作日 16:00）
    try:
        _scheduler.add_job(
            _run_trend_tracking,
            "cron",
            minute="0",
            hour="16",
            day_of_week="mon-fri",
            id="daily_trend_tracking",
            replace_existing=True,
        )
        logger.info("每日趋势跟踪任务已注册: 0 16 * * mon-fri")
    except Exception as exc:
        logger.error("注册趋势跟踪任务失败: %s", exc)


def _run_scan(group_id: int):
    """定时扫描回调"""
    logger.info("[strategy.scanner] 定时扫描开始 strategy_group_id=%d", group_id)
    try:
        from compass.strategy.services.scanner import Scanner
        scanner = Scanner()
        result = scanner.scan(group_id, trigger_type="cron")
        logger.info(
            "[strategy.scanner] strategy_group_id=%d matched=%d total=%d duration=%.1fs",
            group_id,
            result.get("matched_count", 0),
            result.get("total_stocks", 0),
            result.get("duration_seconds", 0),
        )
    except Exception as exc:
        logger.error("策略组 %d 扫描失败: %s", group_id, exc, exc_info=True)


def _run_trend_tracking():
    """每日趋势跟踪回调"""
    logger.info("[strategy.trend_tracker] 每日趋势跟踪开始")
    try:
        from compass.strategy.services.trend_tracker import TrendTracker
        tracker = TrendTracker()
        result = tracker.track_all()
        logger.info(
            "[strategy.trend_tracker] 完成: tracked=%d decayed=%d errors=%d",
            result.get("tracked", 0),
            result.get("decayed", 0),
            result.get("errors", 0),
        )
    except Exception as exc:
        logger.error("趋势跟踪失败: %s", exc, exc_info=True)
