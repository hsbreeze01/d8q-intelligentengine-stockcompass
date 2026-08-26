# -*- coding: utf-8 -*-
"""czsc单股详情: 返回K线+笔+中枢+信号数据供前端图表渲染"""
import pymysql
from .czsc_adapter import build_czsc, valid_pivots
from .czsc_buysell import detect_all_buys, detect_all_sells
from .czsc_divergence import last_divergence
from .trend import last_trend

DB = {'host':'127.0.0.1','port':3306,'user':'root','password':'password','database':'stock_analysis_system','charset':'utf8mb4'}

def get_stock_detail(code, limit=0):
    """返回单股的完整czsc分析结果(供前端K线图渲染)"""
    conn = pymysql.connect(**DB, cursorclass=pymysql.cursors.DictCursor)
    try:
        cur = conn.cursor()
        # limit=0 表示取全部历史(主扫描也用全量); 前端 dataZoom 控制可见范围
        if limit > 0:
            cur.execute('SELECT date dt,open,high,low,close,volume FROM stock_data_daily WHERE stock_code=%s ORDER BY date DESC LIMIT %s', (code, limit))
        else:
            cur.execute('SELECT date dt,open,high,low,close,volume FROM stock_data_daily WHERE stock_code=%s ORDER BY date', (code,))
        rows = cur.fetchall()
        if not rows:
            return {'error': 'no data'}
        if limit > 0:
            rows.reverse()  # DESC 查询需翻转; 全量已是 ASC
        # 股票名
        cur.execute('SELECT name FROM stock_basic WHERE code=%s LIMIT 1', (code,))
        nr = cur.fetchone()
        name = nr['name'] if nr else code
    finally:
        conn.close()

    kl = [{'dt':str(r['dt']),'open':float(r['open']),'high':float(r['high']),'low':float(r['low']),'close':float(r['close']),'volume':float(r['volume'])} for r in rows]
    c = build_czsc(code, kl)
    bis = c.bi_list
    zs = valid_pivots(bis)
    closes = [k['close'] for k in kl]
    buys = detect_all_buys(bis, zs, closes)
    sells = detect_all_sells(bis, zs, closes)
    div = last_divergence(bis, zs, closes)
    lt = last_trend(zs)

    # 格式化笔数据(供前端画线)
    bi_data = []
    for b in bis:
        bi_data.append({
            'sdt': str(b.sdt)[:10], 'edt': str(b.edt)[:10],
            'high': round(b.high, 2), 'low': round(b.low, 2),
            'dir': 'up' if 'up' in str(b.direction).lower() or '上' in str(b.direction) else 'down'
        })

    # 格式化中枢数据(供前端画矩形)
    zs_data = []
    for z in zs:
        zs_data.append({
            'sdt': str(z.sdt)[:10], 'edt': str(z.edt)[:10],
            'zg': round(z.zg, 2), 'zd': round(z.zd, 2),
            'gg': round(z.gg, 2), 'dd': round(z.dd, 2)
        })

    return {
        'code': code, 'name': name,
        'klines': kl,
        'bis': bi_data,
        'zs': zs_data,
        'buys': buys, 'sells': sells,
        'divergence': div,
        'trend': lt['type'].value,
        'bi_count': len(bis), 'zs_count': len(zs)
    }
