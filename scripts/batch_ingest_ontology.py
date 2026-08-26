"""批量灌入: 从 chanlun_signals + stock_data_daily 读取，构建 CZSC 结构，推送到 ontology"""
import sys, json, pymysql, requests
from datetime import datetime

sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')
from chanlun.engine.czsc_adapter import build_czsc, valid_pivots
from chanlun.engine.czsc_buysell import detect_all_buys, detect_all_sells

ONTOLOGY_URL = 'http://127.0.0.1:8080'
DB = {'host':'127.0.0.1','port':3306,'user':'root','password':'password',
      'database':'stock_analysis_system','charset':'utf8mb4',
      'cursorclass': pymysql.cursors.DictCursor}

def get_signal_stocks(conn):
    """获取有信号的股票列表"""
    cur = conn.cursor()
    cur.execute('SELECT DISTINCT stock_code FROM chanlun_signals ORDER BY stock_code')
    return [r['stock_code'] for r in cur.fetchall()]

def get_klines(conn, code):
    cur = conn.cursor()
    cur.execute('SELECT date dt,open,high,low,close,volume FROM stock_data_daily WHERE stock_code=%s ORDER BY date', (code,))
    rows = cur.fetchall()
    if len(rows) < 100:
        return None
    return [{'dt':str(r['dt']),'open':float(r['open']),'high':float(r['high']),
             'low':float(r['low']),'close':float(r['close']),'volume':float(r['volume'])} for r in rows]

def build_ingest_payload(code, klines):
    """构建 ingest payload"""
    c = build_czsc(code, klines)
    bis = c.bi_list
    zs_list = valid_pivots(bis)

    strokes = []
    for i, bi in enumerate(bis):
        strokes.append({
            'id': i+1,
            'direction': 'up' if 'up' in str(bi.direction).lower() else 'down',
            'high': float(bi.high), 'low': float(bi.low),
            'start_time': str(bi.sdt)[:19], 'end_time': str(bi.edt)[:19],
            'start_fractal_id': (i+1)*10+1, 'end_fractal_id': (i+1)*10+2,
        })

    centers = []
    for i, zs in enumerate(zs_list):
        centers.append({
            'id': i+1, 'zg': float(zs.zg), 'zd': float(zs.zd),
            'gg': float(zs.gg), 'dd': float(zs.dd), 'segment_ids': [],
        })

    closes = [k['close'] for k in klines]
    buys = detect_all_buys(bis, zs_list, closes)

    buy_points = []
    for i, b in enumerate(buys):
        buy_points.append({
            'id': i+1, 'type': int(b['type'][-1]),
            'time': str(b['dt'])[:19], 'price': float(b['price']),
            'confirmed_by_type': 'center', 'confirmed_by_id': 1,
        })

    return {
        'symbol': code, 'level': 'D',
        'strokes': strokes, 'centers': centers, 'buy_points': buy_points,
    }

def main():
    conn = pymysql.connect(**DB)
    stocks = get_signal_stocks(conn)
    print(f'有信号股票: {len(stocks)} 只')

    ok, fail = 0, 0
    for i, code in enumerate(stocks):
        klines = get_klines(conn, code)
        if not klines:
            print(f'  [{i+1}/{len(stocks)}] {code}: 数据不足，跳过')
            fail += 1
            continue
        try:
            payload = build_ingest_payload(code, klines)
            resp = requests.post(f'{ONTOLOGY_URL}/ingest', json=payload, timeout=10)
            result = resp.json()
            n = result.get('ingested', 0)
            print(f'  [{i+1}/{len(stocks)}] {code}: {n} triples (strokes={len(payload["strokes"])}, centers={len(payload["centers"])})')
            ok += 1
        except Exception as e:
            print(f'  [{i+1}/{len(stocks)}] {code}: 失败 {e}')
            fail += 1

    conn.close()
    print(f'\n完成: 成功 {ok}, 失败 {fail}')

if __name__ == '__main__':
    main()
