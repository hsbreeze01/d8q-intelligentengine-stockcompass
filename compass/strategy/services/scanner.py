"""策略组引擎 — 信号扫描服务"""
import datetime
import logging
import time
from typing import Optional

from compass.data.database import Database
from compass.strategy import db as db_helpers

logger = logging.getLogger("compass.strategy.scanner")


class Scanner:
    """信号扫描引擎 — 从 indicators_daily + stock_analysis 读取数据做条件匹配"""

    def scan(
        self,
        strategy_group_id: int,
        trigger_type: str = "manual",
        run_id: int = None,
        skip_llm: bool = False,
    ) -> dict:
        """执行扫描，返回结果摘要"""
        # 1. 加载策略组
        group = db_helpers.get_strategy_group(strategy_group_id)
        if not group:
            raise ValueError(f"策略组 {strategy_group_id} 不存在")
        if group["status"] != "active":
            raise ValueError(f"策略组 {strategy_group_id} 未处于 active 状态")

        conditions = group["conditions"]
        signal_logic = group["signal_logic"]
        scoring_threshold = group.get("scoring_threshold")

        # 2. 创建或复用运行记录
        if run_id is None:
            run_id = db_helpers.create_run(strategy_group_id, trigger_type=trigger_type)
        start_time = time.time()

        try:
            # 3. 批量读取最新指标数据 + buy 值
            indicators_rows = self._load_latest_indicators()
            buy_map = self._load_buy_values()

            if not indicators_rows:
                db_helpers.update_run(run_id, status="completed", matched_stocks=0, total_stocks=0)
                return {"run_id": run_id, "matched_count": 0, "total_stocks": 0}

            # 4. 遍历匹配
            matched = []
            for row in indicators_rows:
                stock_code = row.get("stock_code", "")
                indicator_values = self._build_indicator_values(row)
                if self._match(indicator_values, conditions, signal_logic, scoring_threshold):
                    matched.append({
                        "strategy_group_id": strategy_group_id,
                        "run_id": run_id,
                        "stock_code": stock_code,
                        "stock_name": row.get("stock_name", ""),
                        "indicator_snapshot": indicator_values,
                        "buy_star": buy_map.get(stock_code),
                    })

            # 5. 写入 signal_snapshot
            db_helpers.insert_signal_snapshots(matched)

            duration = time.time() - start_time
            db_helpers.update_run(
                run_id,
                total_stocks=len(indicators_rows),
                matched_stocks=len(matched),
                status="completed",
                duration_seconds=round(duration, 2),
                finished_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )

            logger.info(
                "[strategy.scanner] strategy_group_id=%d matched=%d total=%d duration=%.1fs",
                strategy_group_id,
                len(matched),
                len(indicators_rows),
                duration,
            )

            # 6. 触发聚合器
            events_created = 0
            try:
                from compass.strategy.services.aggregator import Aggregator
                agg = Aggregator()
                events_created = agg.aggregate(strategy_group_id, run_id, skip_llm=skip_llm)
            except Exception as exc:
                logger.error("聚合器执行失败: %s", exc, exc_info=True)

            return {
                "run_id": run_id,
                "matched_count": len(matched),
                "total_stocks": len(indicators_rows),
                "duration_seconds": round(duration, 2),
                "events_created": events_created,
            }

        except Exception as exc:
            db_helpers.update_run(
                run_id,
                status="failed",
                error_message=str(exc),
                finished_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            raise

    def _load_latest_indicators(self) -> list:
        """读取每只股票最新一条指标，并附带前一交易日指标。"""
        with Database() as db:
            _, row = db.select_one("SELECT MAX(date) as latest FROM indicators_daily")
            if not row or not row.get("latest"):
                return []

            _, rows = db.select_many(
                """
                SELECT curr.*
                FROM indicators_daily curr
                INNER JOIN (
                    SELECT stock_code, MAX(date) AS latest_date
                    FROM indicators_daily
                    GROUP BY stock_code
                ) latest
                    ON curr.stock_code = latest.stock_code
                    AND curr.date = latest.latest_date
                INNER JOIN (
                    SELECT stock_code, date, MAX(id) AS latest_id
                    FROM indicators_daily
                    GROUP BY stock_code, date
                ) dedup
                    ON curr.stock_code = dedup.stock_code
                    AND curr.date = dedup.date
                    AND curr.id = dedup.latest_id
                ORDER BY curr.stock_code
                """
            )
            if not rows:
                return []

            _, prev_rows = db.select_many(
                """
                SELECT prev.*
                FROM indicators_daily prev
                INNER JOIN (
                    SELECT p.stock_code, MAX(p.date) AS prev_date
                    FROM indicators_daily p
                    INNER JOIN (
                        SELECT stock_code, MAX(date) AS latest_date
                        FROM indicators_daily
                        GROUP BY stock_code
                    ) latest
                        ON p.stock_code = latest.stock_code
                        AND p.date < latest.latest_date
                    GROUP BY p.stock_code
                ) prev_date
                    ON prev.stock_code = prev_date.stock_code
                    AND prev.date = prev_date.prev_date
                INNER JOIN (
                    SELECT stock_code, date, MAX(id) AS latest_id
                    FROM indicators_daily
                    GROUP BY stock_code, date
                ) dedup
                    ON prev.stock_code = dedup.stock_code
                    AND prev.date = dedup.date
                    AND prev.id = dedup.latest_id
                """
            )
            prev_map = {r.get("stock_code"): r for r in prev_rows}
            merged_rows = []
            for row in rows:
                merged = dict(row)
                prev = prev_map.get(row.get("stock_code"), {})
                for key, value in prev.items():
                    if key not in ("id", "stock_code"):
                        merged[f"prev_{key}"] = value
                merged_rows.append(merged)
            return merged_rows

    def _load_buy_values(self) -> dict:
        """从 stock_analysis 读取每只股票最新 buy 值，返回 {stock_code: buy}"""
        result = {}
        with Database() as db:
            _, rows = db.select_many(
                """
                SELECT sa.stock_code, sa.buy
                FROM stock_analysis sa
                INNER JOIN (
                    SELECT stock_code, MAX(id) AS latest_id
                    FROM stock_analysis
                    WHERE buy IS NOT NULL
                    GROUP BY stock_code
                ) latest
                    ON sa.stock_code = latest.stock_code
                    AND sa.id = latest.latest_id
                """
            )
            for r in rows:
                result[r.get("stock_code", "")] = r.get("buy")
        return result

    def _build_indicator_values(self, row: dict) -> dict:
        """构造当前值、昨日值和日变动派生值。"""
        ignored = {"id", "stock_code", "stock_name", "date", "trade_date", "prev_date", "prev_trade_date"}
        values = {
            k: self._safe_float(v)
            for k, v in row.items()
            if k not in ignored
        }
        for key, current in list(values.items()):
            if key.startswith("prev_") or current is None:
                continue
            previous = values.get(f"prev_{key}")
            if previous is None:
                continue
            values[f"{key}_delta"] = current - previous
            if abs(previous) > 1e-9:
                values[f"{key}_pct_change"] = (current - previous) / abs(previous)
        return values

    def _match(
        self,
        indicator_values: dict,
        conditions: list,
        signal_logic: str,
        scoring_threshold: Optional[int],
    ) -> bool:
        """根据条件和逻辑判断是否匹配"""
        if signal_logic == "AND":
            return all(self._eval_condition(indicator_values, c) for c in conditions)
        elif signal_logic == "OR":
            return any(self._eval_condition(indicator_values, c) for c in conditions)
        elif signal_logic == "SCORING":
            score = sum(1 for c in conditions if self._eval_condition(indicator_values, c))
            threshold = scoring_threshold or len(conditions)
            return score >= threshold
        return False

    def _eval_condition(self, indicator_values: dict, condition: dict) -> bool:
        """评估单个条件"""
        indicator = condition.get("indicator", "")
        operator = condition.get("operator", "")
        threshold = self._resolve_threshold(indicator_values, condition)

        current = indicator_values.get(indicator)

        if current is None:
            return False

        current = self._safe_float(current)

        if current is None or threshold is None:
            return False

        if operator == ">":
            return current > threshold
        elif operator == "<":
            return current < threshold
        elif operator == ">=":
            return current >= threshold
        elif operator == "<=":
            return current <= threshold
        elif operator == "==":
            return abs(current - threshold) < 1e-9
        elif operator == "cross_above":
            previous = self._safe_float(indicator_values.get(f"prev_{indicator}"))
            previous_threshold = self._resolve_previous_threshold(indicator_values, condition, threshold)
            return (
                previous is not None
                and previous_threshold is not None
                and previous <= previous_threshold
                and current > threshold
            )
        elif operator == "cross_below":
            previous = self._safe_float(indicator_values.get(f"prev_{indicator}"))
            previous_threshold = self._resolve_previous_threshold(indicator_values, condition, threshold)
            return (
                previous is not None
                and previous_threshold is not None
                and previous >= previous_threshold
                and current < threshold
            )
        return False

    def _resolve_threshold(self, indicator_values: dict, condition: dict) -> Optional[float]:
        """解析条件右侧，可为固定数值，也可为另一指标字段。"""
        compare_to = condition.get("compare_to") or condition.get("compare_indicator")
        if compare_to:
            return self._safe_float(indicator_values.get(compare_to))
        return self._safe_float(condition.get("value"))

    def _resolve_previous_threshold(
        self,
        indicator_values: dict,
        condition: dict,
        current_threshold: float,
    ) -> Optional[float]:
        compare_to = condition.get("compare_to") or condition.get("compare_indicator")
        if not compare_to:
            return current_threshold
        return self._safe_float(indicator_values.get(f"prev_{compare_to}"))

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        """安全转换为 float"""
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None
