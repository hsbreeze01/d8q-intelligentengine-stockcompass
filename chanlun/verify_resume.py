#!/usr/bin/env python3
"""恢复自检工具: 验证czsc新引擎所有模块完整性+可运行性。
用法: venv/bin/python chanlun/verify_resume.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check(desc, condition):
    status = 'PASS' if condition else 'FAIL'
    print(f'  [{status}] {desc}')
    return condition

def main():
    print('=== czsc新引擎恢复自检 ===\n')
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    all_ok = True

    # 1. 文件存在性
    print('[1] 文件存在性:')
    files = [
        'chanlun/czsc_core/__init__.py', 'chanlun/engine/czsc_adapter.py',
        'chanlun/engine/trend.py', 'chanlun/engine/czsc_divergence.py',
        'chanlun/engine/czsc_buysell.py', 'chanlun/engine/market_state.py',
        'chanlun/engine/multi_level.py', 'chanlun/backtest/backtest_czsc.py',
        'chanlun/strategy/czsc_scan.py',
    ]
    for f in files:
        ok = check(f, os.path.exists(os.path.join(base, f)))
        all_ok &= ok

    # 2. 导入验证
    print('\n[2] 模块导入:')
    try:
        from chanlun.czsc_core import CZSC, RawBar, Freq, ZS, BI, Direction
        from chanlun.engine.czsc_adapter import build_czsc, valid_pivots, get_zs_seq
        from chanlun.engine.trend import classify_trends, last_trend, TrendType
        from chanlun.engine.czsc_divergence import last_divergence
        from chanlun.engine.czsc_buysell import detect_all_buys, detect_all_sells
        from chanlun.engine.market_state import get_market_state
        from chanlun.engine.multi_level import multi_level_ok, resample_weekly
        all_ok &= check('所有模块导入成功', True)
    except Exception as e:
        all_ok &= check(f'导入失败: {e}', False)

    # 3. 端到端运行(宁德)
    print('\n[3] 端到端运行(300750):')
    try:
        import pymysql
        conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='password',
                              database='stock_analysis_system', charset='utf8mb4',
                              cursorclass=pymysql.cursors.DictCursor)
        cur = conn.cursor()
        cur.execute('SELECT date dt,open,high,low,close,volume FROM stock_data_daily WHERE stock_code=%s ORDER BY date DESC LIMIT 250', ('300750',))
        rows = cur.fetchall(); rows.reverse()
        kl = [{'dt': str(r['dt']), 'open': float(r['open']), 'high': float(r['high']),
               'low': float(r['low']), 'close': float(r['close']), 'volume': float(r['volume'])} for r in rows]
        conn.close()
        c = build_czsc('300750', kl)
        bis = c.bi_list; zs = valid_pivots(bis); closes = [k['close'] for k in kl]
        all_ok &= check(f'czsc笔={len(bis)}', len(bis) > 3)
        all_ok &= check(f'中枢={len(zs)}', len(zs) >= 1)
        buys = detect_all_buys(bis, zs, closes)
        sells = detect_all_sells(bis, zs, closes)
        all_ok &= check(f'买卖点检测可运行 (buys={len(buys)}, sells={len(sells)})', True)
        div = last_divergence(bis, zs, closes)
        all_ok &= check(f'背驰判定可运行 (is_div={div.get("is_divergence")})', 'is_divergence' in div)
        mkt = get_market_state()
        all_ok &= check(f'大盘状态可运行 (bullish={mkt.get("bullish")})', 'bullish' in mkt)
        ml = multi_level_ok('300750', kl)
        all_ok &= check(f'多级别可运行 (allow={ml.get("allow")})', 'allow' in ml)
    except Exception as e:
        all_ok &= check(f'端到端异常: {e}', False)

    # 4. API 端点
    print('\n[4] API端点:')
    try:
        import urllib.request, json
        resp = urllib.request.urlopen('http://127.0.0.1:8088/api/chanlun/czsc', timeout=10)
        d = json.loads(resp.read())
        all_ok &= check(f'API返回 engine={d.get("engine")} count={d.get("signal_count")}', d.get('engine') == 'czsc')
    except Exception as e:
        all_ok &= check(f'API异常: {e}', False)


    # Summary
    print('')
    print('=' * 40)
    result_text = 'ALL PASS' if all_ok else 'SOME FAILED'
    print('结果: ' + result_text)
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())
