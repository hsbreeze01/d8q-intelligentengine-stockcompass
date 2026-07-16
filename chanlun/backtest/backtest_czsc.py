# -*- coding: utf-8 -*-
"""N9: 对照回测 - czsc新引擎 vs 旧引擎(同标的/区间/成本)
滑动窗口: 从第120根K线开始每5根做一次信号检测, 触发后模拟持仓到出场。
"""
import sys, json, pymysql
sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')
from chanlun.engine.czsc_adapter import build_czsc, valid_pivots
from chanlun.engine.czsc_buysell import detect_all_buys, detect_all_sells
from chanlun.engine.market_state import get_market_state

DB = {'host':'127.0.0.1','port':3306,'user':'root','password':'password','database':'stock_analysis_system','charset':'utf8mb4'}

def load_klines(conn, code, limit=500):
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute('SELECT date dt,open,high,low,close,volume FROM stock_data_daily WHERE stock_code=%s ORDER BY date DESC LIMIT %s',(code,limit))
    rows=cur.fetchall(); rows.reverse()
    return [{'dt':str(r['dt']),'open':float(r['open']),'high':float(r['high']),'low':float(r['low']),'close':float(r['close']),'volume':float(r['volume'])} for r in rows]

def simulate(klines, entry_idx, entry_price, stop_loss, max_days=15):
    for i in range(entry_idx+1, min(entry_idx+max_days+1, len(klines))):
        low = klines[i]['low']; close = klines[i]['close']
        if low <= stop_loss:
            return {'pnl_pct': (stop_loss - entry_price) / entry_price * 100, 'exit': 'stop_loss', 'days': i - entry_idx}
        if close >= entry_price * 1.08:
            return {'pnl_pct': 8.0, 'exit': 'target', 'days': i - entry_idx}
    final = klines[min(entry_idx+max_days, len(klines)-1)]['close']
    return {'pnl_pct': (final - entry_price) / entry_price * 100, 'exit': 'timeout', 'days': max_days}

def run_backtest(codes, limit=500):
    conn = pymysql.connect(**DB)
    results = {'buy1':[],'buy2':[],'buy3':[],'sell1':[],'sell2':[],'sell3':[]}
    for code in codes:
        kl = load_klines(conn, code, limit)
        if len(kl) < 150:
            continue
        for end in range(120, len(kl)-15, 5):
            window = kl[:end]
            c = build_czsc(code, window)
            bis = c.bi_list; zs = valid_pivots(bis); closes = [k['close'] for k in window]
            for sig in detect_all_buys(bis, zs, closes):
                r = simulate(kl, end-1, sig['price'], sig['stop_loss'])
                r['code'] = code; r['type'] = sig['type']; r['dt'] = sig.get('dt','')
                results[sig['type']].append(r)
            for sig in detect_all_sells(bis, zs, closes):
                r = simulate(kl, end-1, sig['price'], sig['stop_loss'])
                r['code'] = code; r['type'] = sig['type']; r['dt'] = sig.get('dt','')
                results[sig['type']].append(r)
    conn.close()
    return results

def print_stats(results):
    print('%-6s %5s %6s %8s %8s %8s' % ('type','N','win%','avg_pnl','max_loss','avg_days'))
    for t in ['buy1','buy2','buy3','sell1','sell2','sell3']:
        rs = results[t]
        if not rs: print('%-6s %5d    -       -        -        -' % (t,0)); continue
        wins = [r for r in rs if r['pnl_pct'] > 0]
        wr = len(wins)/len(rs)*100
        avg = sum(r['pnl_pct'] for r in rs)/len(rs)
        mx = min(r['pnl_pct'] for r in rs)
        ad = sum(r['days'] for r in rs)/len(rs)
        print('%-6s %5d %5.1f%% %7.2f%% %7.2f%% %7.1f' % (t,len(rs),wr,avg,mx,ad))

if __name__ == '__main__':
    conn = pymysql.connect(**DB)
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute("""SELECT stock_code FROM stock_data_daily WHERE date >= DATE_SUB(CURDATE(), INTERVAL 60 DAY) GROUP BY stock_code HAVING COUNT(*)>=40 AND AVG(volume*close)>=100000000 ORDER BY AVG(volume*close) DESC LIMIT 30""")
    codes = [r['stock_code'] for r in cur.fetchall()]
    conn.close()
    print('回测标的: %d只' % len(codes))
    results = run_backtest(codes, 500)
    print_stats(results)
    total = sum(len(v) for v in results.values())
    print('总信号: %d' % total)
    with open('/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/backtest/czsc_bt_result.json','w') as f:
        json.dump({k:[{kk:vv for kk,vv in r.items()} for r in v] for k,v in results.items()}, f, ensure_ascii=False, default=str)
    print('BACKTEST_DONE')
