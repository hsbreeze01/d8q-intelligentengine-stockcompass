#!/usr/bin/env python3
"""信号结果回填Job

每日收盘后执行，追踪所有pending/triggered状态的信号后续走势：
- 计算最大有利/不利幅度
- 判断是否触发止损/目标
- 超过10个交易日标记为expired
- 写入结果字段

调度：每日16:00执行（在czsc_scan 15:40之后）
"""
import sys
import pymysql
import logging
from datetime import datetime, date

sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('signal_review')

DB = {
    'host': '127.0.0.1', 'port': 3306, 'user': 'root',
    'password': 'password', 'database': 'stock_analysis_system', 'charset': 'utf8mb4'
}

MAX_HOLD_DAYS = 10  # 最大持仓天数，超过标记expired


def code_to_board(code):
    """根据股票代码判断板块"""
    prefix = code[:3]
    if prefix in ('300', '301'):
        return 'gem'     # 创业板
    elif prefix == '688':
        return 'star'    # 科创板
    elif prefix in ('430', '830', '831', '832', '833', '834', '835', '836', '837', '838', '839', '870', '871', '872', '873'):
        return 'bse'     # 北交所
    else:
        return 'main'    # 主板 (600/601/603/605/000/001/002/003)


def get_tier(conn, code):
    """根据成交额计算tier"""
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute(
        "SELECT AVG(turnover) as avg_to FROM stock_data_daily "
        "WHERE stock_code=%s AND date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)", (code,)
    )
    r = cur.fetchone()
    if not r or not r['avg_to']:
        return 'D'
    avg = float(r['avg_to'])
    if avg >= 1000000000:
        return 'A'
    elif avg >= 500000000:
        return 'B'
    elif avg >= 300000000:
        return 'C'
    return 'D'


def review_signals():
    """主函数：回填所有需要复盘的信号"""
    conn = pymysql.connect(**DB)
    cur = conn.cursor(pymysql.cursors.DictCursor)

    # 获取所有待复盘信号（pending或triggered）
    cur.execute(
        "SELECT id, stock_code, signal_date, signal_type, signal_price, "
        "stop_loss, target_price, status, tier, board "
        "FROM chanlun_signals WHERE status IN ('pending', 'triggered') "
        "ORDER BY signal_date"
    )
    signals = cur.fetchall()
    log.info("待复盘信号: %d 条", len(signals))

    reviewed = 0
    for sig in signals:
        sid = sig['id']
        code = sig['stock_code']
        sig_date = sig['signal_date']
        sig_price = float(sig['signal_price']) if sig['signal_price'] else None
        stop_loss = float(sig['stop_loss']) if sig['stop_loss'] else None
        target_price = float(sig['target_price']) if sig['target_price'] else None
        sig_type = sig['signal_type']
        is_buy = sig_type.startswith('buy')

        if not sig_price:
            continue

        # 补填board和tier（如果缺失）
        board = sig['board'] or code_to_board(code)
        tier = sig['tier'] or get_tier(conn, code)

        # 获取信号日之后的K线数据
        cur.execute(
            "SELECT date, open, high, low, close FROM stock_data_daily "
            "WHERE stock_code=%s AND date > %s ORDER BY date",
            (code, sig_date)
        )
        after_klines = cur.fetchall()

        if not after_klines:
            # 还没有后续数据，跳过
            # 但补填board/tier
            cur.execute(
                "UPDATE chanlun_signals SET board=%s, tier=%s WHERE id=%s",
                (board, tier, sid)
            )
            continue

        # 计算走势指标
        max_favorable = 0.0  # 最大有利方向幅度(%)
        max_adverse = 0.0    # 最大不利方向幅度(%)
        exit_date = None
        exit_price = None
        exit_reason = None
        hold_days = len(after_klines)

        for i, k in enumerate(after_klines):
            high = float(k['high'])
            low = float(k['low'])
            close = float(k['close'])

            if is_buy:
                # 买入信号：上涨有利，下跌不利
                favorable = (high - sig_price) / sig_price * 100
                adverse = (sig_price - low) / sig_price * 100
            else:
                # 卖出信号：下跌有利，上涨不利
                favorable = (sig_price - low) / sig_price * 100
                adverse = (high - sig_price) / sig_price * 100

            max_favorable = max(max_favorable, favorable)
            max_adverse = max(max_adverse, adverse)

            # 检查止损
            if stop_loss and not exit_date:
                if is_buy and low <= stop_loss:
                    exit_date = k['date']
                    exit_price = stop_loss
                    exit_reason = 'stop_loss'
                    hold_days = i + 1
                elif not is_buy and high >= stop_loss:
                    exit_date = k['date']
                    exit_price = stop_loss
                    exit_reason = 'stop_loss'
                    hold_days = i + 1

            # 检查目标
            if target_price and not exit_date:
                if is_buy and high >= target_price:
                    exit_date = k['date']
                    exit_price = target_price
                    exit_reason = 'target_hit'
                    hold_days = i + 1
                elif not is_buy and low <= target_price:
                    exit_date = k['date']
                    exit_price = target_price
                    exit_reason = 'target_hit'
                    hold_days = i + 1

        # 判断最终状态
        if exit_reason:
            status = exit_reason  # stop_loss or target_hit
        elif hold_days >= MAX_HOLD_DAYS:
            status = 'expired'
            exit_date = after_klines[min(MAX_HOLD_DAYS - 1, len(after_klines) - 1)]['date']
            exit_price = float(after_klines[min(MAX_HOLD_DAYS - 1, len(after_klines) - 1)]['close'])
            exit_reason = 'expired'
            hold_days = MAX_HOLD_DAYS
        else:
            status = 'triggered'  # 仍在持仓期内，等待后续数据

        # 计算盈亏
        pnl_pct = None
        if exit_price:
            if is_buy:
                pnl_pct = round((float(exit_price) - sig_price) / sig_price * 100, 2)
            else:
                pnl_pct = round((sig_price - float(exit_price)) / sig_price * 100, 2)

        # 更新数据库
        cur.execute(
            "UPDATE chanlun_signals SET "
            "tier=%s, board=%s, status=%s, "
            "max_favorable_pct=%s, max_adverse_pct=%s, "
            "exit_date=%s, exit_price=%s, exit_reason=%s, "
            "pnl_pct=%s, hold_days=%s, reviewed_at=NOW() "
            "WHERE id=%s",
            (tier, board, status,
             round(max_favorable, 2), round(max_adverse, 2),
             exit_date, exit_price, exit_reason,
             pnl_pct, hold_days, sid)
        )
        reviewed += 1

    conn.commit()
    conn.close()
    log.info("复盘完成: reviewed=%d", reviewed)
    return reviewed


def _calc_avg_hold_days(completed):
    """估算平均持仓天数"""
    total_days = 0
    count = 0
    for s in completed:
        if s.get('day10_close') and float(s['day10_close'] or 0) != 0:
            days = 10
        elif s.get('day5_close') and float(s['day5_close'] or 0) != 0:
            days = 5
        elif s.get('day3_close') and float(s['day3_close'] or 0) != 0:
            days = 3
        else:
            days = 1
        # 如果触发止损，持仓通常更短
        if s.get('stop_loss') and s.get('price') and s.get('min_pnl'):
            price = float(s['price'] or 1)
            if price > 0:
                sl_pct = abs(price - float(s['stop_loss'] or 0)) / price * 100
                if abs(float(s['min_pnl'] or 0)) >= sl_pct * 0.9:
                    days = min(days, 3)
        total_days += days
        count += 1
    return round(total_days / count, 1) if count else 0


def _calc_exit_reasons(completed):
    """统计出场原因分布"""
    stop_loss = 0
    target_hit = 0
    expired = 0
    for s in completed:
        outcome = s.get('outcome', '')
        if outcome == 'loss':
            if s.get('stop_loss') and s.get('price') and s.get('min_pnl'):
                price = float(s['price'] or 1)
                if price > 0:
                    sl_pct = abs(price - float(s['stop_loss'] or 0)) / price * 100
                    if abs(float(s['min_pnl'] or 0)) >= sl_pct * 0.8:
                        stop_loss += 1
                        continue
            expired += 1
        elif outcome == 'win':
            target_hit += 1
        else:
            expired += 1
    return {'stop_loss': stop_loss, 'target_hit': target_hit, 'expired': expired}


def generate_review_stats():
    """生成复盘统计JSON供前端使用 — 基于czsc_signal_history表"""
    import json

    conn = pymysql.connect(**DB)
    cur = conn.cursor(pymysql.cursors.DictCursor)

    # 先执行回填：对czsc_signal_history中尚未回填的信号计算后续走势
    _backfill_czsc_history(conn)

    # 统计已有outcome的信号
    cur.execute(
        "SELECT signal_date, code, name, type, price, stop_loss, score, grade, "
        "reason, market_attitude, seg_zg, seg_zd, "
        "next_open, day3_close, day5_close, day10_close, max_pnl, min_pnl, outcome "
        "FROM czsc_signal_history WHERE outcome IS NOT NULL "
        "ORDER BY signal_date DESC"
    )
    completed = cur.fetchall()
    conn.close()

    if not completed:
        stats = {'total': 0, 'message': '暂无已完成复盘，新引擎信号将在产出后自动回填'}
        _save_stats(stats)
        return stats

    total = len(completed)
    wins = [s for s in completed if s['outcome'] == 'win']
    losses = [s for s in completed if s['outcome'] == 'loss']
    win_rate = len(wins) / total * 100 if total else 0
    avg_max_pnl = sum(float(s['max_pnl'] or 0) for s in completed) / total
    avg_min_pnl = sum(float(s['min_pnl'] or 0) for s in completed) / total
    avg_win = sum(float(s['max_pnl'] or 0) for s in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(float(s['min_pnl'] or 0) for s in losses) / len(losses)) if losses else 1
    profit_loss_ratio = round(avg_win / avg_loss, 2) if avg_loss else 0

    # 分类型统计
    by_type = {}
    for s in completed:
        t = s['type']
        if t not in by_type:
            by_type[t] = {'total': 0, 'wins': 0, 'pnl_sum': 0}
        by_type[t]['total'] += 1
        if s['outcome'] == 'win':
            by_type[t]['wins'] += 1
        by_type[t]['pnl_sum'] += float(s['max_pnl'] or 0)
    for t in by_type:
        by_type[t]['win_rate'] = round(by_type[t]['wins'] / by_type[t]['total'] * 100, 1)
        by_type[t]['avg_pnl'] = round(by_type[t]['pnl_sum'] / by_type[t]['total'], 2)

    # 分板块统计
    by_board = {}
    for s in completed:
        b = _code_to_board_static(s['code'])
        if b not in by_board:
            by_board[b] = {'total': 0, 'wins': 0, 'pnl_sum': 0}
        by_board[b]['total'] += 1
        if s['outcome'] == 'win':
            by_board[b]['wins'] += 1
        by_board[b]['pnl_sum'] += float(s['max_pnl'] or 0)
    for b in by_board:
        by_board[b]['win_rate'] = round(by_board[b]['wins'] / by_board[b]['total'] * 100, 1)
        by_board[b]['avg_pnl'] = round(by_board[b]['pnl_sum'] / by_board[b]['total'], 2)

    # 分评分等级统计
    by_grade = {}
    for s in completed:
        g = str(s['grade'] or 0)
        if g not in by_grade:
            by_grade[g] = {'total': 0, 'wins': 0}
        by_grade[g]['total'] += 1
        if s['outcome'] == 'win':
            by_grade[g]['wins'] += 1
    for g in by_grade:
        by_grade[g]['win_rate'] = round(by_grade[g]['wins'] / by_grade[g]['total'] * 100, 1)

    stats = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total': total,
        'win_rate': round(win_rate, 1),
        'profit_loss_ratio': profit_loss_ratio,
        'avg_max_favorable': round(avg_max_pnl, 2),
        'avg_max_adverse': round(avg_min_pnl, 2),
        'avg_hold_days': _calc_avg_hold_days(completed),
        'exit_reasons': _calc_exit_reasons(completed),
        'by_type': by_type,
        'by_board': by_board,
        'by_grade': by_grade,
        'outcomes': {
            'win': len(wins),
            'loss': len(losses),
            'breakeven': total - len(wins) - len(losses),
        },
        'recent': [
            {
                'date': str(s['signal_date']), 'code': s['code'], 'name': s['name'],
                'type': s['type'], 'score': s['score'],
                'max_pnl': float(s['max_pnl'] or 0), 'min_pnl': float(s['min_pnl'] or 0),
                'outcome': s['outcome'],
                'board': _code_to_board_static(s['code']),
            }
            for s in completed[:20]
        ]
    }

    _save_stats(stats)
    log.info("复盘统计已生成: total=%d win_rate=%.1f%%", total, win_rate)
    return stats


# P0-A2: signal_review 的统计输出改用独立文件。
# review_stats.json 由 review_weekly.py 独占(前端 /api/chanlun/review 的唯一数据源),
# 两者 schema 不同(本脚本不区分买卖、按10日窗口; review_weekly 区分买卖、
# 按 5/10/20 三档窗口并输出 MFE/MAE 与 R 倍数期望, 且带观察窗口完整性校验),
# 若共用同一文件会每日互相覆盖。
SIGNAL_REVIEW_STATS_PATH = ('/home/ecs-assist-user/d8q-intelligentengine-stockcompass'
                            '/chanlun/strategy/signal_review_stats.json')


def _save_stats(stats):
    import json
    stats = dict(stats)
    stats['_schema'] = 'signal_review_v1'
    stats['_note'] = ('本文件由 signal_review.py 每日16:00 生成, 不区分买卖方向、'
                      '观察窗口10日; 前端复盘页读取的是 review_stats.json'
                      '(由 review_weekly.py 周五16:30 生成)')
    with open(SIGNAL_REVIEW_STATS_PATH, 'w') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2, default=str)


def _code_to_board_static(code):
    prefix = code[:3]
    if prefix in ('300', '301'):
        return 'gem'
    elif prefix == '688':
        return 'star'
    elif prefix in ('430', '830', '831'):
        return 'bse'
    return 'main'


def _backfill_czsc_history(conn):
    """回填czsc_signal_history中尚未有outcome的信号"""
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute(
        "SELECT id, signal_date, code, type, price, stop_loss "
        "FROM czsc_signal_history WHERE outcome IS NULL AND signal_date < CURDATE()"
    )
    pending = cur.fetchall()
    if not pending:
        return

    filled = 0
    for sig in pending:
        sid = sig['id']
        code = sig['code']
        sig_date = sig['signal_date']
        sig_price = float(sig['price']) if sig['price'] else None
        stop_loss = float(sig['stop_loss']) if sig['stop_loss'] else None
        is_buy = sig['type'].startswith('buy')

        if not sig_price:
            continue

        # 获取信号后的K线
        cur.execute(
            "SELECT date, open, high, low, close FROM stock_data_daily "
            "WHERE stock_code=%s AND date > %s ORDER BY date LIMIT 10",
            (code, sig_date)
        )
        klines = cur.fetchall()
        if not klines:
            continue

        # 各时间点收盘价
        next_open = float(klines[0]['open']) if klines else None
        next_close = float(klines[0]['close']) if klines else None
        day3_close = float(klines[2]['close']) if len(klines) > 2 else None
        day5_close = float(klines[4]['close']) if len(klines) > 4 else None
        day10_close = float(klines[9]['close']) if len(klines) > 9 else None

        # 最大盈亏
        max_pnl = 0
        min_pnl = 0
        for k in klines:
            high = float(k['high'])
            low = float(k['low'])
            if is_buy:
                pnl_high = (high - sig_price) / sig_price * 100
                pnl_low = (low - sig_price) / sig_price * 100
            else:
                pnl_high = (sig_price - low) / sig_price * 100
                pnl_low = (sig_price - high) / sig_price * 100
            max_pnl = max(max_pnl, pnl_high)
            min_pnl = min(min_pnl, pnl_low)

        # 判断outcome
        # win: 最大有利>=3% 且 未触发止损(min_pnl > -止损幅度)
        # loss: 触发止损
        sl_pct = abs(sig_price - stop_loss) / sig_price * 100 if stop_loss else 5
        if min_pnl <= -sl_pct:
            outcome = 'loss'
        elif max_pnl >= 3:
            outcome = 'win'
        elif len(klines) >= 10:
            # 10天后按day10收盘判断
            final_pnl = (float(klines[-1]['close']) - sig_price) / sig_price * 100 if is_buy else (sig_price - float(klines[-1]['close'])) / sig_price * 100
            outcome = 'win' if final_pnl > 0 else 'loss'
        else:
            continue  # 数据不足，等后续

        cur.execute(
            "UPDATE czsc_signal_history SET "
            "next_open=%s, next_close=%s, day3_close=%s, day5_close=%s, day10_close=%s, "
            "max_pnl=%s, min_pnl=%s, outcome=%s WHERE id=%s",
            (next_open, next_close, day3_close, day5_close, day10_close,
             round(max_pnl, 2), round(min_pnl, 2), outcome, sid)
        )
        filled += 1

    conn.commit()
    log.info("czsc_signal_history回填: %d/%d", filled, len(pending))
    return filled


# ---------------------------------------------------------------------------
# P0-A1: 此处原有一段从 generate_review_stats() 复制来的统计代码,
# 引用了本函数作用域不存在的 `completed` 变量, 每次执行必抛 NameError,
# 导致每日16:00 的 signal_review 调度任务长期崩溃(回填能完成, 统计永远失败)。
# 该块还包含第二处 review_stats.json 写入, 与 review_weekly.py 争抢同一文件。
# 本函数职责应只限于"回填 czsc_signal_history 的 outcome/pnl 列", 故整块移除。
# 统计输出统一由 generate_review_stats() -> _save_stats() 负责。
# ---------------------------------------------------------------------------


if __name__ == '__main__':
    reviewed = review_signals()
    stats = generate_review_stats()
    print(f"signal_review: reviewed={reviewed}, stats_total={stats.get('total', 0)}")
