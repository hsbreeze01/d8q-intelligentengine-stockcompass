#!/usr/bin/env python3
"""周期性复盘报告 + 规则参数反馈建议

功能:
1. 每周五16:30自动生成本周信号复盘周报
2. 对比本周 vs 前一周的表现趋势
3. 基于累积数据给出规则调整建议
4. 推送企微 + 存档到 review_weekly/ 目录

调度: scheduler每周五16:30调用
"""
import sys
import os
import json
import pymysql
import logging
from datetime import datetime, timedelta
from collections import Counter

sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('weekly_review')

DB = {
    'host': '127.0.0.1', 'port': 3306, 'user': 'root',
    'password': 'password', 'database': 'stock_analysis_system', 'charset': 'utf8mb4'
}

ARCHIVE_DIR = '/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/strategy/review_weekly'
WECOM_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=7c097c2e-d664-46e4-bbdc-39ff5bc1b537"


def _code_to_board(code):
    prefix = code[:3]
    if prefix in ('300', '301'):
        return 'gem'
    elif prefix == '688':
        return 'star'
    return 'main'


def get_week_range(ref_date=None):
    """获取指定日期所在周的周一~周五范围"""
    if ref_date is None:
        ref_date = datetime.now().date()
    weekday = ref_date.weekday()
    monday = ref_date - timedelta(days=weekday)
    friday = monday + timedelta(days=4)
    return monday, friday


def query_week_signals(conn, start_date, end_date):
    """查询指定周的已完成信号"""
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute(
        "SELECT signal_date, code, name, type, price, stop_loss, score, grade, "
        "reason, market_attitude, next_open, day3_close, day5_close, day10_close, "
        "max_pnl, min_pnl, outcome "
        "FROM czsc_signal_history "
        "WHERE signal_date BETWEEN %s AND %s AND outcome IS NOT NULL "
        "ORDER BY signal_date",
        (start_date, end_date)
    )
    return cur.fetchall()


def compute_stats(signals):
    """计算一组信号的统计指标"""
    if not signals:
        return {'total': 0, 'win_rate': 0, 'avg_pnl': 0, 'profit_loss_ratio': 0}

    total = len(signals)
    wins = [s for s in signals if s['outcome'] == 'win']
    losses = [s for s in signals if s['outcome'] == 'loss']
    win_rate = len(wins) / total * 100 if total else 0
    avg_max_pnl = sum(float(s['max_pnl'] or 0) for s in signals) / total
    avg_min_pnl = sum(float(s['min_pnl'] or 0) for s in signals) / total
    avg_win = sum(float(s['max_pnl'] or 0) for s in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(float(s['min_pnl'] or 0) for s in losses) / len(losses)) if losses else 1
    plr = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0

    # 分维度
    by_type = {}
    for s in signals:
        t = s['type']
        if t not in by_type:
            by_type[t] = {'total': 0, 'wins': 0}
        by_type[t]['total'] += 1
        if s['outcome'] == 'win':
            by_type[t]['wins'] += 1
    for t in by_type:
        by_type[t]['win_rate'] = round(by_type[t]['wins'] / by_type[t]['total'] * 100, 1)

    by_board = {}
    for s in signals:
        b = _code_to_board(s['code'])
        if b not in by_board:
            by_board[b] = {'total': 0, 'wins': 0}
        by_board[b]['total'] += 1
        if s['outcome'] == 'win':
            by_board[b]['wins'] += 1
    for b in by_board:
        by_board[b]['win_rate'] = round(by_board[b]['wins'] / by_board[b]['total'] * 100, 1)

    by_grade = {}
    for s in signals:
        g = s['grade'] or 0
        g_label = '⭐⭐⭐' if g >= 3 else ('⭐⭐' if g >= 2 else '⭐')
        if g_label not in by_grade:
            by_grade[g_label] = {'total': 0, 'wins': 0}
        by_grade[g_label]['total'] += 1
        if s['outcome'] == 'win':
            by_grade[g_label]['wins'] += 1
    for g in by_grade:
        by_grade[g]['win_rate'] = round(by_grade[g]['wins'] / by_grade[g]['total'] * 100, 1)

    return {
        'total': total,
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': round(win_rate, 1),
        'avg_max_pnl': round(avg_max_pnl, 2),
        'avg_min_pnl': round(avg_min_pnl, 2),
        'profit_loss_ratio': plr,
        'by_type': by_type,
        'by_board': by_board,
        'by_grade': by_grade,
    }


# ============================================================
# 规则参数反馈建议
# ============================================================

def generate_param_suggestions(all_signals):
    """基于累积复盘数据，自动分析规则参数调整建议"""
    suggestions = []
    if len(all_signals) < 10:
        suggestions.append({
            'level': 'info',
            'message': '数据量不足(<%d条)，建议累积至少20条已完成信号后再做参数调优' % len(all_signals)
        })
        return suggestions

    total = len(all_signals)
    wins = [s for s in all_signals if s['outcome'] == 'win']
    overall_wr = len(wins) / total * 100

    # 1. 分信号类型分析
    type_stats = {}
    for s in all_signals:
        t = s['type']
        if t not in type_stats:
            type_stats[t] = {'total': 0, 'wins': 0, 'pnl_sum': 0}
        type_stats[t]['total'] += 1
        if s['outcome'] == 'win':
            type_stats[t]['wins'] += 1
        type_stats[t]['pnl_sum'] += float(s['max_pnl'] or 0)

    for t, st in type_stats.items():
        wr = st['wins'] / st['total'] * 100 if st['total'] >= 5 else None
        if wr is not None and wr < 40:
            type_names = {'buy1': '一买', 'buy2': '二买', 'buy3': '三买',
                         'sell1': '一卖', 'sell2': '二卖', 'sell3': '三卖'}
            suggestions.append({
                'level': 'warning',
                'dimension': 'signal_type',
                'param': t,
                'message': '%s胜率仅%.1f%%(%d/%d)，建议提高该类型触发门槛或降低展示优先级' % (
                    type_names.get(t, t), wr, st['wins'], st['total']),
                'action': 'raise_threshold_or_demote'
            })
        elif wr is not None and wr > 65:
            suggestions.append({
                'level': 'positive',
                'dimension': 'signal_type',
                'param': t,
                'message': '%s胜率%.1f%%，表现优秀，可考虑加大该类型信号权重' % (
                    type_names.get(t, t), wr),
                'action': 'boost_weight'
            })

    # 2. 分评分等级分析
    grade_stats = {}
    for s in all_signals:
        g = s['grade'] or 0
        if g not in grade_stats:
            grade_stats[g] = {'total': 0, 'wins': 0}
        grade_stats[g]['total'] += 1
        if s['outcome'] == 'win':
            grade_stats[g]['wins'] += 1

    for g, st in grade_stats.items():
        if st['total'] < 5:
            continue
        wr = st['wins'] / st['total'] * 100
        if g >= 2 and wr < 50:
            suggestions.append({
                'level': 'warning',
                'dimension': 'score_threshold',
                'param': f'grade>={g}',
                'message': '评分等级%d(⭐×%d)胜率仅%.1f%%，评分系统区分度不足，建议调整评分权重' % (g, g, wr),
                'action': 'recalibrate_scorer'
            })
        if g <= 1 and wr > 55:
            suggestions.append({
                'level': 'info',
                'dimension': 'score_threshold',
                'param': f'grade={g}',
                'message': '低评分信号(⭐)胜率%.1f%%反而不低，评分维度可能需要重新校准' % wr,
                'action': 'review_score_dimensions'
            })

    # 3. 分板块分析
    board_stats = {}
    for s in all_signals:
        b = _code_to_board(s['code'])
        if b not in board_stats:
            board_stats[b] = {'total': 0, 'wins': 0}
        board_stats[b]['total'] += 1
        if s['outcome'] == 'win':
            board_stats[b]['wins'] += 1

    board_names = {'main': '主板', 'gem': '创业板', 'star': '科创板', 'bse': '北交所'}
    for b, st in board_stats.items():
        if st['total'] < 5:
            continue
        wr = st['wins'] / st['total'] * 100
        if wr < 35:
            suggestions.append({
                'level': 'warning',
                'dimension': 'board',
                'param': b,
                'message': '%s信号胜率仅%.1f%%，建议降低该板块信号权重或提高门槛' % (board_names.get(b, b), wr),
                'action': 'demote_board'
            })

    # 4. 止损有效性分析
    stopped = [s for s in all_signals if float(s['min_pnl'] or 0) <= -5]
    if len(stopped) > total * 0.4:
        suggestions.append({
            'level': 'warning',
            'dimension': 'stop_loss',
            'param': 'sl_pct=5%',
            'message': '%.0f%%的信号触及5%%止损线，止损可能设置过紧，建议放宽至7%%或优化入场时机' % (len(stopped) / total * 100),
            'action': 'widen_stop_loss'
        })

    # 5. 环境过滤有效性
    bull_sigs = [s for s in all_signals if s['market_attitude'] in ('bullish', 'neutral_bull')]
    bear_sigs = [s for s in all_signals if s['market_attitude'] in ('bearish', 'neutral_bear')]
    if bull_sigs and bear_sigs:
        bull_wr = sum(1 for s in bull_sigs if s['outcome'] == 'win') / len(bull_sigs) * 100
        bear_wr = sum(1 for s in bear_sigs if s['outcome'] == 'win') / len(bear_sigs) * 100
        if bear_wr < 30 and len(bear_sigs) >= 5:
            suggestions.append({
                'level': 'critical',
                'dimension': 'market_filter',
                'param': 'bearish_signals',
                'message': '空头环境下信号胜率仅%.1f%%，强烈建议空头市场不产出买入信号' % bear_wr,
                'action': 'filter_bearish_buys'
            })

    if not suggestions:
        suggestions.append({
            'level': 'positive',
            'message': '各维度表现均衡，暂无调整建议，继续累积数据观察'
        })

    return suggestions


# ============================================================
# 周报生成
# ============================================================

def generate_weekly_report(ref_date=None):
    """生成本周复盘报告"""
    conn = pymysql.connect(**DB)

    # 本周和上周范围
    today = ref_date or datetime.now().date()
    this_mon, this_fri = get_week_range(today)
    last_mon, last_fri = get_week_range(this_mon - timedelta(days=1))

    this_week = query_week_signals(conn, this_mon, this_fri)
    last_week = query_week_signals(conn, last_mon, last_fri)

    # 全量已完成信号(用于参数建议)
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute(
        "SELECT signal_date, code, name, type, price, stop_loss, score, grade, "
        "reason, market_attitude, max_pnl, min_pnl, outcome "
        "FROM czsc_signal_history WHERE outcome IS NOT NULL"
    )
    all_completed = cur.fetchall()
    conn.close()

    this_stats = compute_stats(this_week)
    last_stats = compute_stats(last_week)
    all_stats = compute_stats(all_completed)

    # 趋势对比
    def trend_arrow(curr, prev):
        if curr > prev:
            return '↑'
        elif curr < prev:
            return '↓'
        return '→'

    # 参数建议
    suggestions = generate_param_suggestions(all_completed)

    report = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'period': {
            'this_week': f'{this_mon} ~ {this_fri}',
            'last_week': f'{last_mon} ~ {last_fri}',
        },
        'this_week': this_stats,
        'last_week': last_stats,
        'cumulative': all_stats,
        'trend': {
            'win_rate': trend_arrow(this_stats['win_rate'], last_stats['win_rate']),
            'total': trend_arrow(this_stats['total'], last_stats['total']),
            'plr': trend_arrow(this_stats['profit_loss_ratio'], last_stats['profit_loss_ratio']),
        },
        'suggestions': suggestions,
    }

    # 存档
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    archive_path = os.path.join(ARCHIVE_DIR, f'weekly_{this_fri}.json')
    with open(archive_path, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    log.info("周报已存档: %s", archive_path)

    return report


def format_weekly_markdown(report):
    """生成企微推送的markdown格式周报"""
    tw = report['this_week']
    lw = report['last_week']
    cum = report['cumulative']
    trend = report['trend']
    sugg = report['suggestions']

    lines = []
    lines.append('## 📊 缠论信号周报')
    lines.append(f"**{report['period']['this_week']}**")
    lines.append('')

    # 本周总览
    if tw['total'] == 0:
        lines.append('本周无已完成信号（信号尚在持仓期或本周无信号产出）')
    else:
        lines.append(f"### 本周表现")
        lines.append(f"- 信号数: **{tw['total']}** (上周{lw['total']}) {trend['total']}")
        lines.append(f"- 胜率: **{tw['win_rate']}%** (上周{lw['win_rate']}%) {trend['win_rate']}")
        lines.append(f"- 盈亏比: **{tw['profit_loss_ratio']}** (上周{lw['profit_loss_ratio']}) {trend['plr']}")
        lines.append(f"- 平均最大盈利: {tw['avg_max_pnl']}%")
        lines.append(f"- 平均最大回撤: {tw['avg_min_pnl']}%")
        lines.append('')

        # 分类型
        if tw['by_type']:
            lines.append('**按类型:**')
            type_names = {'buy1': '一买', 'buy2': '二买', 'buy3': '三买',
                         'sell1': '一卖', 'sell2': '二卖', 'sell3': '三卖'}
            for t, st in tw['by_type'].items():
                lines.append(f"  {type_names.get(t, t)}: {st['total']}笔 胜率{st['win_rate']}%")
            lines.append('')

    # 累计统计
    lines.append(f"### 累计(全部{cum['total']}笔)")
    lines.append(f"- 胜率: {cum['win_rate']}% | 盈亏比: {cum['profit_loss_ratio']}")
    lines.append('')

    # 参数建议
    if sugg:
        lines.append('### 🔧 规则优化建议')
        for s in sugg:
            icon = {'critical': '🚨', 'warning': '⚠️', 'info': 'ℹ️', 'positive': '✅'}.get(s['level'], '•')
            lines.append(f"{icon} {s['message']}")
        lines.append('')

    lines.append(f"---\n生成时间: {report['generated_at']}")
    return '\n'.join(lines)


def push_weekly_report(markdown_content):
    """推送周报到企微"""
    import urllib.request
    body = json.dumps({
        'msgtype': 'markdown',
        'markdown': {'content': markdown_content}
    }).encode('utf-8')
    req = urllib.request.Request(
        WECOM_WEBHOOK_URL, data=body, method='POST',
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        if result.get('errcode') == 0:
            log.info("周报推送成功")
        else:
            log.error("周报推送失败: %s", result)
    except Exception as e:
        log.error("周报推送异常: %s", e)


if __name__ == '__main__':
    report = generate_weekly_report()
    md = format_weekly_markdown(report)
    print(md)
    print('\n---JSON---')
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str)[:2000])

    # 推送(带--push参数时)
    if '--push' in sys.argv:
        push_weekly_report(md)
