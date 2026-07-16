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
