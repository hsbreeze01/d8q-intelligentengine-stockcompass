#!/usr/bin/env python3
"""每周复盘脚本 - 信号回测与统计

功能:
1. 从 czsc_signal_history 表查询过去一周产生的所有信号(查询层去重)
2. 对每个信号，查询信号日之后5个交易日的行情数据(stock_data_daily)
3. 买入信号与卖出信号分开评估:
   - 买入信号: 可操作性(能否在 entry_zone 买到) + 最高收益 + 止损触发 + 5日胜率
   - 卖出信号: 避险有效性(信号后是否下跌) + 规避跌幅 + 误报率(信号后反而上涨)
4. 按信号类型和评分分组统计
5. 输出到 review_stats.json 供前端展示

用法:
    python review_weekly.py             # 默认回顾上一周
    python review_weekly.py --week 30   # 回顾第30周
    python review_weekly.py --week 2026-W30  # ISO周格式
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
# 复盘观察窗口: 需要信号日之后至少这么多个交易日的数据才纳入统计
# 不足时该信号仍在观察期(pending), 计入统计会使"5日"类指标失真
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


def fetch_signals(conn, start_date, end_date):
    """查询指定周期内的所有信号

    P1-1 防御性去重: 即使 uk_signal 唯一索引失效或历史脏数据残留,
    也保证每个 (signal_date, code, type) 只统计一次。
    优先保留 entry_price 非空的记录(新格式), 其次保留 id 最大的。
    """
    trading_days = fetch_trading_days(conn, start_date, end_date)
    if not trading_days:
        log.warning(f"区间 {start_date} ~ {end_date} 内无交易日，返回空结果")
        return []

    placeholders = ','.join(['%s'] * len(trading_days))
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
            WHERE signal_date IN ({placeholders})
            GROUP BY signal_date, code, type
        ) k ON h.id = k.keep_id
        ORDER BY h.signal_date, h.code
    """
    with conn.cursor() as cur:
        cur.execute(sql, trading_days)
        return cur.fetchall()


def fetch_post_signal_bars(conn, code, signal_date, num_days=5):
    """查询信号日之后N个交易日的行情数据"""
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


def analyze_buy_signal(signal, bars, entry_price, entry_source):
    """分析买入信号: 可操作性 + 收益 + 止损"""
    stop_loss_price = to_float(signal.get('stop_loss'))
    zone_low = entry_price * (1 - ENTRY_ZONE_PCT)
    zone_high = entry_price * (1 + ENTRY_ZONE_PCT)

    had_chance = False
    best_entry = None
    max_high = 0.0
    hit_stop_loss = False
    day5_close = None

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
        if bar_high > max_high:
            max_high = bar_high
        if stop_loss_price and bar_low <= stop_loss_price:
            hit_stop_loss = True
        day5_close = bar_close

    if not hit_stop_loss and stop_loss_price is None:
        for bar in bars:
            bar_low = to_float(bar['low'])
            if bar_low and (bar_low - entry_price) / entry_price <= DEFAULT_STOP_LOSS_PCT:
                hit_stop_loss = True
                break

    max_profit_pct = round((max_high - entry_price) / entry_price * 100, 2) if max_high > 0 else 0
    day5_pnl_pct = round((day5_close - entry_price) / entry_price * 100, 2) if day5_close else None

    return {
        'side': 'buy',
        'entry_price': entry_price,
        'entry_source': entry_source,
        'had_chance': had_chance,
        'best_entry': best_entry,
        'max_profit_pct': max_profit_pct,
        'day5_pnl_pct': day5_pnl_pct,
        'hit_stop_loss': hit_stop_loss,
    }


def analyze_sell_signal(signal, bars, entry_price, entry_source):
    """分析卖出信号: 避险有效性

    卖出信号的正确性与买入相反:
    - 信号后价格下跌 => 避险成功(避免了亏损)
    - 信号后价格上涨 => 误报(卖早了, 错失收益)
    指标语义:
    - avoided_loss_pct: 信号后5日最大跌幅(正数表示成功规避的跌幅)
    - day5_pnl_pct: 5日后收盘相对信号价的涨跌(负数=卖对了)
    - effective: 5日内最低价跌破阈值 => 避险有效
    - false_alarm: 5日收盘反而涨超阈值 => 误报
    """
    min_low = None
    max_high = 0.0
    day5_close = None

    for bar in bars:
        bar_low = to_float(bar['low'])
        bar_high = to_float(bar['high'])
        bar_close = to_float(bar['close'])
        if bar_low is None or bar_high is None:
            continue
        if min_low is None or bar_low < min_low:
            min_low = bar_low
        if bar_high > max_high:
            max_high = bar_high
        day5_close = bar_close

    # 最大跌幅(负数): 信号后5日内最低点相对信号价
    max_drop_pct = round((min_low - entry_price) / entry_price * 100, 2) if min_low else 0
    # 规避的跌幅(正数, 便于阅读): 卖出后股价最深跌了多少
    avoided_loss_pct = round(-max_drop_pct, 2) if max_drop_pct < 0 else 0
    # 错失的涨幅: 仅当信号后价格确实涨超信号价时才为正, 否则为 0
    raw_gain = (max_high - entry_price) / entry_price * 100 if max_high > 0 else 0
    missed_gain_pct = round(max(0.0, raw_gain), 2)
    day5_pnl_pct = round((day5_close - entry_price) / entry_price * 100, 2) if day5_close else None

    # 避险有效: 5日后收盘价低于信号价 => 卖出决策正确
    effective = day5_pnl_pct is not None and day5_pnl_pct < 0
    # 误报: 信号后5日内最高价涨超阈值 => 卖早了
    false_alarm = missed_gain_pct >= SELL_FALSE_ALARM_PCT

    return {
        'side': 'sell',
        'entry_price': entry_price,
        'entry_source': entry_source,
        'max_drop_pct': max_drop_pct,
        'avoided_loss_pct': avoided_loss_pct,
        'missed_gain_pct': missed_gain_pct,
        'day5_pnl_pct': day5_pnl_pct,
        'effective': effective,
        'false_alarm': false_alarm,
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
        'pending': {'buy_count': 0, 'sell_count': 0, 'min_bars_required': MIN_REVIEW_BARS,
                    'buy_details': [], 'sell_details': []},
        'data_quality': {'entry_source_counts': {}, 'reliable_rate': 0, 'fallback_warning': False},
        'buy_summary': compute_buy_stats([]),
        'sell_summary': compute_sell_stats([]),
        'buy_by_type': {}, 'sell_by_type': {},
        'buy_by_grade': {}, 'sell_by_grade': {},
        'buy_details': [], 'sell_details': [],
        # 兼容旧前端字段
        'summary': compute_buy_stats([]),
        'by_type': {}, 'by_grade': {}, 'details': [],
    }



    # === 企微推送 ===
    try:
        msg = _format_review_push(result)
        if msg:
            _push_wecom(msg)
    except Exception as e:
        log.error('复盘推送异常: %s', e)

    dq = result.get('data_quality', {})
    if dq.get('fallback_warning'):
        log.warning(f"数据质量提示: 基准价来源={dq.get('entry_source_counts')}, "
                    f"可信比例={dq.get('reliable_rate')} "
                    f"(price_fallback 表示历史信号无 entry_price, 可操作率会失真)")




# === 企微推送 ===
WECOM_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=%s"
WEBHOOK_KEY = "7c097c2e-d664-46e4-bbdc-39ff5bc1b537"


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
    import urllib.request, json as _json
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
    args = parser.parse_args()

    monday, friday, sunday, week_str = parse_week_arg(args.week)
    period_str = f"{monday} ~ {friday}"
    log.info(f"复盘周期: {week_str} ({period_str})")

    conn = get_db_connection()
    try:
        trading_days = fetch_trading_days(conn, monday, sunday)
        log.info(f"区间内有效交易日 {len(trading_days)} 天: "
                 f"{[str(d) for d in trading_days]}")
        signals = fetch_signals(conn, monday, sunday)
        log.info(f"查询到 {len(signals)} 个信号(已去重, 已过滤非交易日脏数据)")

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
                'pending': {
                    'buy_count': len(pending_buy),
                    'sell_count': len(pending_sell),
                    'min_bars_required': MIN_REVIEW_BARS,
                    'buy_details': pending_buy,
                    'sell_details': pending_sell,
                },
                'data_quality': data_quality,
                'buy_summary': buy_summary,
                'sell_summary': sell_summary,
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
    pd_ = result.get('pending', {})
    if (pd_.get('buy_count', 0) + pd_.get('sell_count', 0)) > 0:
        log.warning(f"观察期提示: 另有买入 {pd_.get('buy_count')} 个 / 卖出 {pd_.get('sell_count')} 个信号"
                    f"因不足 {pd_.get('min_bars_required')} 个交易日未纳入统计, "
                    f"需等窗口满后重跑本周复盘")


if __name__ == "__main__":
    main()
