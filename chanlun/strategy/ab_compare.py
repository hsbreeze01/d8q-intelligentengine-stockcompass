#!/usr/bin/env python3
"""灰度A/B对照框架

支持同时运行两套规则参数(default vs experimental)，
对同一批标的产出信号后独立跟踪，复盘时分组对比。

使用方式:
  # 默认参数扫描(production)
  python czsc_scan.py --profile default

  # 实验参数扫描(灰度)
  python czsc_scan.py --profile experimental

  # 对比报告
  python ab_compare.py

规则配置文件: profiles/default.json, profiles/experimental.json
"""
import sys
import os
import json
import pymysql
import logging
from datetime import datetime

sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('ab_compare')

DB = {
    'host': '127.0.0.1', 'port': 3306, 'user': 'root',
    'password': 'password', 'database': 'stock_analysis_system', 'charset': 'utf8mb4'
}

PROFILES_DIR = '/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/strategy/profiles'


def ensure_profile_table():
    """确保czsc_signal_history有profile字段"""
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE czsc_signal_history ADD COLUMN profile VARCHAR(20) DEFAULT 'default'")
        conn.commit()
        log.info("Added profile column to czsc_signal_history")
    except Exception as e:
        if 'Duplicate column' in str(e):
            pass  # already exists
        else:
            log.warning("profile column: %s", e)
    conn.close()


def load_profile(name):
    """加载规则配置"""
    path = os.path.join(PROFILES_DIR, f'{name}.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    # 返回默认配置
    return get_default_profile()


def get_default_profile():
    """默认(当前生产)规则参数"""
    return {
        'name': 'default',
        'description': '当前生产规则',
        'params': {
            # 信号类型开关
            'enable_buy1': True,
            'enable_buy2': True,
            'enable_buy3': True,
            'enable_sell1': True,
            'enable_sell2': True,
            'enable_sell3': True,
            # 评分阈值
            'min_score_display': 0,       # 最低展示分(0=全部展示)
            'min_score_push': 70,         # 最低推送分
            # 止损参数
            'stop_loss_pct': 5.0,         # 止损百分比
            # 环境过滤
            'filter_bearish_buys': False,  # 空头市场是否过滤买入信号
            # 背驰阈值
            'divergence_threshold': 0.7,  # MACD面积比阈值
            # 标的池
            'min_turnover': 200000000,    # 最低日均成交额(2亿)
            # 二买条件
            'buy2_max_pullback_ratio': 0.50,  # 二买回调最大幅度(占上涨段)
            # 盘整一买条件
            'buy1_min_pivot_bis': 5,      # 盘整一买最少中枢内笔数
        }
    }


def get_experimental_profile():
    """实验规则参数(基于当前复盘反馈调整)"""
    return {
        'name': 'experimental',
        'description': '实验规则 - 收紧门槛+空头过滤',
        'params': {
            'enable_buy1': True,
            'enable_buy2': True,
            'enable_buy3': True,
            'enable_sell1': True,
            'enable_sell2': True,
            'enable_sell3': True,
            'min_score_display': 55,      # 提高展示门槛
            'min_score_push': 75,
            'stop_loss_pct': 7.0,         # 放宽止损到7%
            'filter_bearish_buys': True,  # 空头市场过滤买入
            'divergence_threshold': 0.65, # 更严格的背驰判断
            'min_turnover': 300000000,    # 提高到3亿
            'buy2_max_pullback_ratio': 0.40,  # 收紧二买回调
            'buy1_min_pivot_bis': 7,      # 盘整一买要求更充分
        }
    }


def save_profiles():
    """初始化保存默认和实验配置文件"""
    os.makedirs(PROFILES_DIR, exist_ok=True)
    for profile_func in (get_default_profile, get_experimental_profile):
        p = profile_func()
        path = os.path.join(PROFILES_DIR, f"{p['name']}.json")
        with open(path, 'w') as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        log.info("Profile saved: %s", path)


def compare_profiles():
    """对比两个profile的信号表现"""
    conn = pymysql.connect(**DB)
    cur = conn.cursor(pymysql.cursors.DictCursor)

    results = {}
    for profile in ('default', 'experimental'):
        cur.execute(
            "SELECT type, outcome, max_pnl, min_pnl, score, grade "
            "FROM czsc_signal_history WHERE profile=%s AND outcome IS NOT NULL",
            (profile,)
        )
        signals = cur.fetchall()
        if not signals:
            results[profile] = {'total': 0, 'message': '暂无已完成数据'}
            continue

        total = len(signals)
        wins = sum(1 for s in signals if s['outcome'] == 'win')
        avg_pnl = sum(float(s['max_pnl'] or 0) for s in signals) / total

        results[profile] = {
            'total': total,
            'wins': wins,
            'win_rate': round(wins / total * 100, 1),
            'avg_max_pnl': round(avg_pnl, 2),
            'by_type': {}
        }
        for s in signals:
            t = s['type']
            if t not in results[profile]['by_type']:
                results[profile]['by_type'][t] = {'total': 0, 'wins': 0}
            results[profile]['by_type'][t]['total'] += 1
            if s['outcome'] == 'win':
                results[profile]['by_type'][t]['wins'] += 1

    conn.close()

    # 生成对比报告
    report = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'profiles': results,
        'conclusion': _derive_conclusion(results)
    }

    path = '/home/ecs-assist-user/d8q-intelligentengine-stockcompass/chanlun/strategy/ab_compare_result.json'
    with open(path, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    log.info("A/B对比报告: %s", path)
    return report


def _derive_conclusion(results):
    """根据对比数据给出结论"""
    d = results.get('default', {})
    e = results.get('experimental', {})
    if d.get('total', 0) < 10 or e.get('total', 0) < 10:
        return '数据量不足，继续灰度运行积累样本'

    d_wr = d.get('win_rate', 0)
    e_wr = e.get('win_rate', 0)
    diff = e_wr - d_wr

    if diff > 5:
        return f'experimental胜率高{diff:.1f}%，建议切换为默认规则'
    elif diff < -5:
        return f'experimental胜率低{abs(diff):.1f}%，维持当前default规则'
    else:
        return f'两组差异不显著(差{diff:.1f}%)，继续观察'


def format_compare_markdown(report):
    """A/B对比的企微推送格式"""
    lines = ['## 🧪 A/B规则对照报告', '']
    for name, data in report['profiles'].items():
        label = '🏷️ 生产(default)' if name == 'default' else '🔬 实验(experimental)'
        if data.get('total', 0) == 0:
            lines.append(f'{label}: 暂无数据')
        else:
            lines.append(f"{label}: {data['total']}笔 胜率**{data['win_rate']}%** 均盈{data.get('avg_max_pnl', 0)}%")
    lines.append('')
    lines.append(f"**结论**: {report.get('conclusion', '-')}")
    lines.append(f"\n生成: {report['generated_at']}")
    return '\n'.join(lines)


if __name__ == '__main__':
    ensure_profile_table()
    save_profiles()
    report = compare_profiles()
    print(format_compare_markdown(report))
    print('\n' + json.dumps(report, ensure_ascii=False, indent=2, default=str))
