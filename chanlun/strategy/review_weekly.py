#!/usr/bin/env python3
"""每周复盘脚本 - 信号回测与统计

功能:
1. 从 czsc_signal_history 表查询过去一周产生的所有信号(查询层去重)
2. 对每个信号，查询信号日之后最多 20 个交易日的行情数据(stock_data_daily)
3. 在 5/10/20 三档窗口上分别评估(策略持仓周期 5~20 日, 单一 5 日窗口会低估胜率):
   - 买入信号: 可操作性(能否在 entry_zone 买到) + MFE/MAE + 止损触发 + 窗口末胜率
   - 卖出信号: 避险有效性(信号后是否下跌) + MFE/MAE + 误报率(信号后反而上涨)
4. 计算 R 倍数期望(pnl / 初始风险), 直接回答"每笔期望盈亏多少个止损单位"
5. 关联 sentiment_daily 市场情绪, 按环境相位分层归因(区分策略 alpha 与环境 beta)
6. 按信号类型和评分分组统计
7. 输出到 review_stats.json 供前端展示

指标口径:
   MFE (Maximum Favorable Excursion) 最大有利偏移: 窗口内对信号方向最有利的浮动幅度(>=0)
   MAE (Maximum Adverse Excursion)   最大不利偏移: 窗口内对信号方向最不利的浮动幅度(<=0)
       买入: MFE=(最高价-基准)/基准, MAE=(最低价-基准)/基准
       卖出: MFE=(基准-最低价)/基准, MAE=(基准-最高价)/基准  (方向已按"卖出获益=下跌"归一)
   r_raw       = 窗口末涨跌幅 / 初始风险幅度   (不施加止损, 持有到窗口末)
   r_realized  = 触发止损记 -1R, 否则同 r_raw  (施加止损纪律的实际结果)
   expectancy_r = r_realized 的均值 —— 每笔交易期望赚/亏多少个止损单位

用法:
    python review_weekly.py             # 默认回顾上一周
    python review_weekly.py --week 30   # 回顾第30周
    python review_weekly.py --week 2026-W30  # ISO周格式
    python review_weekly.py --push      # 计算完成后推送企微
"""
import sys
import os
import json
import argparse
import logging
from datetime import datetime, timedelta, date

sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')

import pymysql

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('review_weekly')

DB = {
    'host': '127.0.0.1', 'port': 3306, 'user': 'root',
    'password': 'password', 'database': 'stock_analysis_system', 'charset': 'utf8mb4'
}

OUTPUT_PATH = '/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/strategy/review_stats.json'

# 止损默认比例 (当信号无 stop_loss 字段时使用)
DEFAULT_STOP_LOSS_PCT = -0.08
# entry_zone 范围: entry_price +/- 3%
ENTRY_ZONE_PCT = 0.03

# === 多窗口复盘口径 (2026-09-01) ===
# 原实现只有单一 5 日窗口, 而策略设计持仓周期为 5~20 个交易日 ——
# 用 5 日窗口评估 5~20 日策略会系统性低估胜率(赢的单子还没走完就被判为没赢)。
# 改为 5/10/20 三档并行评估: 每个窗口独立判定"是否满窗"与各项指标,
# 一个有 12 根后续K线的信号会同时计入 5 日与 10 日统计, 但对 20 日窗口仍是 pending。
REVIEW_WINDOWS = (5, 10, 20)
MAX_REVIEW_WINDOW = max(REVIEW_WINDOWS)
# 复盘观察窗口: 需要信号日之后至少这么多个交易日的数据才纳入统计
# 不足时该信号仍在观察期(pending), 计入统计会使"5日"类指标失真
# 保留为"最短窗口"语义, 兼容既有前端字段与 pending 判定
REVIEW_WINDOW_BARS = 5
MIN_REVIEW_BARS = 5
# 卖出信号"避险有效"判定: 5日后收盘价低于信号价(即卖出确实规避了下跌)
# 用收盘价而非最低价, 因为几乎所有股票5日内都会有瞬时下探, 用最低价会导致有效率虚高为100%
# 卖出信号"误报"阈值: 信号后5日内最高价涨超此百分比 => 卖早了, 错失收益
SELL_FALSE_ALARM_PCT = 3.0


def get_db_connection():
    return pymysql.connect(**DB, cursorclass=pymysql.cursors.DictCursor)


def parse_week_arg(week_arg):
    """解析 --week 参数，返回 (monday, friday, sunday, iso_week_str)"""
    today = date.today()

    if week_arg is None:
        # 默认上一周
        last_week = today - timedelta(days=today.weekday() + 7)
        monday = last_week
    elif 'W' in str(week_arg).upper():
        # ISO格式: 2026-W30
        parts = str(week_arg).upper().replace('-W', '-').split('-')
        year, week_num = int(parts[0]), int(parts[1])
        jan4 = date(year, 1, 4)
        start_of_week1 = jan4 - timedelta(days=jan4.weekday())
        monday = start_of_week1 + timedelta(weeks=week_num - 1)
    else:
        # 纯数字周号，当前年份
        week_num = int(week_arg)
        year = today.year
        jan4 = date(year, 1, 4)
        start_of_week1 = jan4 - timedelta(days=jan4.weekday())
        monday = start_of_week1 + timedelta(weeks=week_num - 1)

    friday = monday + timedelta(days=4)
    sunday = monday + timedelta(days=6)
    iso_year, iso_week, _ = monday.isocalendar()
    week_str = f"{iso_year}-W{iso_week:02d}"
    return monday, friday, sunday, week_str


def fetch_trading_days(conn, start_date, end_date):
    """获取区间内的有效交易日集合

    用于过滤脏数据: P0-2 修复前归档以扫描运行日为 signal_date,
    会产生周六/无行情日期的记录, 这些必须排除否则周复盘重复计数。
    """
    sql = """
        SELECT DISTINCT date FROM stock_data_daily
        WHERE date BETWEEN %s AND %s
        ORDER BY date
    """
    with conn.cursor() as cur:
        cur.execute(sql, (start_date, end_date))
        return [r['date'] for r in cur.fetchall()]


def fetch_signals(conn, start_date, end_date, profile='default'):
    """查询指定周期内的所有信号

    P1-1 防御性去重: 即使 uk_signal 唯一索引失效或历史脏数据残留,
    也保证每个 (signal_date, code, type) 只统计一次。
    优先保留 entry_price 非空的记录(新格式), 其次保留 id 最大的。

    profile 隔离(2026-09-02): 只统计指定 profile 的信号, 默认 'default'(生产路径)。
    czsc_signal_history 曾同时收录 default 与 experimental(灰度)信号, 混算会污染口径。
    NULL profile 视为历史生产数据, 计入 default。
    """
    trading_days = fetch_trading_days(conn, start_date, end_date)
    if not trading_days:
        log.warning(f"区间 {start_date} ~ {end_date} 内无交易日，返回空结果")
        return []

    placeholders = ','.join(['%s'] * len(trading_days))
    # profile 过滤: default 兼容历史 NULL 行; 其它 profile 精确匹配
    if profile == 'default':
        prof_clause = "(profile = %s OR profile IS NULL)"
        h_prof_clause = "(h.profile = %s OR h.profile IS NULL)"
    else:
        prof_clause = "profile = %s"
        h_prof_clause = "h.profile = %s"
    sql = f"""
        SELECT h.id, h.signal_date, h.code, h.name, h.type, h.price, h.stop_loss,
               h.score, h.grade, h.reason, h.next_open, h.entry_price
        FROM czsc_signal_history h
        INNER JOIN (
            SELECT signal_date, code, type,
                   COALESCE(
                     MAX(CASE WHEN entry_price IS NOT NULL THEN id END),
                     MAX(id)
                   ) AS keep_id
            FROM czsc_signal_history
            WHERE signal_date IN ({placeholders}) AND {prof_clause}
            GROUP BY signal_date, code, type
        ) k ON h.id = k.keep_id
        WHERE {h_prof_clause}
        ORDER BY h.signal_date, h.code
    """
    params = list(trading_days) + [profile, profile]
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_post_signal_bars(conn, code, signal_date, num_days=MAX_REVIEW_WINDOW):
    """查询信号日之后N个交易日的行情数据(默认取最长窗口, 供多档窗口切片复用)"""
    sql = """
        SELECT DISTINCT date, open, close, high, low, volume
        FROM stock_data_daily
        WHERE stock_code = %s AND date > %s
        ORDER BY date ASC
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (code, signal_date, num_days))
        return cur.fetchall()


def to_float(val, default=None):
    """安全转换 Decimal/None 为 float"""
    if val is None:
        return default
    return float(val)


def resolve_entry_price(signal):
    """确定评估基准价

    P1-2: 优先用 entry_price(信号日收盘价, 用户次日实际可执行价),
    历史数据缺失时回退 next_open(次日开盘价), 最后才回退 price(笔极值, 不可执行)。
    返回 (entry_price, source)
    """
    ep = to_float(signal.get('entry_price'))
    if ep is not None and ep > 0:
        return ep, 'entry_price'
    no = to_float(signal.get('next_open'))
    if no is not None and no > 0:
        return no, 'next_open'
    p = to_float(signal.get('price'))
    if p is not None and p > 0:
        return p, 'price_fallback'
    return None, None


def _risk_pct(entry_price, stop_loss_price):
    """初始风险幅度(%): (基准价 - 止损价)/基准价. 无止损时回退默认止损比例.

    用于把绝对涨跌幅换算成 R 倍数(止损单位), 使不同止损宽度的信号可横向比较。
    """
    if stop_loss_price and stop_loss_price > 0 and entry_price > 0:
        r = abs(entry_price - stop_loss_price) / entry_price * 100
        if r > 0:
            return round(r, 4)
    return round(abs(DEFAULT_STOP_LOSS_PCT) * 100, 4)


def _r_multiples(pnl_pct, risk_pct, hit_stop_loss):
    """把窗口末涨跌幅换算为 R 倍数.

    r_raw      : 不施加止损, 持有到窗口末的结果
    r_realized : 施加止损纪律 —— 窗口内触发止损即记 -1R(实际会被扫出场),
                 否则等于 r_raw。这是真实执行下的期望值口径。
    """
    if pnl_pct is None or not risk_pct:
        return None, None
    r_raw = round(pnl_pct / risk_pct, 4)
    r_realized = -1.0 if hit_stop_loss else r_raw
    return r_raw, r_realized


def _buy_window_metrics(bars, entry_price, stop_loss_price, risk_pct):
    """在给定窗口的K线切片上计算买入信号指标(MFE/MAE/止损/可操作性/R倍数)"""
    zone_low = entry_price * (1 - ENTRY_ZONE_PCT)
    zone_high = entry_price * (1 + ENTRY_ZONE_PCT)

    had_chance = False
    best_entry = None
    max_high = None
    min_low = None
    hit_stop_loss = False
    last_close = None

    for bar in bars:
        bar_low = to_float(bar['low'])
        bar_high = to_float(bar['high'])
        bar_open = to_float(bar['open'])
        bar_close = to_float(bar['close'])
        if bar_low is None or bar_high is None:
            continue

        # 可买机会: 当日价格区间与 entry_zone 有交集(不只看最低价)
        if bar_low <= zone_high and bar_high >= zone_low:
            had_chance = True
        if bar_open is not None and (best_entry is None or bar_open < best_entry):
            best_entry = bar_open
        if max_high is None or bar_high > max_high:
            max_high = bar_high
        if min_low is None or bar_low < min_low:
            min_low = bar_low
        if stop_loss_price and bar_low <= stop_loss_price:
            hit_stop_loss = True
        last_close = bar_close

    # 无 stop_loss 字段时用默认比例兜底判定止损
    if not hit_stop_loss and stop_loss_price is None:
        for bar in bars:
            bar_low = to_float(bar['low'])
            if bar_low and (bar_low - entry_price) / entry_price <= DEFAULT_STOP_LOSS_PCT:
                hit_stop_loss = True
                break

    # MFE/MAE: 买入方向 —— 上涨有利, 下跌不利
    mfe_pct = round((max_high - entry_price) / entry_price * 100, 2) if max_high else 0.0
    mae_pct = round((min_low - entry_price) / entry_price * 100, 2) if min_low else 0.0
    pnl_pct = round((last_close - entry_price) / entry_price * 100, 2) if last_close else None
    r_raw, r_realized = _r_multiples(pnl_pct, risk_pct, hit_stop_loss)

    return {
        'bars_used': len(bars),
        'had_chance': had_chance,
        'best_entry': best_entry,
        'mfe_pct': mfe_pct,
        'mae_pct': mae_pct,
        # max_profit_pct 与 MFE 同义, 保留旧字段名供前端兼容
        'max_profit_pct': mfe_pct,
        'pnl_pct': pnl_pct,
        'hit_stop_loss': hit_stop_loss,
        'win': (pnl_pct is not None and pnl_pct > 0),
        'r_raw': r_raw,
        'r_realized': r_realized,
    }


def analyze_buy_signal(signal, bars, entry_price, entry_source):
    """分析买入信号: 在 5/10/20 三档窗口上分别评估

    顶层字段(max_profit_pct/day5_pnl_pct/hit_stop_loss/had_chance)保持 5 日窗口语义,
    确保既有前端与推送不受影响; 多窗口结果放在 'windows' 下。
    """
    stop_loss_price = to_float(signal.get('stop_loss'))
    risk_pct = _risk_pct(entry_price, stop_loss_price)

    windows = {}
    for w in REVIEW_WINDOWS:
        sliced = bars[:w]
        m = _buy_window_metrics(sliced, entry_price, stop_loss_price, risk_pct)
        m['window_complete'] = len(bars) >= w
        windows[str(w)] = m

    base_w = windows[str(REVIEW_WINDOW_BARS)]
    return {
        'side': 'buy',
        'entry_price': entry_price,
        'entry_source': entry_source,
        'stop_loss': stop_loss_price,
        'risk_pct': risk_pct,
        # --- 旧字段(5日窗口语义), 保持前端兼容 ---
        'had_chance': base_w['had_chance'],
        'best_entry': base_w['best_entry'],
        'max_profit_pct': base_w['max_profit_pct'],
        'day5_pnl_pct': base_w['pnl_pct'],
        'hit_stop_loss': base_w['hit_stop_loss'],
        # --- 新增: 多窗口明细 ---
        'windows': windows,
    }


def _sell_window_metrics(bars, entry_price, risk_pct):
    """在给定窗口的K线切片上计算卖出信号指标(方向已归一: 下跌=有利)"""
    min_low = None
    max_high = None
    last_close = None

    for bar in bars:
        bar_low = to_float(bar['low'])
        bar_high = to_float(bar['high'])
        bar_close = to_float(bar['close'])
        if bar_low is None or bar_high is None:
            continue
        if min_low is None or bar_low < min_low:
            min_low = bar_low
        if max_high is None or bar_high > max_high:
            max_high = bar_high
        last_close = bar_close

    # 最大跌幅(负数): 窗口内最低点相对信号价
    max_drop_pct = round((min_low - entry_price) / entry_price * 100, 2) if min_low else 0
    # 规避的跌幅(正数, 便于阅读): 卖出后股价最深跌了多少
    avoided_loss_pct = round(-max_drop_pct, 2) if max_drop_pct < 0 else 0
    # 错失的涨幅: 仅当窗口内价格确实涨超信号价时才为正
    raw_gain = (max_high - entry_price) / entry_price * 100 if max_high else 0
    missed_gain_pct = round(max(0.0, raw_gain), 2)
    pnl_pct = round((last_close - entry_price) / entry_price * 100, 2) if last_close else None

    # MFE/MAE: 卖出方向 —— 下跌有利, 上涨不利(符号已归一为 MFE>=0 / MAE<=0)
    mfe_pct = avoided_loss_pct
    mae_pct = round(-missed_gain_pct, 2)
    # 避险有效: 窗口末收盘价低于信号价 => 卖出决策正确
    effective = pnl_pct is not None and pnl_pct < 0
    # 误报: 窗口内最高价涨超阈值 => 卖早了
    false_alarm = missed_gain_pct >= SELL_FALSE_ALARM_PCT
    # 卖出信号的 R 倍数: 下跌为正收益, 故取 -pnl
    r_raw, r_realized = _r_multiples(
        None if pnl_pct is None else -pnl_pct, risk_pct, False)

    return {
        'bars_used': len(bars),
        'max_drop_pct': max_drop_pct,
        'avoided_loss_pct': avoided_loss_pct,
        'missed_gain_pct': missed_gain_pct,
        'mfe_pct': mfe_pct,
        'mae_pct': mae_pct,
        'pnl_pct': pnl_pct,
        'effective': effective,
        'false_alarm': false_alarm,
        'win': effective,
        'r_raw': r_raw,
        'r_realized': r_realized,
    }


def analyze_sell_signal(signal, bars, entry_price, entry_source):
    """分析卖出信号: 避险有效性, 在 5/10/20 三档窗口上分别评估

    卖出信号的正确性与买入相反:
    - 信号后价格下跌 => 避险成功(避免了亏损)
    - 信号后价格上涨 => 误报(卖早了, 错失收益)
    顶层字段保持 5 日窗口语义以兼容既有前端。
    """
    stop_loss_price = to_float(signal.get('stop_loss'))
    risk_pct = _risk_pct(entry_price, stop_loss_price)

    windows = {}
    for w in REVIEW_WINDOWS:
        m = _sell_window_metrics(bars[:w], entry_price, risk_pct)
        m['window_complete'] = len(bars) >= w
        windows[str(w)] = m

    base_w = windows[str(REVIEW_WINDOW_BARS)]
    return {
        'side': 'sell',
        'entry_price': entry_price,
        'entry_source': entry_source,
        'risk_pct': risk_pct,
        # --- 旧字段(5日窗口语义) ---
        'max_drop_pct': base_w['max_drop_pct'],
        'avoided_loss_pct': base_w['avoided_loss_pct'],
        'missed_gain_pct': base_w['missed_gain_pct'],
        'day5_pnl_pct': base_w['pnl_pct'],
        'effective': base_w['effective'],
        'false_alarm': base_w['false_alarm'],
        # --- 新增: 多窗口明细 ---
        'windows': windows,
    }


def analyze_signal(signal, bars):
    """分析单个信号, 按买/卖分派到对应评估逻辑"""
    entry_price, entry_source = resolve_entry_price(signal)
    if entry_price is None:
        return None

    sig_type = (signal.get('type') or '').lower()
    is_buy = sig_type.startswith('buy')

    if is_buy:
        metrics = analyze_buy_signal(signal, bars, entry_price, entry_source)
    else:
        metrics = analyze_sell_signal(signal, bars, entry_price, entry_source)

    base = {
        'code': signal['code'],
        'name': signal.get('name', ''),
        'type': signal.get('type', ''),
        'signal_date': str(signal['signal_date']),
        'score': signal.get('score'),
        'grade': signal.get('grade'),
        # 实际可用于评估的交易日数; < MIN_REVIEW_BARS 表示观察窗口未满
        'bars_available': len(bars),
        'window_complete': len(bars) >= MIN_REVIEW_BARS,
    }
    base.update(metrics)
    return base


def compute_buy_stats(details):
    """买入信号统计"""
    if not details:
        return {'count': 0, 'actionable_rate': 0, 'avg_max_profit': 0,
                'stop_loss_hit_rate': 0, 'win_rate_5d': 0, 'avg_day5_pnl': 0}
    count = len(details)
    actionable = sum(1 for d in details if d.get('had_chance'))
    profits = [d.get('max_profit_pct', 0) for d in details]
    stop_hits = sum(1 for d in details if d.get('hit_stop_loss'))
    d5 = [d['day5_pnl_pct'] for d in details if d.get('day5_pnl_pct') is not None]
    wins_5d = sum(1 for v in d5 if v > 0)
    return {
        'count': count,
        'actionable_rate': round(actionable / count, 2),
        'avg_max_profit': round(sum(profits) / len(profits), 2) if profits else 0,
        'stop_loss_hit_rate': round(stop_hits / count, 2),
        'win_rate_5d': round(wins_5d / len(d5), 2) if d5 else 0,
        'avg_day5_pnl': round(sum(d5) / len(d5), 2) if d5 else 0,
    }


def compute_sell_stats(details):
    """卖出信号统计(避险有效性)"""
    if not details:
        return {'count': 0, 'effective_rate': 0, 'avg_avoided_loss': 0,
                'false_alarm_rate': 0, 'avg_missed_gain': 0, 'avg_day5_pnl': 0}
    count = len(details)
    effective = sum(1 for d in details if d.get('effective'))
    false_alarms = sum(1 for d in details if d.get('false_alarm'))
    avoided = [d.get('avoided_loss_pct', 0) for d in details]
    missed = [d.get('missed_gain_pct', 0) for d in details]
    d5 = [d['day5_pnl_pct'] for d in details if d.get('day5_pnl_pct') is not None]
    return {
        'count': count,
        'effective_rate': round(effective / count, 2),
        'avg_avoided_loss': round(sum(avoided) / len(avoided), 2) if avoided else 0,
        'false_alarm_rate': round(false_alarms / count, 2),
        'avg_missed_gain': round(sum(missed) / len(missed), 2) if missed else 0,
        'avg_day5_pnl': round(sum(d5) / len(d5), 2) if d5 else 0,
    }


def _avg(vals, nd=2):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), nd) if vals else 0


def compute_window_stats(details, window, side):
    """在指定窗口上统计一组信号(只统计该窗口已满窗的信号)

    返回含 MFE/MAE 与 R 倍数期望的统计块。expectancy_r 是核心决策指标:
    每笔交易期望赚/亏多少个止损单位, >0 才是正期望策略。
    盈亏平衡胜率 = 1/(1+盈亏比), 故 win_rate 需与 payoff_ratio 一起看。
    """
    key = str(window)
    rows = [d['windows'][key] for d in details
            if d.get('windows', {}).get(key, {}).get('window_complete')]
    base = {
        'window': window, 'count': len(rows),
        'win_rate': 0, 'avg_pnl': 0, 'avg_mfe': 0, 'avg_mae': 0,
        'expectancy_r': 0, 'expectancy_r_raw': 0, 'payoff_ratio': 0,
        'breakeven_win_rate': 0,
    }
    if not rows:
        if side == 'buy':
            base['stop_loss_hit_rate'] = 0
            base['actionable_rate'] = 0
        else:
            base['effective_rate'] = 0
            base['false_alarm_rate'] = 0
        return base

    n = len(rows)
    wins = [r for r in rows if r.get('win')]
    losses = [r for r in rows if not r.get('win')]
    base['win_rate'] = round(len(wins) / n, 2)
    base['avg_pnl'] = _avg([r.get('pnl_pct') for r in rows])
    base['avg_mfe'] = _avg([r.get('mfe_pct') for r in rows])
    base['avg_mae'] = _avg([r.get('mae_pct') for r in rows])
    base['expectancy_r'] = _avg([r.get('r_realized') for r in rows], 3)
    base['expectancy_r_raw'] = _avg([r.get('r_raw') for r in rows], 3)

    # 盈亏比: 平均盈利幅度 / 平均亏损幅度(取绝对值)
    win_pnl = [abs(r['pnl_pct']) for r in wins if r.get('pnl_pct') is not None]
    loss_pnl = [abs(r['pnl_pct']) for r in losses if r.get('pnl_pct') is not None]
    avg_win = sum(win_pnl) / len(win_pnl) if win_pnl else 0
    avg_loss = sum(loss_pnl) / len(loss_pnl) if loss_pnl else 0
    if avg_loss > 0:
        base['payoff_ratio'] = round(avg_win / avg_loss, 2)
        base['breakeven_win_rate'] = round(1 / (1 + avg_win / avg_loss), 2) if avg_win > 0 else 1.0

    if side == 'buy':
        base['stop_loss_hit_rate'] = round(
            sum(1 for r in rows if r.get('hit_stop_loss')) / n, 2)
        base['actionable_rate'] = round(
            sum(1 for r in rows if r.get('had_chance')) / n, 2)
    else:
        base['effective_rate'] = round(
            sum(1 for r in rows if r.get('effective')) / n, 2)
        base['false_alarm_rate'] = round(
            sum(1 for r in rows if r.get('false_alarm')) / n, 2)
    return base


def compute_all_window_stats(details, side):
    """对 REVIEW_WINDOWS 每档窗口各出一份统计"""
    return {str(w): compute_window_stats(details, w, side) for w in REVIEW_WINDOWS}


def compute_pending_by_window(all_details):
    """统计各窗口未满窗的信号数(同一信号可能对短窗满、对长窗未满)"""
    out = {}
    for w in REVIEW_WINDOWS:
        key = str(w)
        out[key] = {
            'buy_count': sum(1 for d in all_details if d['side'] == 'buy'
                             and not d.get('windows', {}).get(key, {}).get('window_complete')),
            'sell_count': sum(1 for d in all_details if d['side'] == 'sell'
                              and not d.get('windows', {}).get(key, {}).get('window_complete')),
        }
    return out


def fetch_sentiment_context(conn, start_date, end_date):
    """读取复盘区间的市场情绪(sentiment_daily), 用于按市场环境分层归因。

    为什么需要: 信号胜率高度依赖市场环境 —— 在情绪升温周里几乎所有买点都赚钱,
    此时的高胜率是 beta 而非策略 alpha。把情绪相位记进复盘结果,
    才能回答"环境该不该做闸门"以及"止损是否集中在环境走弱日"。

    sentiment_daily 由 datafactory 仓库 sentiment.py 生成; 表缺失时返回空 dict(不阻断复盘)。
    """
    sql = """
        SELECT date, composite, phase, composite_v2, phase_glae,
               limit_up, limit_down, up_ratio
        FROM sentiment_daily
        WHERE date BETWEEN %s AND %s
        ORDER BY date
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (start_date, end_date))
            rows = cur.fetchall()
    except pymysql.err.ProgrammingError:
        log.warning('sentiment_daily 表不存在, 跳过市场环境归因'
                    '(该表由 datafactory/sentiment.py 生成)')
        return {}
    except Exception as e:
        log.warning('读取 sentiment_daily 失败, 跳过市场环境归因: %s', e)
        return {}

    ctx = {}
    for r in rows:
        ctx[str(r['date'])] = {
            'composite': to_float(r.get('composite')),
            'phase': r.get('phase'),
            'composite_v2': to_float(r.get('composite_v2')),
            'phase_glae': r.get('phase_glae'),
            'limit_up': r.get('limit_up'),
            'limit_down': r.get('limit_down'),
            'up_ratio': to_float(r.get('up_ratio')),
        }
    return ctx


# 情绪相位的温度序(与 datafactory/sentiment.py 的 PHASES 一致)。
# 按码点排序对温度档位无意义(如 '亢奋' < '修复'), 故显式定义顺序。
PHASE_ORDER = ['冰点', '修复', '温和', '亢奋', '过热']


def _phase_sort_key(p):
    return (PHASE_ORDER.index(p) if p in PHASE_ORDER else len(PHASE_ORDER), p)


def summarize_market_context(ctx):
    """汇总区间市场环境: 均值/区间/相位跨度, 供复盘结论标注"""
    if not ctx:
        return {'available': False, 'by_date': {}}
    comps = [v['composite'] for v in ctx.values() if v.get('composite') is not None]
    phases = [v['phase'] for v in ctx.values() if v.get('phase')]
    return {
        'available': True,
        'by_date': ctx,
        'avg_composite': round(sum(comps) / len(comps), 2) if comps else None,
        'min_composite': round(min(comps), 2) if comps else None,
        'max_composite': round(max(comps), 2) if comps else None,
        # 按温度序排列(冰点 -> 过热), 便于直读环境跨度
        'phase_span': sorted(set(phases), key=_phase_sort_key) if phases else [],
        # 情绪升温周的胜率含较大 beta 成分, 标注出来避免误读为策略 alpha
        'rising': (comps[-1] > comps[0]) if len(comps) >= 2 else None,
    }


def compute_by_phase(details, window, side):
    """按信号日的市场情绪相位分层统计 —— 回答"环境该不该做闸门"的核心归因表"""
    out = {}
    phases = set(d.get('sentiment_phase') for d in details if d.get('sentiment_phase'))
    for ph in sorted(phases, key=_phase_sort_key):
        group = [d for d in details if d.get('sentiment_phase') == ph]
        out[ph] = compute_window_stats(group, window, side)
    return out


def group_by(details, key_fn, stats_fn, sort_reverse=False):
    """按 key_fn 分组并用 stats_fn 统计"""
    result = {}
    keys = set(key_fn(d) for d in details if key_fn(d) is not None)
    for k in sorted(keys, reverse=sort_reverse):
        group = [d for d in details if key_fn(d) == k]
        result[str(k)] = stats_fn(group)
    return result


def empty_result(week_str, period_str):
    return {
        'week': week_str,
        'period': period_str,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_signals': 0,
        'review_windows': list(REVIEW_WINDOWS),
        'pending': {'buy_count': 0, 'sell_count': 0, 'min_bars_required': MIN_REVIEW_BARS,
                    'buy_details': [], 'sell_details': []},
        'pending_by_window': compute_pending_by_window([]),
        'data_quality': {'entry_source_counts': {}, 'reliable_rate': 0, 'fallback_warning': False},
        'buy_summary': compute_buy_stats([]),
        'sell_summary': compute_sell_stats([]),
        'buy_by_window': compute_all_window_stats([], 'buy'),
        'sell_by_window': compute_all_window_stats([], 'sell'),
        'market_context': summarize_market_context({}),
        'buy_by_phase': {}, 'sell_by_phase': {},
        'buy_by_type': {}, 'sell_by_type': {},
        'buy_by_grade': {}, 'sell_by_grade': {},
        'buy_details': [], 'sell_details': [],
        # 兼容旧前端字段
        'summary': compute_buy_stats([]),
        'by_type': {}, 'by_grade': {}, 'details': [],
    }


# === 企微推送 ===
WECOM_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=%s"
# 凭据从环境变量读取, 不入源码。未设置时跳过推送(不阻断复盘计算)。
WEBHOOK_KEY = os.environ.get('D8Q_REVIEW_WECOM_KEY', '')


def _format_review_push(result):
    """格式化周复盘企微推送消息"""
    bs = result.get('buy_summary', {})
    ss = result.get('sell_summary', {})
    pd = result.get('pending', {})
    if not bs.get('count') and not ss.get('count') and not (pd.get('buy_count') or pd.get('sell_count')):
        return None

    lines = []
    lines.append('## 📊 周复盘 (%s)' % result.get('week', ''))
    lines.append('> 周期: %s' % result.get('period', ''))
    lines.append('')

    if bs.get('count'):
        lines.append('**买入信号 %d 个**' % bs['count'])
        lines.append('> 可操作率 %.0f%% | 平均最高收益 %.1f%% | 5日胜率 %.0f%% | 止损触发 %.0f%%' % (
            bs.get('actionable_rate',0)*100, bs.get('avg_max_profit',0),
            bs.get('win_rate_5d',0)*100, bs.get('stop_loss_hit_rate',0)*100))
        lines.append('')
    # 多窗口口径: 5/10/20 日胜率与 R 期望(策略持仓 5~20 日, 单看5日会低估)
    bw = result.get('buy_by_window', {})
    if bw:
        lines.append('**买入·多窗口口径**')
        for w in REVIEW_WINDOWS:
            s = bw.get(str(w))
            if not s or not s.get('count'):
                continue
            lines.append('> %d日(n=%d): 胜率 %.0f%% | 盈亏比 %.2f | 期望 %+.2fR | MFE %+.1f%% / MAE %+.1f%%' % (
                w, s['count'], s.get('win_rate', 0) * 100, s.get('payoff_ratio', 0),
                s.get('expectancy_r', 0), s.get('avg_mfe', 0), s.get('avg_mae', 0)))
        lines.append('')
    if ss.get('count'):
        lines.append('**卖出信号 %d 个** (避险有效性)' % ss['count'])
        lines.append('> 避险有效率 %.0f%% | 平均规避跌幅 %.1f%% | 误报率 %.0f%%' % (
            ss.get('effective_rate',0)*100, ss.get('avg_avoided_loss',0),
            ss.get('false_alarm_rate',0)*100))
        lines.append('')
    pc = (pd.get('buy_count',0) or 0) + (pd.get('sell_count',0) or 0)
    if pc:
        lines.append('> 观察中: %d 个信号窗口未满(买%d/卖%d)' % (
            pc, pd.get('buy_count',0), pd.get('sell_count',0)))
        lines.append('')
    # 买入明细
    for d in result.get('buy_details', [])[:5]:
        icon = '✅' if d.get('had_chance') else '❌'
        lines.append('> %s %s %s 建议买入%.2f 最高%+.1f%% 5日%+.1f%%' % (
            icon, d.get('code',''), d.get('name','')[:4],
            d.get('entry_price',0), d.get('max_profit_pct',0), d.get('day5_pnl_pct',0)))
    lines.append('')
    lines.append('---')
    lines.append('[查看详情](http://47.99.57.152:8088/chanlun-czsc)')
    return chr(10).join(lines)


def _push_wecom(content):
    import urllib.request
    import json as _json
    if not WEBHOOK_KEY:
        log.warning('未设置 D8Q_REVIEW_WECOM_KEY 环境变量, 跳过企微推送')
        return {'errcode': -2, 'errmsg': 'no webhook key'}
    url = WECOM_WEBHOOK_URL % WEBHOOK_KEY
    body = _json.dumps({'msgtype': 'markdown', 'markdown': {'content': content}}).encode('utf-8')
    req = urllib.request.Request(url, data=body, method='POST',
                                headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            r = _json.loads(resp.read())
        if r.get('errcode') == 0:
            log.info('复盘推送成功')
        else:
            log.error('复盘推送失败: %s', r)
        return r
    except Exception as e:
        log.error('复盘推送异常: %s', e)
        return {'errcode': -1}



def main():
    parser = argparse.ArgumentParser(description='每周信号复盘统计')
    parser.add_argument('--week', type=str, default=None,
                        help='指定回顾哪一周，支持: 30, 2026-W30 (默认上一周)')
    parser.add_argument('--push', action='store_true',
                        help='计算完成后推送企微(需设置 D8Q_REVIEW_WECOM_KEY 环境变量)')
    parser.add_argument('--profile', type=str, default='default',
                        help='只统计该 profile 的信号(默认 default 生产路径; NULL 视为 default)')
    args = parser.parse_args()

    monday, friday, sunday, week_str = parse_week_arg(args.week)
    period_str = f"{monday} ~ {friday}"
    log.info(f"复盘周期: {week_str} ({period_str})")

    conn = get_db_connection()
    try:
        trading_days = fetch_trading_days(conn, monday, sunday)
        log.info(f"区间内有效交易日 {len(trading_days)} 天: "
                 f"{[str(d) for d in trading_days]}")
        signals = fetch_signals(conn, monday, sunday, profile=args.profile)
        log.info(f"查询到 {len(signals)} 个信号(profile={args.profile}, 已去重, 已过滤非交易日脏数据)")
        # 市场环境上下文(用于分层归因: 高胜率是策略 alpha 还是环境 beta)
        sentiment_ctx = fetch_sentiment_context(conn, monday, sunday)
        if sentiment_ctx:
            log.info(f"已加载 {len(sentiment_ctx)} 天市场情绪数据用于环境归因")

        if not signals:
            log.warning("本周无信号，生成空报告")
            result = empty_result(week_str, period_str)
        else:
            buy_details, sell_details = [], []
            pending_buy, pending_sell = [], []
            skipped_no_bars = 0
            skipped_no_price = 0
            for sig in signals:
                bars = fetch_post_signal_bars(conn, sig['code'], sig['signal_date'],
                                              num_days=REVIEW_WINDOW_BARS)
                if not bars:
                    skipped_no_bars += 1
                    continue
                analysis = analyze_signal(sig, bars)
                if not analysis:
                    skipped_no_price += 1
                    continue
                # 标注该信号发出当日的市场情绪环境, 供按相位分层归因
                _sc = sentiment_ctx.get(analysis['signal_date'])
                if _sc:
                    analysis['sentiment_composite'] = _sc.get('composite')
                    analysis['sentiment_phase'] = _sc.get('phase')
                    analysis['sentiment_phase_glae'] = _sc.get('phase_glae')
                # 观察窗口未满的信号不计入统计, 避免"5日"指标失真
                if not analysis['window_complete']:
                    if analysis['side'] == 'buy':
                        pending_buy.append(analysis)
                    else:
                        pending_sell.append(analysis)
                    continue
                if analysis['side'] == 'buy':
                    buy_details.append(analysis)
                else:
                    sell_details.append(analysis)

            log.info(f"纳入统计: 买入 {len(buy_details)} 个, 卖出 {len(sell_details)} 个")
            log.info(f"观察中(窗口未满{MIN_REVIEW_BARS}个交易日): "
                     f"买入 {len(pending_buy)} 个, 卖出 {len(pending_sell)} 个")
            if skipped_no_bars or skipped_no_price:
                log.info(f"跳过: 无后续行情 {skipped_no_bars}, 无有效基准价 {skipped_no_price}")

            buy_summary = compute_buy_stats(buy_details)
            sell_summary = compute_sell_stats(sell_details)

            # 数据质量: entry_price 基准价来源分布
            # price_fallback 表示该信号归档时无 entry_price(历史数据), 评估基准退化为笔极值,
            # 此时 actionable_rate 会失真, 需提示用户
            all_details = buy_details + sell_details + pending_buy + pending_sell
            src_counts = {}
            for d in all_details:
                src = d.get('entry_source', 'unknown')
                src_counts[src] = src_counts.get(src, 0) + 1
            total_d = len(all_details)
            data_quality = {
                'entry_source_counts': src_counts,
                'reliable_rate': round(
                    src_counts.get('entry_price', 0) / total_d, 2) if total_d else 0,
                'fallback_warning': src_counts.get('price_fallback', 0) > 0,
            }

            result = {
                'week': week_str,
                'period': period_str,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_signals': len(buy_details) + len(sell_details),
                'profile': args.profile,
                'review_windows': list(REVIEW_WINDOWS),
                'pending': {
                    'buy_count': len(pending_buy),
                    'sell_count': len(pending_sell),
                    'min_bars_required': MIN_REVIEW_BARS,
                    'buy_details': pending_buy,
                    'sell_details': pending_sell,
                },
                'pending_by_window': compute_pending_by_window(all_details),
                'data_quality': data_quality,
                'buy_summary': buy_summary,
                'sell_summary': sell_summary,
                'buy_by_window': compute_all_window_stats(buy_details, 'buy'),
                'sell_by_window': compute_all_window_stats(sell_details, 'sell'),
                'market_context': summarize_market_context(sentiment_ctx),
                # 按市场情绪相位分层(以最短窗口口径), 用于判断环境是否应升级为闸门
                'buy_by_phase': compute_by_phase(buy_details, REVIEW_WINDOW_BARS, 'buy'),
                'sell_by_phase': compute_by_phase(sell_details, REVIEW_WINDOW_BARS, 'sell'),
                'buy_by_type': group_by(buy_details, lambda d: d['type'], compute_buy_stats),
                'sell_by_type': group_by(sell_details, lambda d: d['type'], compute_sell_stats),
                'buy_by_grade': group_by(buy_details, lambda d: d['grade'], compute_buy_stats, sort_reverse=True),
                'sell_by_grade': group_by(sell_details, lambda d: d['grade'], compute_sell_stats, sort_reverse=True),
                'buy_details': buy_details,
                'sell_details': sell_details,
                # 兼容旧前端字段: summary/by_type/by_grade/details 指向买入信号
                'summary': dict(buy_summary, total_signals=len(buy_details)),
                'by_type': group_by(buy_details, lambda d: d['type'], compute_buy_stats),
                'by_grade': group_by(buy_details, lambda d: d['grade'], compute_buy_stats, sort_reverse=True),
                'details': buy_details,
            }
    finally:
        conn.close()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log.info(f"复盘报告已保存: {OUTPUT_PATH}")
    bs = result['buy_summary']
    ss = result['sell_summary']
    log.info(f"买入信号 {bs['count']} 个: 可操作率={bs['actionable_rate']}, "
             f"平均最高收益={bs['avg_max_profit']}%, 止损触发率={bs['stop_loss_hit_rate']}, "
             f"5日胜率={bs['win_rate_5d']}")
    log.info(f"卖出信号 {ss['count']} 个: 避险有效率={ss['effective_rate']}, "
             f"平均规避跌幅={ss['avg_avoided_loss']}%, 误报率={ss['false_alarm_rate']}")

    # 多窗口口径: 这是判断策略是否正期望的核心输出
    for side_key, label in (('buy_by_window', '买入'), ('sell_by_window', '卖出')):
        for w in REVIEW_WINDOWS:
            s = result.get(side_key, {}).get(str(w), {})
            if not s.get('count'):
                continue
            log.info(f"[{label}·{w}日窗口] n={s['count']} 胜率={s['win_rate']} "
                     f"盈亏比={s['payoff_ratio']} 盈亏平衡胜率={s['breakeven_win_rate']} "
                     f"期望={s['expectancy_r']}R (不设止损={s['expectancy_r_raw']}R) "
                     f"MFE={s['avg_mfe']}% MAE={s['avg_mae']}%")
    pbw = result.get('pending_by_window', {})
    if pbw:
        log.info("各窗口观察中(未满窗): " + ", ".join(
            f"{w}日 买{pbw.get(str(w), {}).get('buy_count', 0)}/"
            f"卖{pbw.get(str(w), {}).get('sell_count', 0)}" for w in REVIEW_WINDOWS))

    # 市场环境归因: 区分策略 alpha 与环境 beta
    mc = result.get('market_context', {})
    if mc.get('available'):
        log.info(f"市场环境: 情绪均值={mc.get('avg_composite')} "
                 f"区间=[{mc.get('min_composite')}, {mc.get('max_composite')}] "
                 f"相位={mc.get('phase_span')} 升温={mc.get('rising')}")
        if mc.get('rising'):
            log.warning("本周情绪处于升温通道, 买入胜率含较大市场 beta 成分, "
                        "不可直接视为策略 alpha")
    bbp = result.get('buy_by_phase', {})
    if bbp:
        for ph, s in bbp.items():
            if s.get('count'):
                log.info(f"[买入·环境={ph}] n={s['count']} 胜率={s['win_rate']} "
                         f"期望={s['expectancy_r']}R 止损触发={s['stop_loss_hit_rate']}")

    pd_ = result.get('pending', {})
    if (pd_.get('buy_count', 0) + pd_.get('sell_count', 0)) > 0:
        log.warning(f"观察期提示: 另有买入 {pd_.get('buy_count')} 个 / 卖出 {pd_.get('sell_count')} 个信号"
                    f"因不足 {pd_.get('min_bars_required')} 个交易日未纳入统计, "
                    f"需等窗口满后重跑本周复盘")

    dq = result.get('data_quality', {})
    if dq.get('fallback_warning'):
        log.warning(f"数据质量提示: 基准价来源={dq.get('entry_source_counts')}, "
                    f"可信比例={dq.get('reliable_rate')} "
                    f"(price_fallback 表示历史信号无 entry_price, 可操作率会失真)")

    # === 企微推送(需显式 --push; 原实现该段落在 empty_result() return 之后, 永远不可达) ===
    if args.push:
        try:
            msg = _format_review_push(result)
            if msg:
                _push_wecom(msg)
        except Exception as e:
            log.error('复盘推送异常: %s', e)


if __name__ == "__main__":
    main()
