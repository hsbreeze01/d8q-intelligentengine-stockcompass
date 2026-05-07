"""每日推荐股票评分引擎 — 纯 Python 确定性计算"""
import json
import logging
import time
import datetime
from typing import List, Optional, Tuple

from compass.data.database import Database

logger = logging.getLogger(__name__)

# 权重配置
WEIGHT_TECHNICAL = 0.40
WEIGHT_TREND = 0.25
WEIGHT_FUNDAMENTAL = 0.20
WEIGHT_VOLUME = 0.15

# 排除阈值
MIN_TURNOVER_AMOUNT = 50_000_000   # 5000 万
MIN_TURNOVER_RATE = 0.5            # 0.5%
MAX_CHANGE_PERCENTAGE = 9.5        # 涨跌幅上限


def _filter_eligible(stocks: List[dict]) -> List[dict]:
    """排除不符合条件的股票：ST、低流动性、涨跌幅异常。

    Parameters
    ----------
    stocks : list[dict]
        dic_stock 查询结果，每条记录需包含
        stock_name / latest_price / turnover_rate 等字段。

    Returns
    -------
    list[dict]
        过滤后的股票列表
    """
    eligible = []
    for s in stocks:
        name = s.get("stock_name") or s.get("cns_name") or ""
        # 排除 ST 股票
        if "ST" in name.upper():
            continue

        # 排除涨跌幅异常（当日涨跌幅超过 ±9.5%）
        change_pct = s.get("change_percentage")
        if change_pct is not None:
            try:
                change_pct = abs(float(change_pct))
                if change_pct > MAX_CHANGE_PERCENTAGE:
                    continue
            except (TypeError, ValueError):
                pass

        # 排除流动性不足：成交额低于 5000 万
        turnover_amount = s.get("turnover") or s.get("turnover_amount")
        if turnover_amount is not None:
            try:
                if float(turnover_amount) < MIN_TURNOVER_AMOUNT:
                    continue
            except (TypeError, ValueError):
                pass

        # 排除换手率低于 0.5%
        turnover_rate = s.get("turnover_rate")
        if turnover_rate is not None:
            try:
                if float(turnover_rate) < MIN_TURNOVER_RATE:
                    continue
            except (TypeError, ValueError):
                pass

        eligible.append(s)
    return eligible


def _calc_technical_score(buy: int, sell: int) -> float:
    """技术指标评分 — 基于 stock_analysis 的 buy/sell 信号数量。

    归一化到 0-100：buy 越多分越高，sell 越多分越低。
    公式：50 + (buy - sell) * 10，clamp 到 [0, 100]。
    """
    raw = 50 + (buy - sell) * 10
    return round(max(0.0, min(100.0, raw)), 2)


def _calc_trend_score(rows: List[dict]) -> float:
    """趋势动量评分 — 基于近 20 日行情的 MA 排列和涨跌幅。

    Parameters
    ----------
    rows : list[dict]
        stock_data_daily 最近 20 日数据，按 date 升序，需包含
        close / ma5 / ma10 / ma20 / ma30 / change_percentage 字段。

    Returns
    -------
    float
        0-100 分
    """
    if not rows:
        return 0.0

    score = 50.0

    # 1) MA 多头排列加分：MA5 > MA10 > MA20 > MA30
    latest = rows[-1]
    ma5 = _safe_float(latest.get("ma5"))
    ma10 = _safe_float(latest.get("ma10"))
    ma20 = _safe_float(latest.get("ma20"))
    ma30 = _safe_float(latest.get("ma30"))

    if ma5 and ma10 and ma20 and ma30:
        if ma5 > ma10 > ma20 > ma30:
            score += 25
        elif ma5 > ma10 > ma20:
            score += 15
        elif ma5 > ma10:
            score += 5

    # 2) 近 5 日涨跌幅加分
    if len(rows) >= 5:
        try:
            changes = [float(r.get("change_percentage", 0)) for r in rows[-5:]]
            avg_change = sum(changes) / len(changes)
            # 合理范围（非暴涨）加分
            if 0 < avg_change <= 3:
                score += 15
            elif 3 < avg_change <= 5:
                score += 5
            elif avg_change > 5:
                score -= 5  # 暴涨视为风险
            elif -2 <= avg_change <= 0:
                score += 0  # 微跌不加不减
            else:
                score -= 10  # 大跌
        except (TypeError, ValueError):
            pass

    return round(max(0.0, min(100.0, score)), 2)


def _calc_fundamental_score(stock: dict) -> float:
    """基本面评分 — 基于 PE、PB、市值、换手率。

    Parameters
    ----------
    stock : dict
        dic_stock 行数据，需包含 pe / pb / outstanding / turnover_rate 字段。

    Returns
    -------
    float
        0-100 分
    """
    score = 50.0

    pe = _safe_float(stock.get("pe"))
    pb = _safe_float(stock.get("pb"))

    # PE 在 10-30 区间加分
    if pe is not None:
        if 10 <= pe <= 30:
            score += 20
        elif 0 < pe < 10:
            score += 10
        elif 30 < pe <= 50:
            score += 5
        elif pe < 0:
            score -= 30  # 亏损股大幅扣分

    # PB 在 1-3 区间加分
    if pb is not None:
        if 1 <= pb <= 3:
            score += 15
        elif 0 < pb < 1:
            score += 8
        elif 3 < pb <= 5:
            score += 3

    # 市值合理加分（outstanding * latest_price 近似）
    outstanding = _safe_float(stock.get("outstanding"))
    if outstanding is not None:
        outstanding_yi = outstanding / 1e8  # 转换为亿
        if 10 <= outstanding_yi <= 500:
            score += 10

    return round(max(0.0, min(100.0, score)), 2)


def _calc_volume_score(rows: List[dict]) -> float:
    """量价配合评分 — 基于近 10 日量价数据。

    Parameters
    ----------
    rows : list[dict]
        stock_data_daily 最近 10 日数据，按 date 升序，需包含
        close / volume 字段。

    Returns
    -------
    float
        0-100 分
    """
    if len(rows) < 2:
        return 50.0

    score = 50.0

    # 对最近几天的量价关系打分
    price_up_vol_up = 0
    price_down_vol_down = 0
    total_days = 0

    for i in range(1, len(rows)):
        try:
            prev_close = float(rows[i - 1].get("close", 0))
            curr_close = float(rows[i].get("close", 0))
            prev_vol = float(rows[i - 1].get("volume", 0))
            curr_vol = float(rows[i].get("volume", 0))

            if prev_close == 0 or prev_vol == 0:
                continue

            price_up = curr_close > prev_close
            vol_up = curr_vol > prev_vol

            if price_up and vol_up:
                price_up_vol_up += 1
            elif not price_up and not vol_up:
                price_down_vol_down += 1

            total_days += 1
        except (TypeError, ValueError):
            continue

    if total_days > 0:
        # 量价齐升占比例越高越好
        score += (price_up_vol_up / total_days) * 30
        # 价格下跌缩量给中等分数（不完全扣分）
        score += (price_down_vol_down / total_days) * 10

    return round(max(0.0, min(100.0, score)), 2)


def _generate_reason(
    stock_name: str,
    technical_score: float,
    trend_score: float,
    fundamental_score: float,
    volume_score: float,
    buy: int,
    sell: int,
) -> str:
    """生成推荐理由文本（规则模板拼接）。

    Returns
    -------
    str
        不超过 200 字的中文推荐理由
    """
    scores = {
        "技术指标": technical_score,
        "趋势动量": trend_score,
        "基本面质量": fundamental_score,
        "量价配合": volume_score,
    }
    best_dim = max(scores, key=scores.get)
    best_score = scores[best_dim]

    parts = [f"{stock_name}综合推荐评分较高。"]
    parts.append(f"其中{best_dim}维度表现突出（{best_score}分）。")

    if buy > 0:
        parts.append(f"技术面触发{buy}个买入信号。")
    if technical_score >= 70:
        parts.append("技术面呈现强势。")
    if trend_score >= 70:
        parts.append("均线多头排列，趋势向好。")
    if fundamental_score >= 70:
        parts.append("基本面估值合理。")
    if volume_score >= 70:
        parts.append("量价配合良好。")

    reason = "".join(parts)
    return reason[:200]


def _generate_risk_warning(
    stock_name: str,
    technical_score: float,
    trend_score: float,
    fundamental_score: float,
    volume_score: float,
    is_st: bool = False,
    high_change: bool = False,
) -> str:
    """生成风险提示文本（规则模板拼接）。

    Returns
    -------
    str
        不超过 200 字的中文风险提示
    """
    scores = {
        "技术指标": technical_score,
        "趋势动量": trend_score,
        "基本面质量": fundamental_score,
        "量价配合": volume_score,
    }
    worst_dim = min(scores, key=scores.get)
    worst_score = scores[worst_dim]

    parts = []
    if is_st:
        parts.append("该股票为ST标的，投资风险较高。")
    if high_change:
        parts.append("该股票当日涨跌幅异常，波动风险较大。")

    parts.append(f"需注意{worst_dim}维度得分较低（{worst_score}分）。")

    if fundamental_score < 40:
        parts.append("基本面存在隐患，建议关注财务数据。")
    if technical_score < 40:
        parts.append("技术面偏弱，注意控制仓位。")
    if trend_score < 40:
        parts.append("趋势不明朗，建议谨慎操作。")

    warning = "".join(parts)
    return warning[:200]


def _safe_float(val) -> Optional[float]:
    """Safely convert value to float."""
    if val is None:
        return None
    try:
        f = float(val)
        return f if f != 0 else None
    except (TypeError, ValueError):
        return None


class RecommendationService:
    """每日推荐股票服务 — 评分 + 查询"""

    def generate_daily(self, target_date: Optional[str] = None) -> dict:
        """执行每日推荐计算并写入数据库。

        Parameters
        ----------
        target_date : str, optional
            目标日期，格式 YYYY-MM-DD。默认为今天。

        Returns
        -------
        dict
            {"count": int, "elapsed_seconds": float}
        """
        start_time = time.time()
        today = target_date or datetime.date.today().isoformat()

        with Database() as db:
            # 1. 读取全市场股票列表
            _, stocks = db.select_many(
                "SELECT d.code AS stock_code, d.stock_name, d.pe, d.pb, "
                "d.outstanding, d.turnover_rate, d.latest_price, "
                "s.change_percentage, s.turnover "
                "FROM dic_stock d "
                "LEFT JOIN stock_data_daily s "
                "ON d.code = s.stock_code AND s.date = %s "
                "WHERE d.latest_price > 0 AND d.status = 0",
                (today,),
            )

            # 2. 过滤
            eligible = _filter_eligible(stocks)
            logger.info("推荐候选股票: %d / %d", len(eligible), len(stocks))

            # 3. 逐只评分
            scored = []
            for stock in eligible:
                code = stock["stock_code"]
                name = stock.get("stock_name") or ""

                # 技术指标评分
                buy, sell = 0, 0
                _, analysis = db.select_one(
                    "SELECT buy, sell FROM stock_analysis "
                    "WHERE stock_code = %s AND record_time = %s",
                    (code, today),
                )
                if analysis:
                    buy = analysis.get("buy", 0) or 0
                    sell = analysis.get("sell", 0) or 0
                tech_score = _calc_technical_score(buy, sell)

                # 趋势动量评分
                _, trend_rows = db.select_many(
                    "SELECT close, change_percentage FROM stock_data_daily "
                    "WHERE stock_code = %s AND date <= %s "
                    "ORDER BY date DESC LIMIT 20",
                    (code, today),
                )
                trend_rows.reverse()
                trend_score = _calc_trend_score(trend_rows)

                # 基本面评分
                fund_score = _calc_fundamental_score(stock)

                # 量价配合评分
                _, vol_rows = db.select_many(
                    "SELECT close, volume FROM stock_data_daily "
                    "WHERE stock_code = %s AND date <= %s "
                    "ORDER BY date DESC LIMIT 10",
                    (code, today),
                )
                vol_rows.reverse()
                vol_score = _calc_volume_score(vol_rows)

                # 加权总分
                total = (
                    tech_score * WEIGHT_TECHNICAL
                    + trend_score * WEIGHT_TREND
                    + fund_score * WEIGHT_FUNDAMENTAL
                    + vol_score * WEIGHT_VOLUME
                )
                total = round(total, 2)

                scored.append({
                    "stock_code": code,
                    "stock_name": name,
                    "total_score": total,
                    "technical_score": tech_score,
                    "trend_score": trend_score,
                    "fundamental_score": fund_score,
                    "volume_score": vol_score,
                    "buy": buy,
                    "sell": sell,
                })

            # 4. 排序取 Top N
            scored.sort(key=lambda x: x["total_score"], reverse=True)
            top_n = scored[:50]

            # 5. 生成理由并写入
            generated_at = datetime.datetime.now()
            for rank, item in enumerate(top_n, start=1):
                is_st = "ST" in (item["stock_name"] or "").upper()
                high_change = False
                # 检查涨跌幅
                _, latest = db.select_one(
                    "SELECT change_percentage FROM stock_data_daily "
                    "WHERE stock_code = %s AND date = %s",
                    (item["stock_code"], today),
                )
                if latest:
                    cp = _safe_float(latest.get("change_percentage"))
                    if cp is not None and abs(cp) > 7:
                        high_change = True

                reason = _generate_reason(
                    item["stock_name"],
                    item["technical_score"],
                    item["trend_score"],
                    item["fundamental_score"],
                    item["volume_score"],
                    item["buy"],
                    item["sell"],
                )
                risk = _generate_risk_warning(
                    item["stock_name"],
                    item["technical_score"],
                    item["trend_score"],
                    item["fundamental_score"],
                    item["volume_score"],
                    is_st=is_st,
                    high_change=high_change,
                )

                db.execute(
                    "INSERT INTO daily_recommendation "
                    "(stock_code, stock_name, recommendation_date, "
                    "total_score, technical_score, trend_score, "
                    "fundamental_score, volume_score, rank, "
                    "reason, risk_warning, generated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE "
                    "total_score=VALUES(total_score), "
                    "technical_score=VALUES(technical_score), "
                    "trend_score=VALUES(trend_score), "
                    "fundamental_score=VALUES(fundamental_score), "
                    "volume_score=VALUES(volume_score), "
                    "rank=VALUES(rank), "
                    "reason=VALUES(reason), "
                    "risk_warning=VALUES(risk_warning), "
                    "generated_at=VALUES(generated_at)",
                    (
                        item["stock_code"],
                        item["stock_name"],
                        today,
                        item["total_score"],
                        item["technical_score"],
                        item["trend_score"],
                        item["fundamental_score"],
                        item["volume_score"],
                        rank,
                        reason,
                        risk,
                        generated_at,
                    ),
                )

            elapsed = time.time() - start_time
            logger.info("推荐计算完成: %d 只, 耗时 %.1f 秒", len(top_n), elapsed)

        return {"count": len(top_n), "elapsed_seconds": round(elapsed, 2)}

    def get_daily(
        self,
        date: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """查询指定日期的推荐列表。

        Parameters
        ----------
        date : str, optional
            日期字符串 YYYY-MM-DD，默认当天。
        limit : int
            返回数量上限。
        offset : int
            偏移量。

        Returns
        -------
        dict
            {recommendations: [...], total: int, generated_at: str|None}
        """
        target = date or datetime.date.today().isoformat()

        with Database() as db:
            # 总数
            _, count_row = db.select_one(
                "SELECT COUNT(*) AS total FROM daily_recommendation "
                "WHERE recommendation_date = %s",
                (target,),
            )
            total = count_row["total"] if count_row else 0

            if total == 0:
                return {
                    "recommendations": [],
                    "total": 0,
                    "generated_at": None,
                }

            # 排名数据
            _, rows = db.select_many(
                "SELECT stock_code, stock_name, total_score AS score, "
                "rank, reason, risk_warning, recommendation_date, generated_at "
                "FROM daily_recommendation "
                "WHERE recommendation_date = %s "
                "ORDER BY total_score DESC "
                "LIMIT %s OFFSET %s",
                (target, limit, offset),
            )

            generated_at = rows[0]["generated_at"].isoformat() if rows and rows[0].get("generated_at") else None

            recommendations = []
            for r in rows:
                recommendations.append({
                    "stock_code": r["stock_code"],
                    "stock_name": r["stock_name"],
                    "score": float(r["score"]),
                    "rank": r["rank"],
                    "reason": r["reason"],
                    "risk_warning": r["risk_warning"],
                    "recommendation_date": r["recommendation_date"].isoformat() if hasattr(r["recommendation_date"], "isoformat") else str(r["recommendation_date"]),
                })

            return {
                "recommendations": recommendations,
                "total": total,
                "generated_at": generated_at,
            }

    def get_performance(self, date: str) -> dict:
        """推荐效果回溯 — 计算指定日期推荐的后续涨跌幅。

        Parameters
        ----------
        date : str
            推荐日期 YYYY-MM-DD。

        Returns
        -------
        dict
            包含每条推荐的 actual_change_1d / actual_change_5d 及整体统计。
        """
        with Database() as db:
            _, recs = db.select_many(
                "SELECT r.stock_code, r.stock_name, r.total_score AS score, "
                "r.rank, r.reason, r.risk_warning, r.recommendation_date "
                "FROM daily_recommendation r "
                "WHERE r.recommendation_date = %s "
                "ORDER BY r.total_score DESC",
                (date,),
            )

            if not recs:
                return {"recommendations": [], "stats": None}

            results = []
            changes_1d = []
            changes_5d = []

            for rec in recs:
                code = rec["stock_code"]
                rec_date = rec["recommendation_date"]

                # 次日涨跌幅
                _, next_row = db.select_one(
                    "SELECT change_percentage FROM stock_data_daily "
                    "WHERE stock_code = %s AND date > %s "
                    "ORDER BY date LIMIT 1",
                    (code, rec_date),
                )
                change_1d = float(next_row["change_percentage"]) if next_row and next_row.get("change_percentage") is not None else None

                # 5 日涨跌幅
                _, rows_5d = db.select_many(
                    "SELECT close FROM stock_data_daily "
                    "WHERE stock_code = %s AND date > %s "
                    "ORDER BY date LIMIT 5",
                    (code, rec_date),
                )
                change_5d = None
                if len(rows_5d) == 5 and rows_5d[0]["close"]:
                    try:
                        start_price = float(rows_5d[0]["close"])
                        end_price = float(rows_5d[-1]["close"])
                        if start_price > 0:
                            change_5d = round((end_price - start_price) / start_price * 100, 2)
                    except (TypeError, ValueError):
                        pass

                if change_1d is not None:
                    changes_1d.append(change_1d)
                if change_5d is not None:
                    changes_5d.append(change_5d)

                results.append({
                    "stock_code": code,
                    "stock_name": rec["stock_name"],
                    "score": float(rec["score"]),
                    "rank": rec["rank"],
                    "reason": rec["reason"],
                    "risk_warning": rec["risk_warning"],
                    "recommendation_date": rec["recommendation_date"].isoformat() if hasattr(rec["recommendation_date"], "isoformat") else str(rec["recommendation_date"]),
                    "actual_change_1d": change_1d,
                    "actual_change_5d": change_5d,
                })

            # 整体统计
            stats = None
            if changes_1d:
                avg_1d = round(sum(changes_1d) / len(changes_1d), 2)
                win_rate_1d = round(sum(1 for c in changes_1d if c > 0) / len(changes_1d) * 100, 2)
                stats = {
                    "avg_change_1d": avg_1d,
                    "win_rate_1d": win_rate_1d,
                    "count": len(changes_1d),
                }
                if changes_5d:
                    avg_5d = round(sum(changes_5d) / len(changes_5d), 2)
                    win_rate_5d = round(sum(1 for c in changes_5d if c > 0) / len(changes_5d) * 100, 2)
                    stats["avg_change_5d"] = avg_5d
                    stats["win_rate_5d"] = win_rate_5d

            return {"recommendations": results, "stats": stats}
