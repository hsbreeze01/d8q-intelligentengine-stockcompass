# -*- coding: utf-8 -*-
"""缠论历史回填: 绕过数据就绪检查，对指定日期范围执行扫描"""
import sys, os, json, pymysql
from datetime import datetime, timedelta
sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')

DB = {'host':'127.0.0.1','port':3306,'user':'root','password':'password','database':'stock_analysis_system','charset':'utf8mb4'}

def get_trade_dates(conn, start, end):
    cur = conn.cursor()
    cur.execute('SELECT DISTINCT date FROM stock_data_daily WHERE date BETWEEN %s AND %s ORDER BY date', (start, end))
    return [str(r[0]) for r in cur.fetchall()]

def backfill_dates(dates):
    from chanlun.strategy.czsc_scan import get_stock_pool, get_stock_name, _code_to_board
    from chanlun.engine.czsc_adapter import build_czsc, valid_pivots
    from chanlun.engine.czsc_buysell import detect_all_buys, detect_all_sells
    
    conn = pymysql.connect(**DB)
    pool_with_tier = get_stock_pool(conn)
    pool = [code for code, _ in pool_with_tier]
    tier_map = {code: tier for code, tier in pool_with_tier}
    
    # 检查哪些日期已有数据
    cur = conn.cursor()
    existing = set()
    cur.execute('SELECT DISTINCT signal_date FROM chanlun_signals')
    for r in cur.fetchall():
        existing.add(str(r[0]))
    
    todo = [d for d in dates if d not in existing]
    if not todo:
        print(f'所有日期已有信号数据: {existing}')
        return
    
    print(f'待回填: {todo}')
    print(f'标的池: {len(pool)} 只')
    
    for target_date in todo:
        print(f'\n=== {target_date} ===')
        signals = []
        
        for i, code in enumerate(pool):
            if (i+1) % 200 == 0:
                print(f'  进度: {i+1}/{len(pool)}')
            try:
                cur2 = conn.cursor(pymysql.cursors.DictCursor)
                cur2.execute('''
                    SELECT date, open, high, low, close, volume
                    FROM stock_data_daily
                    WHERE stock_code = %s
                    ORDER BY date ASC
                ''', (code,))
                klines = cur2.fetchall()
                if len(klines) < 60:
                    continue
                
                c = build_czsc(code, klines)
                bis = c.bi_list
                zs_list = valid_pivots(bis)
                if not zs_list:
                    continue
                
                closes = [k['close'] for k in klines]
                buys = detect_all_buys(bis, zs_list, closes)
                sells = detect_all_sells(bis, zs_list, closes)
                
                for b in buys:
                    bdate = str(b.get('dt',''))[:10]
                    if bdate == target_date:
                        signals.append((code, get_stock_name(conn, code), target_date,
                                       b['type'], b.get('price', 0), b.get('stop_loss', 0),
                                       b.get('target', 0), json.dumps(b.get('reason', []), ensure_ascii=False),
                                       tier_map.get(code, 'D')))
                for s in sells:
                    sdate = str(s.get('dt',''))[:10]
                    if sdate == target_date:
                        signals.append((code, get_stock_name(conn, code), target_date,
                                       s['type'], s.get('price', 0), 0, 0,
                                       json.dumps(s.get('reason', []), ensure_ascii=False),
                                       tier_map.get(code, 'D')))
            except Exception:
                continue
        
        if signals:
            cur3 = conn.cursor()
            for sig in signals:
                cur3.execute('''
                    INSERT INTO chanlun_signals
                    (stock_code, stock_name, signal_date, timeframe, signal_type,
                     signal_price, stop_loss, target_price, status, reason_chain, tier)
                    VALUES (%s, %s, %s, 'D', %s, %s, %s, %s, 'pending', %s, %s)
                ''', sig)
            conn.commit()
            print(f'  写入 {len(signals)} 条信号')
        else:
            print(f'  无信号')
    
    conn.close()
    print('\n回填完成')

if __name__ == '__main__':
    if len(sys.argv) >= 3:
        dates = sys.argv[1:]
    else:
        # 默认回填 23~29
        dates = ['2026-07-23','2026-07-24','2026-07-25','2026-07-26','2026-07-27','2026-07-28','2026-07-29']
    backfill_dates(dates)
