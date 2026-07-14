#!/usr/bin/env python3
"""缠论全市场每日扫描脚本

使用方式：
  python3 scripts/chanlun_scan.py                # 扫描全市场
  python3 scripts/chanlun_scan.py --stock 600519 # 扫描单只
  python3 scripts/chanlun_scan.py --top 50       # 只扫描市值前50
  
触发时机：每日15:30收盘后（通过cron或systemd timer）
数据来源：MySQL stock_data_daily 表
输出：chanlun_signals + chanlun_pivots 表写入
"""
import sys
import os
import json
import argparse
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from chanlun.engine.fractal import identify_fractals
from chanlun.engine.stroke import build_strokes
from chanlun.engine.pivot import find_pivots
from chanlun.engine.divergence import compute_macd, find_trend_divergence
from chanlun.signals.buy_sell import detect_buy3, detect_buy2, detect_buy1
from chanlun.signals.scorer import score_signal, get_action_suggestion
from chanlun.engine.types import PivotStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("chanlun_scan")

# DB配置
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "password",
    "database": "stock_analysis_system",
    "charset": "utf8mb4"
}

# 扫描参数
LOOKBACK_DAYS = 120       # 回看120根K线
MIN_TURNOVER = 3e8        # 最低日均成交额3亿
MIN_SCORE = 60            # 最低入库评分


def get_db():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)



def get_stock_pool(conn, top_n=None):
    """获取待扫描股票池"""
    sql = "SELECT stock_code, stock_code as stock_name FROM stock_data_daily WHERE date >= DATE_SUB(CURDATE(), INTERVAL 20 DAY) GROUP BY stock_code HAVING AVG(turnover) >= %s ORDER BY AVG(turnover) DESC"
    if top_n:
        sql += " LIMIT %d" % top_n
    
    with conn.cursor() as cur:
        cur.execute(sql, (MIN_TURNOVER,))
        rows = cur.fetchall()
    
    filtered = []
    for r in rows:
        c = r["stock_code"]
        if c[:3] in ("000","001","002","003","300","600","601","603","605"):
            filtered.append(r)
    return filtered


def get_klines(conn, stock_code, days=LOOKBACK_DAYS):
    """从MySQL获取K线数据"""
    sql = """
        SELECT date as dt, open, high, low, close, volume
        FROM stock_data_daily
        WHERE stock_code = %s
        ORDER BY date DESC
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (stock_code, days))
        rows = cur.fetchall()
    
    # 倒序回来（按时间正序）
    rows.reverse()
    
    # 转换格式
    klines = []
    for r in rows:
        klines.append({
            "dt": str(r["dt"]),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r["volume"])
        })
    return klines


def analyze_stock(klines, stock_code, stock_name):
    """对单只股票执行缠论分析"""
    if len(klines) < 30:
        return None, None
    
    # 引擎链路
    merged_klines, fractals = identify_fractals(klines)
    strokes = build_strokes(fractals)
    pivots = find_pivots(strokes)
    
    if not strokes or not pivots:
        return pivots, None
    
    # MACD
    closes = [k["close"] for k in klines]
    dif, dea, macd_bar = compute_macd(closes)
    divergence = find_trend_divergence(strokes, pivots, macd_bar, dif)
    
    current_price = klines[-1]["close"]
    
    # 检测买卖点（按优先级：三买 > 二买 > 一买）
    signal = None
    signal = detect_buy3(strokes, pivots, current_price)
    if not signal:
        signal = detect_buy2(strokes, pivots, divergence)
    if not signal:
        signal = detect_buy1(strokes, pivots, divergence, dif)
    
    if signal:
        # 计算成交量比率
        recent_vol = [k["volume"] for k in klines[-5:]]
        avg_vol = sum(k["volume"] for k in klines[-20:]) / 20 if len(klines) >= 20 else 1
        vol_ratio = (sum(recent_vol) / len(recent_vol)) / avg_vol if avg_vol > 0 else 1.0
        
        macd_dif = dif[-1] if dif else 0
        
        # 评分
        pivot_for_score = pivots[-1] if pivots else None
        signal = score_signal(
            signal,
            pivot=pivot_for_score,
            divergence=divergence,
            volume_ratio=vol_ratio,
            macd_dif=macd_dif,
            market_bullish=True,   # TODO: 接入大盘状态判断
            sector_strong=True,    # TODO: 接入板块强弱判断
            capital_inflow=False   # TODO: 接入资金流向数据
        )
    
    return pivots, signal


def save_pivots(conn, stock_code, pivots):
    """保存中枢数据"""
    if not pivots:
        return
    
    sql = """
        INSERT INTO chanlun_pivots 
        (stock_code, timeframe, pivot_start_date, pivot_end_date, zg, zd, gg, dd, direction, stroke_count, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        pivot_end_date=VALUES(pivot_end_date), status=VALUES(status), updated_at=NOW()
    """
    with conn.cursor() as cur:
        for p in pivots[-3:]:  # 只保存最近3个中枢
            cur.execute(sql, (
                stock_code, "D",
                datetime.now().strftime("%Y-%m-%d"),  # 简化：用当前日期
                datetime.now().strftime("%Y-%m-%d") if p.status == PivotStatus.COMPLETED else None,
                p.zg, p.zd, p.gg, p.dd,
                p.direction.value if p.direction else None,
                len(p.strokes),
                p.status.value
            ))
    conn.commit()


def save_signal(conn, stock_code, stock_name, signal):
    """保存信号数据"""
    if not signal or signal.score < MIN_SCORE:
        return False
    
    sql = """
        INSERT INTO chanlun_signals 
        (stock_code, stock_name, signal_date, timeframe, signal_type, signal_price,
         stop_loss, target_price, score, morphology_score, dynamics_score, 
         environment_score, macd_area_ratio, reason_chain, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            stock_code, stock_name,
            datetime.now().strftime("%Y-%m-%d"),
            "D",
            signal.type.value,
            signal.price,
            signal.stop_loss,
            signal.target,
            signal.score,
            signal.morphology_score,
            signal.dynamics_score,
            signal.environment_score,
            signal.divergence.ratio if signal.divergence else None,
            json.dumps(signal.reason_chain, ensure_ascii=False),
            "pending"
        ))
    conn.commit()
    return True


def run_scan(stock_code=None, top_n=None):
    """执行扫描主流程"""
    conn = get_db()
    
    start_time = datetime.now()
    log.info("=" * 50)
    log.info("缠论全市场扫描开始")
    log.info("=" * 50)
    
    # 获取股票池
    if stock_code:
        pool = [{"stock_code": stock_code, "stock_name": stock_code}]
    else:
        pool = get_stock_pool(conn, top_n=top_n)
    
    log.info(f"股票池: {len(pool)} 只")
    
    total = len(pool)
    signals_found = 0
    errors = 0
    
    for i, stock in enumerate(pool):
        code = stock["stock_code"]
        name = stock.get("stock_name", code)
        
        try:
            klines = get_klines(conn, code)
            if len(klines) < 30:
                continue
            
            pivots, signal = analyze_stock(klines, code, name)
            
            # 保存中枢
            if pivots:
                save_pivots(conn, code, pivots)
            
            # 保存信号
            if signal and signal.score >= MIN_SCORE:
                saved = save_signal(conn, code, name, signal)
                if saved:
                    signals_found += 1
                    log.info(f"  [{signals_found}] {code} {name} | "
                             f"{signal.type.value.upper()} | "
                             f"Score:{signal.score} | "
                             f"Price:{signal.price:.2f} Stop:{signal.stop_loss:.2f}")
        
        except Exception as e:
            errors += 1
            if errors <= 5:
                log.warning(f"  {code} error: {e}")
        
        # 进度日志
        if (i + 1) % 100 == 0:
            log.info(f"  进度: {i+1}/{total} ({(i+1)*100//total}%)")
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    log.info("=" * 50)
    log.info(f"扫描完成: {total}只 | 信号:{signals_found} | 错误:{errors} | 耗时:{elapsed:.1f}s")
    log.info("=" * 50)
    
    conn.close()
    return signals_found


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="缠论全市场每日扫描")
    parser.add_argument("--stock", type=str, help="扫描单只股票代码")
    parser.add_argument("--top", type=int, help="只扫描前N只（按成交额）")
    args = parser.parse_args()
    
    run_scan(stock_code=args.stock, top_n=args.top)
