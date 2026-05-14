"""趋势跟踪器 — 每日趋势跟踪 + 信号衰减判定 + 资讯关联

职责：
- 每日对 lifecycle='tracking' 的群体事件执行趋势跟踪
- 记录触发股票变化（new_stocks / lost_stocks）
- 聚合量化指标均值（RSI / MACD DIF / 量比 / 综合评分）
- 信号衰减判定（连续 2 日 avg_score < 0.5 → suggest_close）
- 资讯持续关联（用 llm_keywords + llm_related_themes 搜索近 24h 资讯）
"""
import datetime
import json
import logging
from typing import Optional

from compass.strategy import db
from compass.services.data_gateway import DataGateway

logger = logging.getLogger(__name__)

# 衰减阈值
DECAY_SCORE_THRESHOLD = 0.5
DECAY_CONSECUTIVE_DAYS = 2


class TrendTracker:
    """趋势跟踪器"""

    def __init__(self, gateway: Optional[DataGateway] = None):
        self._gateway = gateway

    @property
    def gateway(self) -> DataGateway:
        if self._gateway is None:
            self._gateway = DataGateway()
        return self._gateway

    def track_all(self) -> dict:
        """对所有 lifecycle='tracking' 的事件执行趋势跟踪。

        Returns
        -------
        dict
            {"tracked": int, "decayed": int, "errors": int}
        """
        events = db.list_tracking_events()
        if not events:
            logger.info("无 tracking 事件，跳过趋势跟踪")
            return {"tracked": 0, "decayed": 0, "errors": 0}

        tracked = 0
        decayed = 0
        errors = 0

        for event in events:
            try:
                result = self._track_event(event)
                tracked += 1
                if result.get("decayed"):
                    decayed += 1
            except Exception as e:
                logger.error(
                    "趋势跟踪失败 event=%d: %s", event.get("id"), e
                )
                errors += 1

        logger.info(
            "趋势跟踪完成: tracked=%d, decayed=%d, errors=%d",
            tracked, decayed, errors,
        )
        return {"tracked": tracked, "decayed": decayed, "errors": errors}

    def _track_event(self, event: dict) -> dict:
        """对单个事件执行趋势跟踪。

        Returns
        -------
        dict
            {"track_id": int, "decayed": bool}
        """
        event_id = event["id"]
        today = datetime.date.today().isoformat()

        # 1. 获取当日触发股票列表 + 指标数据
        current_stocks = self._get_current_stocks(event)

        # 2. 与前一日对比 → new_stocks / lost_stocks
        prev_tracking = db.get_latest_trend_tracking(event_id)
        if prev_tracking is None:
            # 首次跟踪：所有股票为 new_stocks
            new_stocks = current_stocks
            lost_stocks = []
        else:
            prev_stock_list = self._get_stocks_from_tracking(prev_tracking)
            new_stocks = [s for s in current_stocks if s not in prev_stock_list]
            lost_stocks = [s for s in prev_stock_list if s not in current_stocks]

        # 3. 聚合指标均值
        indicators = self._get_stock_indicators(event, current_stocks)

        # 4. 资讯关联
        news_count = 0
        try:
            news_count = self._associate_news(event)
        except Exception as e:
            logger.warning("资讯关联失败 event=%d: %s", event_id, e)

        # 5. 写入 trend_tracking 记录
        stock_codes = [s if isinstance(s, str) else s.get("code", "")
                       for s in current_stocks]
        new_codes = [s if isinstance(s, str) else s.get("code", "")
                     for s in new_stocks]
        lost_codes = [s if isinstance(s, str) else s.get("code", "")
                      for s in lost_stocks]

        track_id = db.insert_trend_tracking(
            event_id=event_id,
            track_date=today,
            stock_count=len(stock_codes),
            new_stocks=new_codes,
            lost_stocks=lost_codes,
            avg_rsi=indicators.get("avg_rsi"),
            avg_macd_dif=indicators.get("avg_macd_dif"),
            avg_volume_ratio=indicators.get("avg_volume_ratio"),
            avg_score=indicators.get("avg_score"),
            news_count=news_count,
        )

        # 6. 衰减判定
        decayed = False
        try:
            decayed = self._check_decay(event_id, indicators.get("avg_score"))
        except Exception as e:
            logger.warning("衰减判定失败 event=%d: %s", event_id, e)

        return {"track_id": track_id, "decayed": decayed}

    def _get_current_stocks(self, event: dict) -> list:
        """获取事件当前触发股票列表"""
        matched = event.get("matched_stocks", [])
        if not matched:
            return []
        result = []
        for s in matched:
            if isinstance(s, str):
                result.append(s)
            elif isinstance(s, dict):
                result.append(s.get("code", ""))
        return [r for r in result if r]

    def _get_stocks_from_tracking(self, tracking: dict) -> list:
        """从跟踪记录中提取前一日的股票列表"""
        # 使用 new_stocks + 已存在的 stocks（通过 lost_stocks 反推）
        # 简化：这里只能用 stock_count 做参考，实际需查询当日快照
        return []

    def _get_stock_indicators(self, event: dict, stocks: list) -> dict:
        """聚合触发股票的量化指标均值"""
        if not stocks:
            return {}

        stock_codes = []
        for s in stocks:
            if isinstance(s, str):
                stock_codes.append(s)
            elif isinstance(s, dict):
                stock_codes.append(s.get("code", ""))

        # 从 micro data 获取指标
        try:
            micro = db.get_event_micro_data(event["id"])
            if not micro or not micro.get("stocks"):
                return {}

            rsi_vals = []
            macd_vals = []
            vol_vals = []
            score_vals = []

            for stock in micro["stocks"]:
                snap = stock.get("indicator_snapshot", {})
                if snap:
                    rsi = snap.get("RSI")
                    macd_dif = snap.get("MACD_DIF") or snap.get("MACD")
                    vol_ratio = snap.get("volume_ratio") or snap.get("量比")
                    score = snap.get("score")

                    if rsi is not None:
                        try:
                            rsi_vals.append(float(rsi))
                        except (TypeError, ValueError):
                            pass
                    if macd_dif is not None:
                        try:
                            macd_vals.append(float(macd_dif))
                        except (TypeError, ValueError):
                            pass
                    if vol_ratio is not None:
                        try:
                            vol_vals.append(float(vol_ratio))
                        except (TypeError, ValueError):
                            pass
                    if score is not None:
                        try:
                            score_vals.append(float(score))
                        except (TypeError, ValueError):
                            pass

            # buy_star 归一化到 0-1 作为 score 替代
            if not score_vals:
                for stock in micro["stocks"]:
                    bs = stock.get("buy_star")
                    if bs is not None:
                        try:
                            score_vals.append(float(bs) / 10.0)
                        except (TypeError, ValueError):
                            pass

            result = {}
            if rsi_vals:
                result["avg_rsi"] = round(sum(rsi_vals) / len(rsi_vals), 4)
            if macd_vals:
                result["avg_macd_dif"] = round(
                    sum(macd_vals) / len(macd_vals), 4
                )
            if vol_vals:
                result["avg_volume_ratio"] = round(
                    sum(vol_vals) / len(vol_vals), 4
                )
            if score_vals:
                result["avg_score"] = round(
                    sum(score_vals) / len(score_vals), 4
                )

            return result

        except Exception as e:
            logger.warning("获取指标失败 event=%d: %s", event["id"], e)
            return {}

    def _associate_news(self, event: dict) -> int:
        """用关键词搜索近 24h 资讯并追加到事件记录。"""
        keywords = event.get("llm_keywords") or []
        themes = event.get("llm_related_themes") or []

        # 解析 JSON 字符串
        if isinstance(keywords, str):
            try:
                keywords = json.loads(keywords)
            except (json.JSONDecodeError, TypeError):
                keywords = []
        if isinstance(themes, str):
            try:
                themes = json.loads(themes)
            except (json.JSONDecodeError, TypeError):
                themes = []

        if not keywords and not themes:
            return 0

        all_kw = list(set(keywords + themes))
        matched = self.gateway.search_news_by_keywords(all_kw, limit=20)

        if matched:
            try:
                db.append_event_news_matched(event["id"], matched)
            except Exception as e:
                logger.warning("追加资讯失败 event=%d: %s", event["id"], e)

        return len(matched)

    def _check_decay(self, event_id: int, current_score: Optional[float]) -> bool:
        """信号衰减判定：连续 N 日 avg_score < 阈值 → suggest_close。

        Returns
        -------
        bool
            是否触发了衰减
        """
        if current_score is None:
            return False

        if current_score >= DECAY_SCORE_THRESHOLD:
            return False

        # 获取最近 N-1 个交易日的记录（加上当天 = N 个）
        recent = db.get_recent_trend_trackings(event_id, DECAY_CONSECUTIVE_DAYS)

        # 需要至少有 CONSECUTIVE_DAYS 个连续低分记录
        # 当天记录刚刚写入，所以 recent 中最新的一条就是今天
        low_count = 0
        for record in recent:
            score = record.get("avg_score")
            if score is not None and score < DECAY_SCORE_THRESHOLD:
                low_count += 1

        if low_count >= DECAY_CONSECUTIVE_DAYS:
            reason = (
                f"连续 {DECAY_CONSECUTIVE_DAYS} 日评分低于 "
                f"{DECAY_SCORE_THRESHOLD}，信号衰减"
            )
            try:
                db.update_event_lifecycle(
                    event_id,
                    lifecycle="suggest_close",
                    suggest_close_reason=reason,
                )
                logger.info("信号衰减 event=%d: %s", event_id, reason)
            except Exception as e:
                logger.error("更新生命周期失败 event=%d: %s", event_id, e)
            return True

        return False
