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
from chanlun.hotspot.concept_match import check_resonance
from chanlun.engine.holdings_tracker import load_holdings, save_holdings, add_holding, check_exit, update_holdings_daily

DB = {'host':'127.0.0.1','port':3306,'user':'root','password':'password','database':'stock_analysis_system','charset':'utf8mb4'}
# 主缓存路径(default profile)。non-default profile 追加 _{profile} 后缀避免覆盖主缓存。
_CACHE_DIR = '/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/strategy'
CACHE_PATH = _CACHE_DIR + '/signals_cache_czsc.json'


def _cache_path(profile):
    """按 profile 返回缓存文件路径。non-default 写独立文件,不覆盖主缓存。"""
    if profile == 'default' or not profile:
        return CACHE_PATH
    return _CACHE_DIR + '/signals_cache_czsc_' + str(profile) + '.json'


def _code_to_board(code):
    """股票代码 -> 板块分类"""
    prefix = code[:3]
    if prefix in ('300', '301'):
        return 'gem'     # 创业板
    elif prefix == '688':
        return 'star'    # 科创板
    elif prefix in ('430', '830', '831', '832', '833', '834', '835', '836', '837', '838', '839', '870', '871', '872', '873'):
        return 'bse'     # 北交所
    else:
        return 'main'    # 主板


def get_stock_pool(conn):
    """标的池: 日均成交额>=2亿的全部A股, 按流动性分层。

    Tier分类(用于展示标记):
      A — 日均>=10亿 (超大盘龙头, 结构周期长)
      B — 日均5-10亿 (大盘主力)
      C — 日均3-5亿 (中盘活跃, 信号主产区)
      D — 日均2-3亿 (中小盘机会)
    """
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute(
        "SELECT stock_code, AVG(turnover) as avg_to "
        "FROM stock_data_daily WHERE date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) "
        "GROUP BY stock_code HAVING AVG(turnover) >= 200000000 "
        "ORDER BY AVG(turnover) DESC"
    )
    valid = ('000','001','002','003','300','301','600','601','603','605','688')
    result = []
    for r in cur.fetchall():
        code = r['stock_code']
        if code[:3] not in valid:
            continue
        avg = float(r['avg_to'])
        if avg >= 1000000000:
            tier = 'A'
        elif avg >= 500000000:
            tier = 'B'
        elif avg >= 300000000:
            tier = 'C'
        else:
            tier = 'D'
        result.append((code, tier))
    return result

def get_stock_name(conn, code):
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute('SELECT name FROM stock_basic WHERE code=%s LIMIT 1', (code,))
    r = cur.fetchone()
    return r['name'] if r else code

def get_stock_industry(conn, code):
    """get_sw_industry: 个股申万行业(三级,形如 计算机-IT服务Ⅱ-IT服务Ⅲ)。无则返回空串。"""
    try:
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute('SELECT industry FROM stock_basic WHERE code=%s LIMIT 1', (code,))
        r = cur.fetchone()
        ind = (r['industry'] or '').strip() if r else ''
        return ind
    except Exception:
        return ''

# 数据就绪阈值: 当日入库标的数须达到近期均值的该比例, 否则判定数据管线未完成
DATA_READY_RATIO = 0.95
# 近期参考天数
DATA_READY_REF_DAYS = 5


def _check_data_ready(conn):
    """检查当天行情数据是否已入库完毕。

    数据管线(datapipeline)在收盘后持续采集, 通常 15:30~15:50 完成。
    若 czsc_scan 在数据未就绪时执行, last_close 会是 T-1 的值,
    导致推送内容中"现价"与实际偏差巨大(如百润股份案例: 显示17.81实际19.59涨停)。

    返回 (ready: bool, today_count: int, avg_count: float, today_date: str)
    """
    cur = conn.cursor(pymysql.cursors.DictCursor)
    # 获取最新2个交易日
    cur.execute("SELECT DISTINCT date FROM stock_data_daily ORDER BY date DESC LIMIT %d"
                % (DATA_READY_REF_DAYS + 1))
    dates = [r['date'] for r in cur.fetchall()]
    if len(dates) < 2:
        return True, 0, 0, ''  # 数据太少, 不阻塞

    latest = dates[0]
    ref_dates = dates[1:DATA_READY_REF_DAYS + 1]

    # 排除非正常交易股票: 北交所(9/4/8开头)、ST停牌、CDR(689开头)
    _NORMAL_FILTER = (
        "stock_code NOT LIKE '9%%' AND stock_code NOT LIKE '4%%' "
        "AND stock_code NOT LIKE '8%%' AND stock_code NOT LIKE '689%%' "
        "AND stock_code COLLATE utf8mb4_unicode_ci NOT IN (SELECT code FROM stock_basic WHERE name LIKE '%%ST%%')"
    )
    # 最新日入库标的数(仅正常交易股票)
    cur.execute("SELECT COUNT(DISTINCT stock_code) n FROM stock_data_daily WHERE date=%s AND " + _NORMAL_FILTER, (latest,))
    today_count = cur.fetchone()['n']

    # 参考日均入库数(仅正常交易股票)
    if ref_dates:
        placeholders = ','.join(['%s'] * len(ref_dates))
        cur.execute(f"SELECT AVG(day_count) avg_n FROM "
                    f"(SELECT date, COUNT(DISTINCT stock_code) day_count "
                    f"FROM stock_data_daily WHERE date IN ({placeholders}) "
                    f"AND {_NORMAL_FILTER} "
                    f"GROUP BY date) t", ref_dates)
        avg_count = float(cur.fetchone()['avg_n'] or today_count)
    else:
        avg_count = today_count

    ready = avg_count == 0 or today_count >= avg_count * DATA_READY_RATIO
    return ready, today_count, avg_count, str(latest)


def scan(profile='default', profile_cfg=None):
    conn = pymysql.connect(**DB)

    # 数据就绪校验: 行情数据未入库完毕则跳过本次执行, 等待下一轮调度重试
    ready, today_n, avg_n, data_date = _check_data_ready(conn)
    if not ready:
        msg = (f'czsc_scan: 数据未就绪, 跳过本次执行 '
               f'(最新日{data_date}: {today_n}只, 近期均值{avg_n:.0f}只, '
               f'需达 {DATA_READY_RATIO*100:.0f}% 即 {avg_n*DATA_READY_RATIO:.0f}只)')
        print(msg)
        print('czsc_scan: reason=data_not_ready data_date=%s' % data_date)
        conn.close()
        return {'skipped': True, 'reason': 'data_not_ready',
                'today_count': today_n, 'avg_count': avg_n, 'data_date': data_date}

    # 获取最近2个交易日(用于非交易日判断和信号有效期)
    _tc = conn.cursor(pymysql.cursors.DictCursor)
    _tc.execute("SELECT DISTINCT date FROM stock_data_daily ORDER BY date DESC LIMIT 2")
    _recent_trade_dates = [str(r['date']) for r in _tc.fetchall()]
    _last_trade_date = _recent_trade_dates[0] if _recent_trade_dates else None
    _valid_signal_dates = set(_recent_trade_dates)  # 信号有效窗口: 最近2个交易日

    # 非交易日判断: 如果最新交易日距今超过2个自然日,跳过扫描
    from datetime import timedelta as _td
    _today = datetime.now().strftime('%Y-%m-%d')
    _days_since = (datetime.now().date() - datetime.strptime(_last_trade_date, '%Y-%m-%d').date()).days if _last_trade_date else 99
    if _days_since > 2:
        print(f'czsc_scan: 非交易日(最新数据={_last_trade_date}, 距今{_days_since}天)，跳过')
        print('czsc_scan: reason=non_trading_day data_date=%s' % _last_trade_date)
        conn.close()
        return {'skipped': True, 'reason': 'non_trading_day', 'last_trade_date': _last_trade_date}

    pool_with_tier = get_stock_pool(conn)
    pool = [code for code, _ in pool_with_tier]
    tier_map = {code: tier for code, tier in pool_with_tier}
    market = get_market_state()
    # 丰富大盘信息
    market['summary'] = market.get('label', '中性')
    market['position'] = '中枢上方' if market.get('above_zg') else ('中枢下方' if market.get('below_zd') else '中枢内')

    signals = []
    # B2-4e: 止损硬门槛(百分数)。与 czsc_buysell.HARD_MAX_STOP_PCT 保持一致。
    from chanlun.engine.czsc_buysell import HARD_MAX_STOP_PCT as _HMS
    _HARD_MAX_STOP_PCT_PCT = _HMS * 100
    _dropped_by_stop = []
    cur = conn.cursor(pymysql.cursors.DictCursor)
    for code in pool:
        cur.execute('SELECT date dt,open,high,low,close,volume FROM stock_data_daily WHERE stock_code=%s ORDER BY date',(code,))
        rows = cur.fetchall()
        if len(rows) < 100:
            continue
        kl = [{'dt':str(r['dt']),'open':float(r['open']),'high':float(r['high']),'low':float(r['low']),'close':float(r['close']),'volume':float(r['volume'])} for r in rows]
        c = build_czsc(code, kl)
        bis = c.bi_list; closes = [k['close'] for k in kl]
        zs_full = valid_pivots(bis)
        buys = detect_all_buys(bis, zs_full, closes)
        sells = detect_all_sells(bis, zs_full, closes)

        if not buys and not sells:
            continue

        # 信号有效期: 最近2个交易日内确认的信号(对当前决策有效)
        buys = [s for s in buys if str(s.get('dt',''))[:10] in _valid_signal_dates]
        sells = [s for s in sells if str(s.get('dt',''))[:10] in _valid_signal_dates]

        if not buys and not sells:
            continue

        name = get_stock_name(conn, code)
        industry = get_stock_industry(conn, code)
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

            # 信号新鲜度: fresh=最新交易日 / actionable=前一交易日
            _sig_dt = str(sig.get('dt',''))[:10]
            _freshness = 'fresh' if _sig_dt == _last_trade_date else 'actionable'
            sig.update({
                'code': code,
                'tier': tier_map.get(code, 'D'),
                'board': _code_to_board(code),
                'freshness': _freshness,
                'name': name,
                'industry': industry,
                'industry_l1': industry.split('-')[0] if industry else '',
                'last_close': round(last_close, 2),
                'stop_loss_pct': round(sl_pct, 1),
                'market_bullish': market['bullish'],
                # B3-8: 按信号方向取周线许可(买入看 allow_buy, 卖出看 allow_sell)
                'weekly_allow': (ml.get('allow_buy', ml['allow'])
                                 if sig['type'].startswith('buy')
                                 else ml.get('allow_sell', True)),
                'weekly_sufficient': ml.get('sufficient', True),
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
            # B2-4c: 建议买入价 = 信号自带的 exec_price(信号确认K线收盘价),
            # 与 dt 时间对齐; 缺失时才退回该股最新收盘价。
            _entry = sig.get('exec_price') or round(last_close, 2)
            sig['entry_price'] = round(float(_entry), 2)
            sig['entry_zone_low'] = round(float(_entry) * 0.97, 2)
            sig['entry_zone_high'] = round(float(_entry) * 1.03, 2)
            # 重算止损比: 基于建议买入价
            if sig.get("entry_price") and sig.get("stop_loss"):
                sig["stop_loss_pct"] = round(abs(sig["stop_loss"] - sig["entry_price"]) / sig["entry_price"] * 100, 1)
            # B2-4e: 硬门槛 — 止损距离超过 HARD_MAX_STOP_PCT 的信号直接丢弃,
            # 不再依赖前端筛选(旧数据曾出现 32%/52%/65%/69% 的不可用止损)。
            if sig.get('stop_loss_pct', 0) > _HARD_MAX_STOP_PCT_PCT:
                _dropped_by_stop.append((code, sig['type'], sig['stop_loss_pct']))
                continue
            signals.append(sig)



    # === P0-1: 信号去重 — 同一股票只保留最高优先级信号 ===
    # 优先级: buy1 > buy2 > buy3, sell1 > sell2 > sell3
    # B3-7: 买入与卖出分别去重。
    # 旧实现把 buy/sell 放在同一优先级池且 key 仅为 code,
    # 一只股票同时有 buy3 与 sell1 时会因 sell1 优先级更高而顶掉 buy3 ——
    # 但买入信号面向空仓者、卖出信号面向持仓者, 两者不应互斥。
    _priority = {"buy1": 1, "buy2": 2, "buy3": 3, "sell1": 1, "sell2": 2, "sell3": 3}
    _dedup = {}
    for sig in signals:
        _side = 'buy' if sig["type"].startswith('buy') else 'sell'
        key = (sig["code"], _side)          # 同股同方向只留最高优先级
        p = _priority.get(sig["type"], 9)
        if key not in _dedup or p < _priority.get(_dedup[key]["type"], 9):
            _dedup[key] = sig
    signals = list(_dedup.values())

    # === P1-2: 信号评分(含题材共振) ===
    env_score = market.get("env_score", 12)
    for sig in signals:
        # 检查题材共振(只有确认有效时才加分和标注)
        resonance = check_resonance(sig.get('name', ''), sig.get('code', ''))
        if resonance:
            sig['resonance_bonus'] = resonance['bonus_score']
            sig['resonance'] = resonance['reason']
        else:
            sig['resonance_bonus'] = 0
            sig['resonance'] = None
        sc = score_signal(sig, env_score)
        sig["score"] = sc["score"]
        # P2-1: 同时落库五维基础分, 便于追溯共振加分前的原始水平
        sig["base_score"] = sc.get("base_score", sc["score"])
        sig["grade"] = sc["grade"]
        sig["grade_label"] = sc["grade_label"]
        sig["score_detail"] = sc["detail"]

    # === 当日信号状态(全部可操作) + 归档到DB ===
    from datetime import datetime as _dt
    today = _dt.now()
    today_str = today.strftime('%Y-%m-%d')
    # === 信号状态判定: 基于信号确认日(entry_price)与当天收盘(last_close)的偏离 ===
    # 信号确认日 = sig['dt'] 对应K线的收盘价(entry_price)
    # last_close = 数据库中该股最新收盘价
    # 如果 last_close 已脱离 entry_zone, 信号过期不再建议操作
    for sig in signals:
        entry_price = sig.get('entry_price', 0)
        last_close = sig.get('last_close', 0)
        zone_low = sig.get('entry_zone_low', 0)
        zone_high = sig.get('entry_zone_high', 0)
        pnl_pct = round((last_close - entry_price) / entry_price * 100, 1) if entry_price > 0 else 0
        sig['pnl_pct'] = pnl_pct
        sig['days'] = 0
        is_buy = sig['type'].startswith('buy')
        # 信号确认日期(用于前端展示)
        sig_date = str(sig.get('dt', ''))[:10]
        sig_date_short = sig_date[5:].replace('-', '/')  # "07/27"
        sig['signal_date_label'] = sig_date_short

        if is_buy:
            if last_close > zone_high:
                # 现价已高于可买区间上限 -> 追高风险大
                sig['status'] = 'expired_high'
                sig['status_label'] = '已涨离(%.1f%%)' % pnl_pct
                sig['action'] = '现价%.2f已超可买区间上限%.2f，不建议追高' % (last_close, zone_high)
            elif last_close < zone_low:
                # 现价已低于可买区间下限 -> 信号可能失效
                sig['status'] = 'expired_low'
                sig['status_label'] = '已跌破(%.1f%%)' % abs(pnl_pct)
                sig['action'] = '现价%.2f已低于可买区间下限%.2f，信号可能失效，关注止损%.2f' % (last_close, zone_low, sig.get('stop_loss', 0))
            else:
                # 现价仍在可买区间内 -> 次日可操作
                sig['status'] = 'actionable'
                sig['status_label'] = '可操作'
                sig['action'] = '下一交易日开盘确认价格在%.2f~%.2f区间内买入，仓位20%%' % (zone_low, zone_high)
        else:
            if last_close < entry_price * 0.97:
                sig['status'] = 'expired_down'
                sig['status_label'] = '已下跌(%.1f%%)' % abs(pnl_pct)
                sig['action'] = '卖出信号已兑现，跌%.1f%%' % abs(pnl_pct)
            else:
                sig['status'] = 'actionable'
                sig['status_label'] = '建议卖出'
                sig['action'] = '如持有该股，下一交易日开盘卖出；如未持有则忽略'

    # 归档到MySQL(每日信号存入历史表供复盘)
    try:
        archive_conn = pymysql.connect(**DB)
        archive_cur = archive_conn.cursor()
        for sig in signals:
            # P0-2: signal_date 使用信号实际发生日(sig['dt'])，而非扫描运行日
            # 保证复盘按周切分不错位；扫描日单独记录在 scan_date
            _sig_date = str(sig.get('dt', ''))[:10] or today_str
            archive_cur.execute('''INSERT INTO czsc_signal_history
                (signal_date, code, name, type, price, stop_loss, score, grade,
                 reason, trend_type, weekly_trend, divergence, div_ratio,
                 market_attitude, market_env_score, seg_zg, seg_zd, profile, entry_price,
                 base_score, target_price, target_type, scan_date)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    name=VALUES(name), price=VALUES(price), stop_loss=VALUES(stop_loss),
                    score=VALUES(score), grade=VALUES(grade), reason=VALUES(reason),
                    trend_type=VALUES(trend_type), weekly_trend=VALUES(weekly_trend),
                    divergence=VALUES(divergence), div_ratio=VALUES(div_ratio),
                    market_attitude=VALUES(market_attitude),
                    market_env_score=VALUES(market_env_score),
                    seg_zg=VALUES(seg_zg), seg_zd=VALUES(seg_zd),
                    entry_price=VALUES(entry_price), base_score=VALUES(base_score),
                    target_price=VALUES(target_price), target_type=VALUES(target_type),
                    scan_date=VALUES(scan_date)''',
                (_sig_date, sig['code'], sig.get('name',''), sig['type'],
                 sig.get('price'), sig.get('stop_loss'), sig.get('score'),
                 sig.get('grade'), sig.get('reason'), sig.get('trend_type'),
                 sig.get('weekly_trend'), 1 if sig.get('divergence') else 0,
                 sig.get('div_ratio'), market.get('attitude'),
                 market.get('env_score'), sig.get('seg_zg'), sig.get('seg_zd'), profile,
                 sig.get('entry_price'), sig.get('base_score'),
                 sig.get('target_price'), sig.get('target_type'), today_str))
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
    # B1-3: 修复负数切片 — len(active_h)>3 时 [:3-N] 变成 [:-k] 会加入几乎全部候选,
    # 击穿持仓上限。改为 max(0, ...) 保证超限时不再建仓。
    _slots = max(0, 3 - len(active_h))
    for sig in buy_candidates[:_slots]:
        if sig["code"] not in existing_codes:
            active_h.append(add_holding(sig))
            existing_codes.add(sig["code"])
    save_holdings(active_h)
    save_holdings(active_h)

    # 按信号质量排序: 周线允许优先, 止损比小优先
    signals.sort(key=lambda s: (not s['weekly_allow'], s['stop_loss_pct']))

    result = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'engine': 'czsc', 'version': '3.0', 'profile': profile,
        'pool_size': len(pool),
        'pool_tiers': {'A': sum(1 for _,t in pool_with_tier if t=='A'), 'B': sum(1 for _,t in pool_with_tier if t=='B'), 'C': sum(1 for _,t in pool_with_tier if t=='C'), 'D': sum(1 for _,t in pool_with_tier if t=='D')},
        'signal_window': sorted(_valid_signal_dates),
        'dropped_by_stop_loss': len(_dropped_by_stop),
        'hard_max_stop_pct': _HARD_MAX_STOP_PCT_PCT,
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
    _out = _cache_path(profile)
    os.makedirs(os.path.dirname(_out), exist_ok=True)
    with open(_out, 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    if _dropped_by_stop:
        print('czsc_scan: 因止损>%.0f%% 丢弃 %d 个信号(样例: %s)' % (
            _HARD_MAX_STOP_PCT_PCT, len(_dropped_by_stop), _dropped_by_stop[:5]))
    print('czsc_scan v2: %d signals from %d stocks' % (len(signals), len(pool)))
    print('czsc_scan: reason=ok data_date=%s signal_count=%d' % (_last_trade_date, len(signals)))
    return result

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--push', action='store_true', help='推送企微')
    parser.add_argument('--profile', default='default', help='规则profile: default/experimental')
    args = parser.parse_args()

    # 加载profile配置
    import os, json as _json
    profile_path = os.path.join(os.path.dirname(__file__), 'profiles', f'{args.profile}.json')
    _profile_cfg = None
    if os.path.exists(profile_path):
        with open(profile_path) as _pf:
            _profile_cfg = _json.load(_pf)

    result = scan(profile=args.profile, profile_cfg=_profile_cfg)


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

        tier_icon = {'A':'\U0001f534','B':'\U0001f7e0','C':'\U0001f7e1','D':'\U0001f7e2'}.get(sig.get('tier',''),'\u26aa')
        fresh_tag = '' if sig.get('freshness')=='fresh' else ' [\u6628]'
        lines.append('**%d. %s %s %s%s** <font color="%s">%s</font>' % (
            i+1, tier_icon, sig.get('code',''), sig.get('name',''), fresh_tag, color, tp))
        entry = sig.get('entry_price', sig.get('price', 0))
        zone_l = sig.get('entry_zone_low', 0)
        zone_h = sig.get('entry_zone_high', 0)
        lines.append('> \u5efa\u8bae\u4e70\u5165=%.2f (\u533a\u95f4%.2f~%.2f) | \u4fe1\u53f7\u4ef7=%.2f | \u6b62\u635f=%.1f%%%s | \u5468\u7ebf%s' % (
            entry, zone_l, zone_h, sig.get('price',0), sl_pct, sl_warn, weekly))
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


import json as _json
from datetime import datetime as _dt

_STATUS_FILE = '/var/log/d8q/czsc_scan_status.json'

def _write_status(result):
    """写入扫描状态供前端读取"""
    status = {
        'last_run': _dt.now().strftime('%Y-%m-%d %H:%M:%S'),
        'skipped': result.get('skipped', False),
        'reason': result.get('reason'),
        'signal_count': len(result.get('signals', [])),
        'today_count': result.get('today_count'),
        'avg_count': result.get('avg_count'),
        'data_date': result.get('data_date'),
    }
    try:
        with open(_STATUS_FILE, 'w') as f:
            _json.dump(status, f, ensure_ascii=False)
    except Exception:
        pass

def scan_and_push():
    """扫描+推送一体"""
    result = scan()
    _write_status(result)
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
