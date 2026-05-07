import os
import sys
import logging

logger = logging.getLogger("compass.scheduler")


def _ensure_legacy_path():
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    for p in [base, os.path.dirname(base)]:
        if p not in sys.path:
            sys.path.insert(0, p)


class DailyAnalysisTask:
    def run(self):
        logger.info("DailyAnalysisTask starting...")
        try:
            _ensure_legacy_path()
            from stockdata.DailyStockCheckTaskV2 import DailyStockCheckTaskV2

            task = DailyStockCheckTaskV2()
            task.action()
            logger.info("DailyAnalysisTask completed")
        except Exception as e:
            logger.error("DailyAnalysisTask failed: %s", e)


class DailyRecommendationTask:
    """每日推荐计算任务 — 在 DailyAnalysisTask 完成后执行"""

    def run(self):
        logger.info("DailyRecommendationTask starting...")
        try:
            from compass.services.recommendation import RecommendationService

            svc = RecommendationService()
            result = svc.generate_daily()
            logger.info(
                "DailyRecommendationTask completed: %d recommendations, %.1f seconds",
                result["count"],
                result["elapsed_seconds"],
            )
        except Exception as e:
            logger.error("DailyRecommendationTask failed: %s", e)
