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

DB = {'host':'127.0.0.1','port':3306,'user':'root','password':'password','database':'stock_analysis_system','charset':'utf8mb4'}
CACHE_PATH = '/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/strategy/signals_cache_czsc.json'

def get_stock_pool(conn, limit=80):
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute("""SELECT stock_code FROM stock_data_daily WHERE date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                   GROUP BY stock_code HAVING AVG(volume*close) >= 50000000
                   ORDER BY AVG(volume*close) DESC LIMIT %s""", (limit,))
    valid = ('000','001','002','003','300','600','601','603','605')
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
    market['summary'] = '看多' if market['bullish'] else '看空'
    market['position'] = '中枢上方' if market.get('above_zg') else '中枢内/下方'

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
        bis = c.bi_list; zs = valid_pivots(bis); closes = [k['close'] for k in kl]
        buys = detect_all_buys(bis, zs, closes)
        sells = detect_all_sells(bis, zs, closes)

        if not buys and not sells:
            continue

        name = get_stock_name(conn, code)
        ml = multi_level_ok(code, kl)
        div = last_divergence(bis, zs, closes)
        lt = last_trend(zs)
        last_close = kl[-1]['close']

        for sig in buys + sells:
            # 止损比(%)
            sl_pct = abs(sig['stop_loss'] - sig['price']) / sig['price'] * 100 if sig.get('stop_loss') and sig.get('price') else 0
            # 距中枢位置
            zg_val = sig.get('zg') or (zs[-1].zg if zs else None)
            zd_val = sig.get('zd') or (zs[-1].zd if zs else None)

            sig.update({
                'code': code,
                'name': name,
                'last_close': round(last_close, 2),
                'stop_loss_pct': round(sl_pct, 1),
                'market_bullish': market['bullish'],
                'weekly_allow': ml['allow'],
                'weekly_trend': ml['weekly_trend'],
                'bi_count': len(bis),
                'zs_count': len(zs),
                'trend_type': lt['type'].value,
                'divergence': div['is_divergence'],
                'div_ratio': div.get('ratio', 0),
                'zg': round(zg_val, 2) if zg_val else None,
                'zd': round(zd_val, 2) if zd_val else None,
            })
            signals.append(sig)

    conn.close()

    # 按信号质量排序: 周线允许优先, 止损比小优先
    signals.sort(key=lambda s: (not s['weekly_allow'], s['stop_loss_pct']))

    result = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'engine': 'czsc', 'version': '2.0',
        'signal_count': len(signals),
        'pool_size': len(pool),
        'market': market,
        'signals': signals,
    }
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print('czsc_scan v2: %d signals from %d stocks' % (len(signals), len(pool)))
    return result

if __name__ == '__main__':
    scan()
