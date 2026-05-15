"""策略组引擎 — 群体事件聚合器"""
import datetime
import logging
import threading

from compass.data.database import Database
from compass.strategy import db as db_helpers

logger = logging.getLogger("compass.strategy.aggregator")


class Aggregator:
    """群体事件聚合器 — 扫描后自动执行"""

    def aggregate(self, strategy_group_id: int, run_id: int, skip_llm: bool = False) -> int:
        """对本次扫描结果执行聚合检测，返回创建/更新的事件数"""
        # 1. 获取策略组配置
        group = db_helpers.get_strategy_group(strategy_group_id)
        if not group:
            return 0

        aggregation = group.get("aggregation", {})
        dimension = aggregation.get("dimension", "industry")
        min_stocks = aggregation.get("min_stocks", 3)
        time_window_minutes = aggregation.get("time_window_minutes", 60)

        # 2. 获取本次扫描的信号快照
        with Database() as db:
            _, signals = db.select_many(
                "SELECT * FROM signal_snapshot WHERE run_id = %s",
                (run_id,),
            )

        if not signals:
            return 0

        # 3. 获取股票的行业/概念/主题信息
        stock_codes = [s["stock_code"] for s in signals]
        dimension_map = self._load_dimension_map(dimension, stock_codes)

        # 4. 按维度值分组
        groups = {}
        for sig in signals:
            dim_val = dimension_map.get(sig["stock_code"], "未知")
            if dim_val not in groups:
                groups[dim_val] = []
            groups[dim_val].append(sig)

        # 5. 对每组进行聚合检测
        events_touched = 0
        now = datetime.datetime.now()
        window_end = now + datetime.timedelta(minutes=time_window_minutes)

        for dim_val, sigs in groups.items():
            if len(sigs) < min_stocks:
                continue

            # 计算聚合指标
            buy_stars = [
                s["buy_star"] for s in sigs if s.get("buy_star") is not None
            ]
            avg_buy_star = (
                round(sum(buy_stars) / len(buy_stars), 2) if buy_stars else None
            )
            max_buy_star = max(buy_stars) if buy_stars else None

            matched_stocks = [
                {
                    "code": s["stock_code"],
                    "name": s.get("stock_name", ""),
                    "buy_star": s.get("buy_star"),
                }
                for s in sigs
            ]

            # 检查是否有可追加的 open 事件
            existing = db_helpers.find_open_event(
                strategy_group_id, dimension, dim_val
            )

            if existing:
                # 检查是否在时间窗口内
                created_at = existing.get("created_at")
                if isinstance(created_at, str):
                    created_at = datetime.datetime.strptime(
                        created_at, "%Y-%m-%d %H:%M:%S"
                    )
                if isinstance(created_at, datetime.datetime):
                    elapsed = (now - created_at).total_seconds() / 60
                    if elapsed <= time_window_minutes:
                        # 追加到已有事件
                        old_matched = existing.get("matched_stocks", [])
                        old_codes = {m.get("code") for m in old_matched}
                        new_matched = [
                            m for m in matched_stocks
                            if m["code"] not in old_codes
                        ]
                        all_matched = old_matched + new_matched
                        all_stars = [
                            m["buy_star"]
                            for m in all_matched
                            if m.get("buy_star") is not None
                        ]

                        db_helpers.update_group_event(
                            existing["id"],
                            stock_count=len(all_matched),
                            avg_buy_star=(
                                round(sum(all_stars) / len(all_stars), 2)
                                if all_stars
                                else None
                            ),
                            max_buy_star=max(all_stars) if all_stars else None,
                            matched_stocks=all_matched,
                        )
                        events_touched += 1
                        continue

                # 超出时间窗口，不追加 → 评估是否创建新事件

            # 创建新事件（lifecycle='tracking'）
            event_id = db_helpers.insert_group_event({
                "strategy_group_id": strategy_group_id,
                "run_id": run_id,
                "dimension": dimension,
                "dimension_value": dim_val,
                "stock_count": len(matched_stocks),
                "avg_buy_star": avg_buy_star,
                "max_buy_star": max_buy_star,
                "matched_stocks": matched_stocks,
                "status": "open",
                "window_start": now.strftime("%Y-%m-%d %H:%M:%S"),
                "window_end": window_end.strftime("%Y-%m-%d %H:%M:%S"),
                "sector_change_pct": db_helpers.calc_sector_change_pct(matched_stocks, now.strftime("%Y-%m-%d")),
            })

            # 设置 lifecycle='tracking'
            try:
                db_helpers.update_event_lifecycle(event_id, lifecycle="tracking")
            except Exception as exc:
                logger.warning("设置 lifecycle 失败 event=%d: %s", event_id, exc)

            events_touched += 1

            # 异步触发 LLM 分析（fire-and-forget）
            if not skip_llm:
                try:
                    self._trigger_llm_analysis(event_id)
                except Exception as exc:
                    logger.warning("触发 LLM 分析失败 event=%d: %s", event_id, exc)

        # 6. 关闭超时事件
        try:
            closed = db_helpers.close_expired_events()
            if closed:
                logger.info("关闭了 %d 个超时群体事件", closed)
        except Exception as exc:
            logger.error("关闭超时事件失败: %s", exc)

        return events_touched

    def _trigger_llm_analysis(self, event_id: int):
        """Fire-and-forget LLM 分析 — 启动后台线程，不阻塞调用方"""
        thread = threading.Thread(
            target=self._llm_analyze_sync,
            args=(event_id,),
            daemon=True,
        )
        thread.start()

    def _llm_analyze_sync(self, event_id: int):
        """后台线程执行 LLM 分析，失败仅 log warning"""
        try:
            from compass.strategy.services.llm_extractor import LLMExtractor
            extractor = LLMExtractor()
            extractor.analyze_event(event_id)
        except Exception as exc:
            logger.warning("LLM 分析失败 event=%d: %s", event_id, exc)

    def _load_dimension_map(self, dimension: str, stock_codes: list) -> dict:
        """加载股票的维度值映射 {stock_code: dimension_value}"""
        result = {}
        if not stock_codes:
            return result

        # 根据维度选择字段
        if dimension == "industry":
            field = "industry"
        elif dimension == "concept":
            field = "concept"  # 预留
        else:
            field = "theme"  # 预留

        with Database() as db:
            placeholders = ",".join(["%s"] * len(stock_codes))
            _, rows = db.select_many(
                f"SELECT code, {field} FROM stock_basic "
                f"WHERE code IN ({placeholders})",
                tuple(stock_codes),
            )
            for r in rows:
                val = r.get(field)
                if val:
                    result[r["code"]] = val
        return result
