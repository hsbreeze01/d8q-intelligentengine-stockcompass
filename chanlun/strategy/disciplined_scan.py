"""纪律化策略扫描+推送（独立入口）

与原有chanlun_scan.py完全隔离。
每日15:35执行，基于UserProfile生成个性化推送。

功能：
1. 全市场扫描 → 生成纪律化信号
2. 检查持仓状态 → 生成出场提醒
3. 推送到企微群
"""
import sys
import os
import json
import time
import logging
from datetime import datetime, date

sys.path.insert(0, "/home/ecs-assist-user/d8q-intelligentengine-stockcompass")

import pymysql
from chanlun.strategy.disciplined import (
    UserProfile, DEFAULT_PROFILE, DisciplinedSignal, HoldingStatus,
    analyze_stock, check_exit, format_signal_push, format_holding_check,
    get_strategy_params, SignalGrade,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("disciplined_scan")

DB_CONFIG = {
    "host": "127.0.0.1", "port": 3306, "user": "root",
    "password": "password", "database": "stock_analysis_system",
    "charset": "utf8mb4"
}

HOLDINGS_FILE = "/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/strategy/holdings.json"
WECOM_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=%s"


def get_db():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)


def get_stock_pool(conn, limit=100):
    """获取扫描标的池：高成交额A股"""
    sql = """SELECT stock_code FROM stock_data_daily
             WHERE date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
             GROUP BY stock_code HAVING AVG(turnover) >= 200000000
             ORDER BY AVG(turnover) DESC LIMIT %s"""
    with conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
    valid_prefix = ("000", "001", "002", "003", "300", "600", "601", "603", "605")
    return [r["stock_code"] for r in rows if r["stock_code"][:3] in valid_prefix]


def get_klines(conn, stock_code, limit=150):
    """获取最近N天K线"""
    sql = """SELECT date as dt, open, high, low, close, volume
             FROM stock_data_daily WHERE stock_code=%s
             ORDER BY date DESC LIMIT %s"""
    with conn.cursor() as cur:
        cur.execute(sql, (stock_code, limit))
        rows = cur.fetchall()
    rows.reverse()
    return [{"dt": str(r["dt"]), "open": float(r["open"]), "high": float(r["high"]),
             "low": float(r["low"]), "close": float(r["close"]), "volume": float(r["volume"])} for r in rows]


def get_stock_name(conn, stock_code):
    """获取股票名称"""
    sql = "SELECT stock_name FROM stock_basic WHERE stock_code=%s LIMIT 1"
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (stock_code,))
            row = cur.fetchone()
            return row["stock_name"] if row else stock_code
    except Exception:
        return stock_code


def load_holdings() -> list:
    """加载持仓数据"""
    if not os.path.exists(HOLDINGS_FILE):
        return []
    try:
        with open(HOLDINGS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_holdings(holdings: list):
    """保存持仓数据"""
    os.makedirs(os.path.dirname(HOLDINGS_FILE), exist_ok=True)
    with open(HOLDINGS_FILE, "w") as f:
        json.dump(holdings, f, ensure_ascii=False, indent=2)


def push_wecom(content: str, webhook_key: str):
    """推送到企微群机器人"""
    import urllib.request
    url = WECOM_WEBHOOK_URL % webhook_key
    body = json.dumps({"msgtype": "markdown", "markdown": {"content": content}}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        if result.get("errcode") == 0:
            log.info("推送成功")
        else:
            log.warning("推送失败: %s", result)
        return result
    except Exception as e:
        log.error("推送异常: %s", e)
        return {"errcode": -1, "errmsg": str(e)}


def scan_signals(profile: UserProfile):
    """扫描全市场，生成纪律化信号"""
    conn = get_db()
    stock_codes = get_stock_pool(conn, limit=100)
    log.info("开始扫描，标的池: %d只", len(stock_codes))

    signals = []
    for code in stock_codes:
        klines = get_klines(conn, code, limit=150)
        if len(klines) < 80:
            continue
        name = get_stock_name(conn, code)
        sig = analyze_stock(klines, code, profile, stock_name=name)
        if sig:
            signals.append(sig)

    conn.close()
    log.info("扫描完成，发现 %d 个可操作信号", len(signals))
    return signals


def check_holdings(profile: UserProfile):
    """检查现有持仓的出场条件"""
    holdings_data = load_holdings()
    if not holdings_data:
        return [], []

    conn = get_db()
    updated_holdings = []
    exit_holdings = []

    for h_data in holdings_data:
        code = h_data["stock_code"]
        # 获取今日K线
        sql = """SELECT close, high FROM stock_data_daily
                 WHERE stock_code=%s ORDER BY date DESC LIMIT 1"""
        with conn.cursor() as cur:
            cur.execute(sql, (code,))
            row = cur.fetchone()

        if not row:
            updated_holdings.append(h_data)
            continue

        today_close = float(row["close"])

        # 重建HoldingStatus
        holding = HoldingStatus(
            stock_code=code,
            stock_name=h_data.get("stock_name", code),
            entry_date=h_data["entry_date"],
            entry_price=h_data["entry_price"],
            position_amount=h_data["position_amount"],
            shares=h_data.get("shares", 100),
            highest_close=max(h_data.get("highest_close", h_data["entry_price"]), today_close),
            hold_days=h_data.get("hold_days", 0),
            trailing_active=h_data.get("trailing_active", False),
        )

        # 检查出场条件
        holding = check_exit(holding, today_close, profile)

        if holding.exit_signal:
            exit_holdings.append(holding)
        else:
            # 更新数据
            h_data["hold_days"] = holding.hold_days
            h_data["highest_close"] = holding.highest_close
            h_data["trailing_active"] = holding.trailing_active
            h_data["current_price"] = today_close
            h_data["pnl_pct"] = holding.pnl_pct
            h_data["pnl_amount"] = holding.pnl_amount
            updated_holdings.append(h_data)

    conn.close()

    # 保存更新后的持仓（移除已出场的）
    save_holdings(updated_holdings)

    return updated_holdings, exit_holdings


def run(profile: UserProfile = None):
    """主执行入口"""
    if profile is None:
        profile = DEFAULT_PROFILE

    today = datetime.now().strftime("%Y-%m-%d")
    log.info("=== 纪律化策略扫描 %s ===", today)
    log.info("用户: %s | 风险: %s | 资金: %d", profile.name, profile.risk_preference, profile.total_capital)

    # 1. 检查持仓
    active_holdings, exit_holdings = check_holdings(profile)
    current_count = len(active_holdings)
    log.info("当前持仓: %d只, 需出场: %d只", current_count, len(exit_holdings))

    # 2. 扫描新信号（只在有空位时）
    new_signals = []
    available_slots = profile.max_holdings - current_count
    if available_slots > 0:
        all_signals = scan_signals(profile)
        # 排除已持有的
        held_codes = {h["stock_code"] for h in active_holdings}
        all_signals = [s for s in all_signals if s.stock_code not in held_codes]
        # 按评分排序取top
        all_signals.sort(key=lambda s: s.score, reverse=True)
        new_signals = all_signals[:available_slots]
    else:
        log.info("持仓已满(%d/%d)，跳过扫描", current_count, profile.max_holdings)

    # 3. 构建推送内容
    messages = []

    # 出场提醒
    if exit_holdings:
        exit_lines = ["## ⚠️ 明日出场提醒", ""]
        for h in exit_holdings:
            exit_lines.append("**%s** %s | %s" % (h.stock_code, h.stock_name, h.exit_reason))
            exit_lines.append("> 持仓%d天 | 盈亏%s%.1f%% (%.0f元) | 明日开盘卖出" % (
                h.hold_days, "+" if h.pnl_pct > 0 else "", h.pnl_pct, h.pnl_amount))
            exit_lines.append("")
        messages.append("\n".join(exit_lines))

    # 新信号
    if new_signals:
        for sig in new_signals:
            messages.append(format_signal_push(sig, profile))
    
    # 持仓状态
    if active_holdings:
        holding_objs = []
        for h in active_holdings:
            holding_objs.append(HoldingStatus(
                stock_code=h["stock_code"],
                stock_name=h.get("stock_name", h["stock_code"]),
                entry_date=h["entry_date"],
                entry_price=h["entry_price"],
                position_amount=h["position_amount"],
                shares=h.get("shares", 100),
                current_price=h.get("current_price", h["entry_price"]),
                highest_close=h.get("highest_close", h["entry_price"]),
                hold_days=h.get("hold_days", 0),
                pnl_pct=h.get("pnl_pct", 0),
                pnl_amount=h.get("pnl_amount", 0),
                trailing_active=h.get("trailing_active", False),
            ))
        messages.append(format_holding_check(holding_objs, profile))

    # 无任何内容时
    if not messages:
        summary = "## 📐 纪律化策略 (%s)\n\n无新信号，无持仓。\n持仓空位: %d/%d" % (
            today, available_slots, profile.max_holdings)
        messages.append(summary)

    # 4. 推送
    full_message = "\n\n---\n\n".join(messages)
    
    # 添加尾部信息
    params = get_strategy_params(profile)
    full_message += "\n\n---\n> 配置: %s | 止损%d%% | 止盈%d%%/%d%% | 超时%d天 | 仓位%d元/笔" % (
        profile.risk_preference, params["stop_loss_pct"] * 100,
        params["trailing_trigger"] * 100, params["trailing_drawdown"] * 100,
        params["max_hold_days"], params["full_position"])

    if profile.push_channel == "wecom_webhook" and profile.push_webhook_key:
        push_wecom(full_message, profile.push_webhook_key)
    
    # 打印到stdout（调试用）
    print(full_message)

    return {"signals": len(new_signals), "exits": len(exit_holdings), "holdings": len(active_holdings)}


if __name__ == "__main__":
    run()
