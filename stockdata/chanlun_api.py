"""缠论信号API

提供以下端点：
- GET /chanlun/signals          - 获取最新信号列表
- GET /chanlun/signals/<code>   - 获取单只股票的信号详情+结构数据
- GET /chanlun/pivots/<code>    - 获取单只股票的中枢数据
- GET /chanlun/backtest         - 获取最新回测结果
- POST /chanlun/scan            - 手动触发扫描（admin）
"""
import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from flask import Blueprint, jsonify, request

from chanlun.engine.fractal import identify_fractals
from chanlun.engine.stroke import build_strokes
from chanlun.engine.pivot import find_pivots
from chanlun.engine.divergence import compute_macd, find_trend_divergence
from chanlun.signals.buy_sell import detect_buy3
from chanlun.engine.types import Direction, PivotStatus

chanlun_bp = Blueprint("chanlun", __name__, url_prefix="/chanlun")

DB_CONFIG = {
    "host": "127.0.0.1", "port": 3306, "user": "root",
    "password": "password", "database": "stock_analysis_system",
    "charset": "utf8mb4"
}


def get_db():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)


@chanlun_bp.route("/signals", methods=["GET"])
def get_signals():
    """获取最新信号列表
    
    Query params:
      - date: 日期（默认今天）
      - min_score: 最低评分（默认60）
      - limit: 数量限制（默认20）
    """
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    min_score = int(request.args.get("min_score", 60))
    limit = int(request.args.get("limit", 20))
    
    conn = get_db()
    sql = """SELECT stock_code, stock_name, signal_date, signal_type, 
                    signal_price, stop_loss, target_price, 
                    score, morphology_score, dynamics_score, environment_score,
                    macd_area_ratio, reason_chain, status
             FROM chanlun_signals 
             WHERE signal_date = %s AND score >= %s
             ORDER BY score DESC LIMIT %s"""
    
    with conn.cursor() as cur:
        cur.execute(sql, (date, min_score, limit))
        rows = cur.fetchall()
    conn.close()
    
    # 格式化
    for r in rows:
        r["signal_date"] = str(r["signal_date"])
        if r["reason_chain"]:
            try:
                r["reason_chain"] = json.loads(r["reason_chain"])
            except:
                pass
        # 计算盈亏比
        if r["stop_loss"] and r["target_price"] and r["signal_price"]:
            risk = float(r["signal_price"]) - float(r["stop_loss"])
            reward = float(r["target_price"]) - float(r["signal_price"])
            r["risk_reward"] = round(reward / risk, 1) if risk > 0 else 0
    
    return jsonify({"date": date, "count": len(rows), "signals": rows})


@chanlun_bp.route("/signals/<stock_code>", methods=["GET"])
def get_signal_detail(stock_code):
    """获取单只股票的缠论结构数据（用于图表渲染）
    
    返回: K线数据 + 笔序列 + 中枢 + 信号 + MACD面积
    """
    conn = get_db()
    
    # 获取K线
    sql = """SELECT date as dt, open, high, low, close, volume 
             FROM stock_data_daily WHERE stock_code=%s 
             ORDER BY date DESC LIMIT 120"""
    with conn.cursor() as cur:
        cur.execute(sql, (stock_code,))
        rows = cur.fetchall()
    
    rows.reverse()
    klines = [{"dt": str(r["dt"]), "open": float(r["open"]), "high": float(r["high"]),
               "low": float(r["low"]), "close": float(r["close"]), "volume": float(r["volume"])} for r in rows]
    
    if len(klines) < 30:
        return jsonify({"error": "insufficient data"}), 400
    
    # 运行引擎
    merged, fractals = identify_fractals(klines)
    strokes = build_strokes(fractals)
    pivots = find_pivots(strokes)
    
    closes = [k["close"] for k in klines]
    dif, dea, macd_bar = compute_macd(closes)
    divergence = find_trend_divergence(strokes, pivots, macd_bar, dif)
    
    # 获取数据库中的信号
    sql2 = """SELECT * FROM chanlun_signals WHERE stock_code=%s ORDER BY signal_date DESC LIMIT 5"""
    with conn.cursor() as cur:
        cur.execute(sql2, (stock_code,))
        db_signals = cur.fetchall()
    
    conn.close()
    
    # 格式化输出（前端图表所需的全部数据）
    response = {
        "stock_code": stock_code,
        "klines": klines,
        "strokes": [
            {"start_idx": s.start_idx, "end_idx": s.end_idx,
             "start_value": s.start_value, "end_value": s.end_value,
             "direction": s.direction.value}
            for s in strokes
        ],
        "pivots": [
            {"start_idx": p.start_idx, "end_idx": p.end_idx,
             "zg": p.zg, "zd": p.zd, "gg": p.gg, "dd": p.dd,
             "status": p.status.value, "stroke_count": len(p.strokes)}
            for p in pivots
        ],
        "macd": {
            "dif": [round(v, 3) for v in dif],
            "dea": [round(v, 3) for v in dea],
            "bar": [round(v, 3) for v in macd_bar]
        },
        "divergence": {
            "detected": divergence is not None,
            "is_divergent": divergence.is_divergent if divergence else False,
            "area_a": divergence.area_a if divergence else None,
            "area_c": divergence.area_c if divergence else None,
            "ratio": divergence.ratio if divergence else None
        } if divergence else None,
        "signals": [{
            "type": s["signal_type"], "date": str(s["signal_date"]),
            "price": float(s["signal_price"]) if s["signal_price"] else None,
            "score": s["score"],
            "reason_chain": json.loads(s["reason_chain"]) if s["reason_chain"] else []
        } for s in db_signals]
    }
    
    return jsonify(response)


@chanlun_bp.route("/pivots/<stock_code>", methods=["GET"])
def get_pivots(stock_code):
    """获取股票的中枢历史"""
    conn = get_db()
    sql = """SELECT * FROM chanlun_pivots WHERE stock_code=%s ORDER BY created_at DESC LIMIT 10"""
    with conn.cursor() as cur:
        cur.execute(sql, (stock_code,))
        rows = cur.fetchall()
    conn.close()
    
    for r in rows:
        r["pivot_start_date"] = str(r["pivot_start_date"]) if r["pivot_start_date"] else None
        r["pivot_end_date"] = str(r["pivot_end_date"]) if r["pivot_end_date"] else None
        r["created_at"] = str(r["created_at"]) if r["created_at"] else None
        r["updated_at"] = str(r["updated_at"]) if r["updated_at"] else None
    
    return jsonify({"stock_code": stock_code, "pivots": rows})


@chanlun_bp.route("/backtest", methods=["GET"])
def get_backtest():
    """获取最新回测结果"""
    conn = get_db()
    sql = "SELECT * FROM chanlun_backtest ORDER BY created_at DESC LIMIT 5"
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    conn.close()
    
    for r in rows:
        for k in ("run_date", "period_start", "period_end", "created_at"):
            if r.get(k):
                r[k] = str(r[k])
    
    return jsonify({"results": rows})


def add_chanlun_routes(app):
    """注册缠论路由到Flask app"""
    app.register_blueprint(chanlun_bp)


# infopublisher推送集成
def push_high_score_signals(min_score=75):
    """将高分信号推送到infopublisher
    
    调用 49.234.48.221:8089 的推送接口
    """
    import requests
    
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    
    sql = """SELECT stock_code, stock_name, signal_type, signal_price, 
                    stop_loss, target_price, score, reason_chain
             FROM chanlun_signals 
             WHERE signal_date=%s AND score >= %s AND status='pending'"""
    
    with conn.cursor() as cur:
        cur.execute(sql, (today, min_score))
        signals = cur.fetchall()
    
    if not signals:
        return 0
    
    # 构建推送内容
    lines = [f"📊 缠论信号扫描 ({today})", f"共 {len(signals)} 个高分信号：", ""]
    
    for s in signals:
        type_name = {"buy1": "一买", "buy2": "二买", "buy3": "三买"}.get(s["signal_type"], s["signal_type"])
        risk = float(s["signal_price"]) - float(s["stop_loss"])
        reward = float(s["target_price"]) - float(s["signal_price"])
        rr = round(reward / risk, 1) if risk > 0 else 0
        
        lines.append(f"🟢 {s['stock_code']} | {type_name} | 评分{s['score']}")
        lines.append(f"   价格:{s['signal_price']} 止损:{s['stop_loss']} 目标:{s['target_price']} 盈亏比:1:{rr}")
        lines.append("")
    
    content = "\n".join(lines)
    
    # 推送到infopublisher
    try:
        resp = requests.post(
            "http://49.234.48.221:8089/api/notify",
            json={"title": f"缠论信号 {today}", "content": content, "channel": "wechat"},
            timeout=10
        )
        if resp.status_code == 200:
            # 更新状态为已推送
            with conn.cursor() as cur:
                cur.execute("UPDATE chanlun_signals SET status='notified' WHERE signal_date=%s AND score>=%s",
                           (today, min_score))
            conn.commit()
    except Exception as e:
        print(f"Push failed: {e}")
    
    conn.close()
    return len(signals)
