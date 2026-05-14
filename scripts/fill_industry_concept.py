#!/usr/bin/env python3
"""
从 mootdx F10 采集 A 股行业分类和概念板块，写入 stock_basic 表。
数据源: 通达信 TCP 7709 — 不可能被 IP 封锁。
频率: 5 秒/只，5512 只 ≈ 7.6 小时。
支持断点续跑（跳过已有 industry 的股票）。
用法:
  python fill_industry_concept.py              # 增量（只采集空记录）
  python fill_industry_concept.py force        # 全量重采
"""

import re
import sys
import time
import signal
import logging
import pymysql
from mootdx.quotes import Quotes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = "password"
DB_NAME = "stock_analysis_system"

INTERVAL = 5
BATCH_COMMIT = 50

client = None
conn = None
shutdown = False


def handle_signal(sig, frame):
    global shutdown
    log.info("收到停止信号，等待当前任务完成后退出...")
    shutdown = True


def get_db():
    return pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME,
        charset="utf8mb4", autocommit=False,
    )


def get_tdx_client():
    return Quotes.factory(market="std")


def parse_industry(text):
    if not text:
        return ""
    m = re.search(r"行业类别\s*｜\s*([^｜]+?)\s*｜", text)
    return m.group(1).strip() if m else ""


def parse_concepts(text):
    if not text:
        return []
    lines = text.split("\n")
    concept_start = -1
    for i, line in enumerate(lines):
        if line.strip() == "【3.概念板块】":
            concept_start = i
            break
    if concept_start < 0:
        return []

    concepts = []
    for j in range(concept_start + 1, len(lines)):
        line = lines[j].strip()
        if line.startswith("【4.") or "免责声明" in line:
            break
        if not line.startswith("｜"):
            continue
        parts = line.split("｜")
        first_cell = parts[1].strip() if len(parts) > 1 else ""
        if not first_cell or first_cell == "概念名称":
            continue
        concepts.append(first_cell)
    return concepts


def fetch_one(code, tdx):
    text1 = tdx.F10(symbol=code, name="公司概况")
    industry = parse_industry(text1)

    text2 = tdx.F10(symbol=code, name="最新提示")
    concepts = parse_concepts(text2)

    return industry, concepts


def main():
    global client, conn, shutdown

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    mode = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    force = mode == "force"

    log.info("初始化 mootdx 客户端...")
    client = get_tdx_client()
    conn = get_db()
    cur = conn.cursor()

    if force:
        cur.execute("SELECT code FROM stock_basic ORDER BY code")
        codes = [row[0] for row in cur.fetchall()]
        log.info(f"强制模式：重新采集全部 {len(codes)} 只股票")
    else:
        cur.execute(
            "SELECT code FROM stock_basic "
            "WHERE (industry IS NULL OR industry = '' OR concept IS NULL OR concept = '') "
            "ORDER BY code"
        )
        codes = [row[0] for row in cur.fetchall()]
        log.info(f"增量模式：需采集 {len(codes)} 只股票")

    if not codes:
        log.info("无需采集，退出")
        return

    success = 0
    fail = 0
    skipped = 0
    batch_count = 0
    t0 = time.time()

    for i, code in enumerate(codes):
        if shutdown:
            log.info("用户停止，提交已采集数据后退出")
            break

        try:
            industry, concepts = fetch_one(code, client)

            if not industry and not concepts:
                skipped += 1
                if (i + 1) % 100 == 0:
                    elapsed = time.time() - t0
                    eta = elapsed / max(i + 1, 1) * (len(codes) - i - 1)
                    log.info(
                        f"[{i+1}/{len(codes)}] {code}: 无数据 "
                        f"成功={success} 跳过={skipped} "
                        f"ETA={eta/60:.0f}min"
                    )
                time.sleep(INTERVAL)
                continue

            concept_str = ",".join(concepts)
            # Only update fields that have new data (don't overwrite existing)
            updates = []
            params = []
            if industry:
                updates.append("industry=%s")
                params.append(industry)
            if concept_str:
                updates.append("concept=%s")
                params.append(concept_str)
            if updates:
                sql = "UPDATE stock_basic SET " + ", ".join(updates) + " WHERE code=%s"
                params.append(code)
                cur.execute(sql, params)
            batch_count += 1
            success += 1

            if batch_count >= BATCH_COMMIT:
                conn.commit()
                batch_count = 0

            if (i + 1) % 50 == 0 or success <= 5:
                elapsed = time.time() - t0
                eta = elapsed / max(i + 1, 1) * (len(codes) - i - 1)
                ind_short = industry[:25] if industry else "(空)"
                log.info(
                    f"[{i+1}/{len(codes)}] {code}: "
                    f"industry=[{ind_short}] concepts={len(concepts)} "
                    f"成功={success} 失败={fail} 跳过={skipped} "
                    f"ETA={eta/60:.0f}min"
                )

        except Exception as e:
            fail += 1
            log.warning(f"[{i+1}/{len(codes)}] {code}: {type(e).__name__}: {str(e)[:80]}")
            if batch_count > 0:
                conn.commit()
                batch_count = 0
            time.sleep(2)
            try:
                client = get_tdx_client()
            except Exception:
                pass
            continue

        time.sleep(INTERVAL)

    if batch_count > 0:
        conn.commit()

    elapsed = time.time() - t0
    cur.execute("SELECT COUNT(*) FROM stock_basic WHERE industry IS NOT NULL AND industry != ''")
    filled = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM stock_basic")
    total = cur.fetchone()[0]
    log.info(
        f"完成: 成功={success} 失败={fail} 跳过={skipped} "
        f"耗时={elapsed/60:.1f}min "
        f"数据库={filled}/{total} ({filled/total*100:.1f}%)"
    )
    conn.close()


if __name__ == "__main__":
    main()
