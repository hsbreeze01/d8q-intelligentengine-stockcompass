#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热点采集可执行入口
用法:
    python run.py --all       运行所有采集+趋势计算
    python run.py --weibo     只采微博+百度热搜
    python run.py --policy    只采政策源
    python run.py --concept   只采概念板块
    python run.py --trend     只计算趋势(不采集)
"""
import argparse
import sys
import time
import traceback
from datetime import datetime

from collector import WeiboCrawler, BaiduCrawler, EastMoneyCrawler, PolicyCrawler
from finance_filter import filter_items
from storage import save_hot_events, save_concept_boards, save_collect_log
from lifecycle import compute_heat_trends


def run_crawler(crawler_cls, name: str) -> dict:
    """运行单个采集器并存储结果"""
    print(f"\n{'='*60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始采集: {name}")
    print(f"{'='*60}")

    start = time.time()
    try:
        crawler = crawler_cls()
        items = crawler.fetch()
        duration_ms = int((time.time() - start) * 1000)

        print(f"  原始采集: {len(items)} 条")

        # 关键词过滤和分类
        items = filter_items(items)
        finance_count = sum(1 for i in items if i.get('is_finance_related'))
        print(f"  金融相关: {finance_count} 条")

        # 写入数据库
        hot_rows = save_hot_events(items)
        print(f"  写入t_hot_event: {hot_rows} 行")

        # 概念板块单独写入
        concept_rows = 0
        if name == 'eastmoney_concept':
            concept_rows = save_concept_boards(items)
            print(f"  写入t_concept_board_daily: {concept_rows} 行")

        # 记录采集日志
        save_collect_log(
            source=name,
            status='success',
            items_count=len(items),
            duration_ms=duration_ms,
        )

        print(f"  耗时: {duration_ms}ms ✓")
        return {'status': 'success', 'count': len(items), 'finance': finance_count, 'duration_ms': duration_ms}

    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        error_msg = str(e)
        print(f"  ✗ 采集失败: {error_msg}")
        traceback.print_exc()

        save_collect_log(
            source=name,
            status='failed',
            items_count=0,
            error_msg=error_msg[:500],
            duration_ms=duration_ms,
        )
        return {'status': 'failed', 'error': error_msg, 'duration_ms': duration_ms}


def main():
    parser = argparse.ArgumentParser(description='热点信息采集系统')
    parser.add_argument('--all', action='store_true', help='运行所有采集+趋势计算')
    parser.add_argument('--weibo', action='store_true', help='只采微博+百度热搜')
    parser.add_argument('--policy', action='store_true', help='只采政策源')
    parser.add_argument('--concept', action='store_true', help='只采概念板块')
    parser.add_argument('--trend', action='store_true', help='只计算趋势(不采集)')
    args = parser.parse_args()

    # 如果没有指定任何参数，显示帮助
    if not any([args.all, args.weibo, args.policy, args.concept, args.trend]):
        parser.print_help()
        sys.exit(1)

    print(f"\n{'#'*60}")
    print(f"# 热点采集系统 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    results = {}
    total_start = time.time()

    # 微博+百度
    if args.all or args.weibo:
        results['weibo'] = run_crawler(WeiboCrawler, 'weibo')
        results['baidu'] = run_crawler(BaiduCrawler, 'baidu')

    # 概念板块
    if args.all or args.concept:
        results['eastmoney_concept'] = run_crawler(EastMoneyCrawler, 'eastmoney_concept')

    # 政策
    if args.all or args.policy:
        results['policy'] = run_crawler(PolicyCrawler, 'policy')

    # 趋势计算
    if args.all or args.trend:
        print(f"\n{'='*60}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 计算热度趋势...")
        print(f"{'='*60}")
        try:
            stats = compute_heat_trends()
            print(f"  分析话题: {stats['topics_analyzed']} 个")
            print(f"  写入趋势: {stats['inserted']} 条 ✓")
            results['trend'] = {'status': 'success', **stats}
        except Exception as e:
            print(f"  ✗ 趋势计算失败: {e}")
            traceback.print_exc()
            results['trend'] = {'status': 'failed', 'error': str(e)}

    # 汇总
    total_duration = int((time.time() - total_start) * 1000)
    print(f"\n{'#'*60}")
    print(f"# 采集汇总 (总耗时: {total_duration}ms)")
    print(f"{'#'*60}")
    for name, result in results.items():
        status = result.get('status', 'unknown')
        if status == 'success':
            count = result.get('count', result.get('inserted', 0))
            print(f"  ✓ {name:25s} | {count:4d} 条 | {result.get('duration_ms', 0)}ms")
        else:
            print(f"  ✗ {name:25s} | FAILED: {result.get('error', 'unknown')[:50]}")

    # 返回状态码
    failed = [k for k, v in results.items() if v.get('status') != 'success']
    if failed:
        print(f"\n⚠ 部分采集失败: {', '.join(failed)}")
        sys.exit(2)
    else:
        print(f"\n✓ 全部采集成功!")
        sys.exit(0)


if __name__ == '__main__':
    main()
