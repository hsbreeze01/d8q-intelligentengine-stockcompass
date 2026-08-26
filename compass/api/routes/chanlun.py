"""缠论信号API

提供以下端点：
- GET /chanlun/signals          - 获取最新信号列表
- GET /chanlun/signals/<code>   - 获取单只股票的信号详情+结构数据
- GET /chanlun/pivots/<code>    - 获取单只股票的中枢数据
- GET /chanlun/backtest         - 获取最新回测结果
- POST /chanlun/scan            - 手动触发扫描（admin）
"""
from datetime import datetime

import pymysql
from flask import Blueprint, jsonify, request, render_template

from chanlun.engine.czsc_detail import get_stock_detail

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
    sql = """SELECT code AS stock_code, name AS stock_name, signal_date,
                    type AS signal_type, COALESCE(entry_price, price) AS signal_price,
                    stop_loss, target_price, target_type,
                    COALESCE(base_score, score) AS score, score AS total_score,
                    market_env_score AS environment_score,
                    div_ratio AS macd_area_ratio, reason, grade,
                    'pending' AS status
             FROM czsc_signal_history
             WHERE signal_date = %s AND profile = 'default'
               AND COALESCE(base_score, score) >= %s
             ORDER BY COALESCE(base_score, score) DESC LIMIT %s"""
    
    with conn.cursor() as cur:
        cur.execute(sql, (date, min_score, limit))
        rows = cur.fetchall()
    conn.close()
    
    # 格式化
    for r in rows:
        r["signal_date"] = str(r["signal_date"])
        r["reason_chain"] = [r.pop("reason")] if r.get("reason") else []
        r["morphology_score"] = 0
        r["dynamics_score"] = 0
        r["risk_reward"] = 0
        if r["stop_loss"] and r["target_price"] and r["signal_price"]:
            price = float(r["signal_price"])
            stop = float(r["stop_loss"])
            target = float(r["target_price"])
            if r["signal_type"].startswith("buy"):
                risk, reward = price - stop, target - price
            else:
                risk, reward = stop - price, price - target
            r["risk_reward"] = round(reward / risk, 1) if risk > 0 and reward > 0 else 0
    
    return jsonify({"date": date, "count": len(rows), "signals": rows})


@chanlun_bp.route("/signals/<stock_code>", methods=["GET"])
def get_signal_detail(stock_code):
    """获取单只股票的 v3 缠论结构与历史信号。"""
    detail = get_stock_detail(stock_code, limit=120)
    if detail.get("error"):
        return jsonify(detail), 400

    klines = detail["klines"]
    date_idx = {str(k["dt"])[:10]: i for i, k in enumerate(klines)}
    strokes = []
    for bi in detail["bis"]:
        is_up = bi["dir"] == "up"
        strokes.append({
            "start_idx": date_idx.get(str(bi["sdt"])[:10]),
            "end_idx": date_idx.get(str(bi["edt"])[:10]),
            "start_value": bi["low"] if is_up else bi["high"],
            "end_value": bi["high"] if is_up else bi["low"],
            "direction": bi["dir"],
        })
    pivots = [{
        "start_idx": date_idx.get(str(z["sdt"])[:10]),
        "end_idx": date_idx.get(str(z["edt"])[:10]),
        "start_date": z["sdt"],
        "end_date": z["edt"],
        "zg": z["zg"], "zd": z["zd"], "gg": z["gg"], "dd": z["dd"],
        "status": "completed",
    } for z in detail["zs"]]

    conn = get_db()
    sql = """SELECT signal_date, type, COALESCE(entry_price, price) AS price,
                    COALESCE(base_score, score) AS score, reason
             FROM czsc_signal_history
             WHERE code=%s AND profile='default'
             ORDER BY signal_date DESC LIMIT 5"""
    with conn.cursor() as cur:
        cur.execute(sql, (stock_code,))
        db_signals = cur.fetchall()
    conn.close()

    response = {
        "stock_code": stock_code,
        "klines": klines,
        "strokes": strokes,
        "pivots": pivots,
        "divergence": detail["divergence"],
        "trend": detail["trend"],
        "signals": [{
            "type": s["type"], "date": str(s["signal_date"]),
            "price": float(s["price"]) if s["price"] else None,
            "score": s["score"],
            "reason_chain": [s["reason"]] if s["reason"] else [],
        } for s in db_signals]
    }
    return jsonify(response)


@chanlun_bp.route("/pivots/<stock_code>", methods=["GET"])
def get_pivots(stock_code):
    """获取 v3 引擎实时计算的个股中枢。"""
    detail = get_stock_detail(stock_code)
    if detail.get("error"):
        return jsonify(detail), 404
    return jsonify({"stock_code": stock_code, "pivots": detail["zs"]})


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




@chanlun_bp.route("/detail", methods=["GET"])
def chanlun_detail_page():
    """缠论信号详情页（图表可视化）"""
    stock_code = request.args.get("code", "002384")
    return render_template("chanlun_detail.html", stock_code=stock_code)

# infopublisher推送集成
def push_high_score_signals(min_score=75):
    """将高分信号推送到infopublisher
    
    调用 49.234.48.221:8089 的推送接口
    """
    import requests
    
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    
    sql = """SELECT code AS stock_code, name AS stock_name, type AS signal_type,
                    COALESCE(entry_price, price) AS signal_price,
                    stop_loss, target_price, COALESCE(base_score, score) AS score,
                    reason
             FROM czsc_signal_history
             WHERE signal_date=%s AND profile='default'
               AND COALESCE(base_score, score) >= %s AND notified_at IS NULL"""
    
    with conn.cursor() as cur:
        cur.execute(sql, (today, min_score))
        signals = cur.fetchall()
    
    if not signals:
        return 0
    
    # 构建推送内容
    lines = [f"📊 缠论信号扫描 ({today})", f"共 {len(signals)} 个高分信号：", ""]
    
    for s in signals:
        type_name = {
            "buy1": "一买", "buy2": "二买", "buy3": "三买",
            "sell1": "一卖", "sell2": "二卖", "sell3": "三卖",
        }.get(s["signal_type"], s["signal_type"])
        price = float(s["signal_price"])
        stop = float(s["stop_loss"])
        target = float(s["target_price"]) if s["target_price"] else None
        is_buy = s["signal_type"].startswith("buy")
        risk = price - stop if is_buy else stop - price
        reward = ((target - price) if is_buy else (price - target)) if target else 0
        rr = round(reward / risk, 1) if risk > 0 and reward > 0 else 0
        
        icon = "🟢" if is_buy else "🔴"
        lines.append(f"{icon} {s['stock_code']} | {type_name} | 评分{s['score']}")
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
                cur.execute("""UPDATE czsc_signal_history SET notified_at=NOW()
                               WHERE signal_date=%s AND profile='default'
                                 AND COALESCE(base_score, score)>=%s
                                 AND notified_at IS NULL""",
                            (today, min_score))
            conn.commit()
    except Exception as e:
        print(f"Push failed: {e}")
    
    conn.close()
    return len(signals)


@chanlun_bp.route("/scan", methods=["POST"])
def trigger_scan():
    """手动触发 v3 缠论扫描。
    
    由 factory scheduler 15:35 调用。
    执行 chanlun/strategy/czsc_scan.py 并返回结果。
    """
    import subprocess
    try:
        result = subprocess.run(
            ["/home/ecs-assist-user/d8q-intelligentengine-stockcompass/venv/bin/python3.12",
             "/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/strategy/czsc_scan.py"],
            capture_output=True, text=True, timeout=180,
            cwd="/home/ecs-assist-user/d8q-intelligentengine-stockcompass"
        )
        if result.returncode == 0:
            return jsonify({"status": "ok", "output": result.stdout.strip()[-500:]})
        else:
            return jsonify({"status": "error", "stderr": result.stderr[:500]}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "message": "scan timeout (180s)"}), 504
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
