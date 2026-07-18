# -*- coding: utf-8 -*-
"""czsc新引擎每日扫描(v2): 输出丰富信号缓存供前端展示"""
import sys, json, os, pymysql
from datetime import datetime
sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')
from chanlun.engine.czsc_adapter import build_czsc, valid_pivots
from chanlun.engine.czsc_buysell import detect_all_buys, detect_all_sells
from chanlun.engine.market_state import get_market_state
from chanlun.engine.multi_level import multi_level_ok
from chanlun.engine.czsc_divergence import last_divergence
from chanlun.engine.trend import last_trend
from chanlun.engine.segment_adapter import bis_to_segments, segment_pivots
from chanlun.engine.czsc_scorer import score_signal
from chanlun.engine.holdings_tracker import load_holdings, save_holdings, add_holding, check_exit, update_holdings_daily

DB = {'host':'127.0.0.1','port':3306,'user':'root','password':'password','database':'stock_analysis_system','charset':'utf8mb4'}
CACHE_PATH = '/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/strategy/signals_cache_czsc.json'

def get_stock_pool(conn, limit=150):
    """标的池: 日均成交额>=5亿的A股(含科创板688/北交所301)"""
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute("""SELECT stock_code FROM stock_data_daily WHERE date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                   GROUP BY stock_code HAVING AVG(turnover) >= 500000000
                   ORDER BY AVG(turnover) DESC LIMIT %s""", (limit,))
    valid = ('000','001','002','003','300','301','600','601','603','605','688')
    return [r['stock_code'] for r in cur.fetchall() if r['stock_code'][:3] in valid]

def get_stock_name(conn, code):
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute('SELECT name FROM stock_basic WHERE code=%s LIMIT 1', (code,))
    r = cur.fetchone()
    return r['name'] if r else code

def scan():
    conn = pymysql.connect(**DB)
    pool = get_stock_pool(conn)
    market = get_market_state()
    # 丰富大盘信息
    market['summary'] = market.get('label', '中性')
    market['position'] = '中枢上方' if market.get('above_zg') else ('中枢下方' if market.get('below_zd') else '中枢内')

    signals = []
    cur = conn.cursor(pymysql.cursors.DictCursor)
    for code in pool:
        cur.execute('SELECT date dt,open,high,low,close,volume FROM stock_data_daily WHERE stock_code=%s ORDER BY date DESC LIMIT 250',(code,))
        rows = cur.fetchall()
        if len(rows) < 100:
            continue
        rows.reverse()
        kl = [{'dt':str(r['dt']),'open':float(r['open']),'high':float(r['high']),'low':float(r['low']),'close':float(r['close']),'volume':float(r['volume'])} for r in rows]
        c = build_czsc(code, kl)
        bis = c.bi_list; closes = [k['close'] for k in kl]
        zs_full = valid_pivots(bis)
        buys = detect_all_buys(bis, zs_full, closes)
        sells = detect_all_sells(bis, zs_full, closes)

        if not buys and not sells:
            continue

        # 只保留当日信号: 笔端点日期 = 今日或昨日(覆盖盘后确认)
        from datetime import datetime as _dtm, timedelta
        today_str = _dtm.now().strftime('%Y-%m-%d')
        yesterday_str = (_dtm.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        valid_dates = {today_str, yesterday_str}
        buys = [s for s in buys if str(s.get('dt',''))[:10] in valid_dates]
        sells = [s for s in sells if str(s.get('dt',''))[:10] in valid_dates]

        if not buys and not sells:
            continue

        name = get_stock_name(conn, code)
        ml = multi_level_ok(code, kl)
        div = last_divergence(bis, zs_full, closes)
        lt = last_trend(zs_full)
        last_close = kl[-1]['close']
        # P2: 线段级别中枢
        segs = bis_to_segments(bis)
        seg_zs = segment_pivots(segs)

        for sig in buys + sells:
            # 止损比(%)
            sl_pct = abs(sig['stop_loss'] - sig['price']) / sig['price'] * 100 if sig.get('stop_loss') and sig.get('price') else 0
            # 距中枢位置
            zg_val = sig.get('zg') or (zs_full[-1].zg if zs_full else None)
            zd_val = sig.get('zd') or (zs_full[-1].zd if zs_full else None)
            # 线段级别中枢(如有)
            seg_zg = seg_zs[-1]['zg'] if seg_zs else None
            seg_zd = seg_zs[-1]['zd'] if seg_zs else None

            sig.update({
                'code': code,
                'name': name,
                'last_close': round(last_close, 2),
                'stop_loss_pct': round(sl_pct, 1),
                'market_bullish': market['bullish'],
                'weekly_allow': ml['allow'],
                'weekly_trend': ml['weekly_trend'],
                'bi_count': len(bis),
                'zs_count': len(zs_full),
                'trend_type': lt['type'].value,
                'divergence': div['is_divergence'],
                'div_ratio': div.get('ratio', 0),
                'zg': round(zg_val, 2) if zg_val else None,
                'zd': round(zd_val, 2) if zd_val else None,
                'seg_zg': round(seg_zg, 2) if seg_zg else None,
                'seg_zd': round(seg_zd, 2) if seg_zd else None,
                'seg_count': len(segs),
            })
            signals.append(sig)



    # === P0-1: 信号去重 — 同一股票只保留最高优先级信号 ===
    # 优先级: buy1 > buy2 > buy3, sell1 > sell2 > sell3
    _priority = {"buy1":1, "sell1":2, "buy2":3, "sell2":4, "buy3":5, "sell3":6}
    _dedup = {}
    for sig in signals:
        key = sig["code"]
        p = _priority.get(sig["type"], 9)
        if key not in _dedup or p < _priority.get(_dedup[key]["type"], 9):
            _dedup[key] = sig
    signals = list(_dedup.values())

    # === P1-2: 信号评分 ===
    env_score = market.get("env_score", 12)
    for sig in signals:
        sc = score_signal(sig, env_score)
        sig["score"] = sc["score"]
        sig["grade"] = sc["grade"]
        sig["grade_label"] = sc["grade_label"]
        sig["score_detail"] = sc["detail"]

    # === 当日信号状态(全部可操作) + 归档到DB ===
    from datetime import datetime as _dt
    today = _dt.now()
    today_str = today.strftime('%Y-%m-%d')
    for sig in signals:
        sig_price = sig.get('price', 0)
        last_close = sig.get('last_close', 0)
        pnl_pct = round((last_close - sig_price) / sig_price * 100, 1) if sig_price > 0 else 0
        sig['days'] = 0
        sig['pnl_pct'] = pnl_pct
        is_buy = sig['type'].startswith('buy')
        if is_buy:
            sig['status'] = 'new'
            sig['status_label'] = '明日开盘买入'
            sig['action'] = '明日9:30确认价格在信号价±3%%内后买入,仓位20%%'
        else:
            sig['status'] = 'new'
            sig['status_label'] = '明日开盘卖出'
            sig['action'] = '如持有该股,明日开盘卖出;如未持有则忽略'

    # 归档到MySQL(每日信号存入历史表供复盘)
    try:
        archive_conn = pymysql.connect(**DB)
        archive_cur = archive_conn.cursor()
        for sig in signals:
            archive_cur.execute('''INSERT IGNORE INTO czsc_signal_history
                (signal_date, code, name, type, price, stop_loss, score, grade,
                 reason, trend_type, weekly_trend, divergence, div_ratio,
                 market_attitude, market_env_score, seg_zg, seg_zd)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (today_str, sig['code'], sig.get('name',''), sig['type'],
                 sig.get('price'), sig.get('stop_loss'), sig.get('score'),
                 sig.get('grade'), sig.get('reason'), sig.get('trend_type'),
                 sig.get('weekly_trend'), 1 if sig.get('divergence') else 0,
                 sig.get('div_ratio'), market.get('attitude'),
                 market.get('env_score'), sig.get('seg_zg'), sig.get('seg_zd')))
        archive_conn.commit()
        archive_conn.close()
    except Exception as e:
        print('archive error: %s' % e)

    conn.close()

    # === 持仓跟踪 ===
    prices_map = {}
    holdings = load_holdings()
    # 获取持仓股的最新价格(从DB查询)
    try:
        h_conn = pymysql.connect(**DB)
        h_cur = h_conn.cursor(pymysql.cursors.DictCursor)
        for h in holdings:
            h_cur.execute('SELECT close FROM stock_data_daily WHERE stock_code=%s ORDER BY date DESC LIMIT 1', (h['code'],))
            r = h_cur.fetchone()
            if r:
                prices_map = {h['code']: float(r['close'])}
        h_conn.close()
    except:
        prices_map = {}
    prices_map.update({s["code"]: s["last_close"] for s in signals})
    active_h, exited_h = update_holdings_daily(prices_map)
    # 高评分新买点(⭐⭐以上)加入待入仓建议(不自动入仓,由用户确认)
    buy_candidates = [s for s in signals if s["type"].startswith("buy") and s.get("grade", 0) >= 2]
    # 全自动入仓: ⭐⭐以上买点自动加入持仓跟踪(模型验证阶段)
    existing_codes = {h["code"] for h in active_h}
    for sig in buy_candidates[:3 - len(active_h)]:
        if sig["code"] not in existing_codes:
            active_h.append(add_holding(sig))
            existing_codes.add(sig["code"])
    save_holdings(active_h)
    save_holdings(active_h)

    # 按信号质量排序: 周线允许优先, 止损比小优先
    signals.sort(key=lambda s: (not s['weekly_allow'], s['stop_loss_pct']))

    result = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'engine': 'czsc', 'version': '3.0',
        'pool_size': len(pool),
        'market': market,
        # 三区块结构
        'today_signals': signals,  # 今日可操作信号
        'signal_count': len(signals),
        'holdings': active_h,  # 活跃持仓
        'holdings_count': len(active_h),
        'exited_today': exited_h,  # 今日触发出场的持仓
        'buy_candidates': buy_candidates,  # 建议入仓(待用户确认)
        # 兼容旧字段
        'signals': signals,
              'exited_count': len(exited_h),
              'exited_details': exited_h[:5],
    }
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print('czsc_scan v2: %d signals from %d stocks' % (len(signals), len(pool)))
    return result

if __name__ == '__main__':
    scan()


# === 企微推送 ===
WECOM_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=%s"
WEBHOOK_KEY = "7c097c2e-d664-46e4-bbdc-39ff5bc1b537"

def format_push_message(result):
    """格式化企微 markdown 推送消息"""
    mkt = result.get('market', {})
    sigs = result.get('signals', [])
    if not sigs:
        return None

    lines = []
    lines.append('## \U0001f9ea \u7f20\u8bba\u667a\u80fd\u4fe1\u53f7(czsc)')
    lines.append('')

    # 大盘
    mkt_icon = '\U0001f7e2' if mkt.get('bullish') else '\U0001f534'
    lines.append('**\u5927\u76d8**: %s %s | \u4f4d\u7f6e=%s | \u6536\u76d8=%s' % (
        mkt_icon, mkt.get('summary', '-'), mkt.get('position', '-'), mkt.get('last_close', '-')))
    lines.append('')

    # 信号列表(最多显示8个)
    type_map = {'buy1':'\u4e00\u4e70','buy2':'\u4e8c\u4e70','buy3':'\u4e09\u4e70','sell1':'\u4e00\u5356','sell2':'\u4e8c\u5356','sell3':'\u4e09\u5356'}
    reason_map = {'pullback_not_break_low':'\u56de\u8c03\u4e0d\u7834\u524d\u4f4e','breakout_pullback_above_zg':'\u7a81\u7834\u56de\u8e29','trend_bottom_divergence':'\u8d8b\u52bf\u5e95\u80cc\u9a70','consolidation_bottom_divergence':'\u76d8\u6574\u5e95\u80cc\u9a70','trend_top_divergence':'\u8d8b\u52bf\u9876\u80cc\u9a70','consolidation_top_divergence':'\u76d8\u6574\u9876\u80cc\u9a70','rebound_not_break_high':'\u53cd\u5f39\u4e0d\u7834\u524d\u9ad8','breakdown_rebound_below_zd':'\u8dcc\u7834\u56de\u62bd\u4e0d\u8fc7ZD'}

    for i, sig in enumerate(sigs[:8]):
        is_buy = sig['type'].startswith('buy')
        color = 'info' if is_buy else 'warning'
        tp = type_map.get(sig['type'], sig['type'])
        reason = reason_map.get(sig.get('reason',''), sig.get('reason',''))
        sl_pct = sig.get('stop_loss_pct', 0)
        sl_warn = ' \u26a0\ufe0f' if sl_pct >= 10 else ''
        weekly = '\u2713' if sig.get('weekly_allow') else '\u2717'

        lines.append('**%d. %s %s** <font color="%s">%s</font>' % (
            i+1, sig.get('code',''), sig.get('name',''), color, tp))
        lines.append('> \u4fe1\u53f7\u4ef7=%.2f | \u73b0\u4ef7=%s | \u6b62\u635f=%.1f%%%s | \u5468\u7ebf%s' % (
            sig.get('price',0), sig.get('last_close','-'), sl_pct, sl_warn, weekly))
        lines.append('> \u903b\u8f91: %s' % reason)
        lines.append('')

    if len(sigs) > 8:
        lines.append('> ... \u8fd8\u6709 %d \u4e2a\u4fe1\u53f7\uff0c\u8bf7\u67e5\u770b\u5e73\u53f0' % (len(sigs) - 8))
        lines.append('')

    # 止损预警
    invalids = result.get('invalid_signals', [])
    if invalids:
        lines.append('')
        lines.append('### \u26a0\ufe0f \u6b62\u635f\u9884\u8b66(\u5efa\u8bae\u79bb\u573a)')
        for inv in invalids:
            lines.append('> <font color="warning">%s %s</font> \u4fe1\u53f7\u4ef7=%.2f \u73b0\u4ef7=%s \u6b62\u635f=%.2f **\u5df2\u8dcc\u7834**' % (
                inv.get('code',''), inv.get('name',''), inv.get('price',0), inv.get('last_close','-'), inv.get('stop_loss',0)))
        lines.append('')

    lines.append('---')
    lines.append('\u6807\u7684\u6c60 %s\u53ea | \u5f15\u64ce czsc v%s | [%s](%s)' % (
        result.get('pool_size','-'), result.get('version','2.0'),
        '\u67e5\u770b\u8be6\u60c5', 'http://47.99.57.152:8088/chanlun-czsc'))

    return '\n'.join(lines)


def push_wecom(content):
    """推送到企微群机器人"""
    import urllib.request
    url = WECOM_WEBHOOK_URL % WEBHOOK_KEY
    body = json.dumps({'msgtype': 'markdown', 'markdown': {'content': content}}).encode('utf-8')
    req = urllib.request.Request(url, data=body, method='POST',
                                headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        if result.get('errcode') == 0:
            print('czsc推送成功')
        else:
            print('czsc推送失败: %s' % result)
        return result
    except Exception as e:
        print('czsc推送异常: %s' % e)
        return {'errcode': -1, 'errmsg': str(e)}


def scan_and_push():
    """扫描+推送一体"""
    result = scan()
    msg = format_push_message(result)
    if msg:
        push_wecom(msg)
    else:
        print('czsc: 无信号，跳过推送')


if __name__ == '__main__':
    import sys
    if '--push' in sys.argv:
        scan_and_push()
    else:
        scan()
