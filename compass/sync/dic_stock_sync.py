"""dic_stock 同步模块 — 通过 akshare 获取 A 股实时行情并批量 UPSERT 到 MySQL。

支持两种调用方式：
1. 模块函数: from compass.sync.dic_stock_sync import sync_dic_stock
2. CLI: python -m compass.sync.dic_stock_sync
"""
import logging
import time

import akshare as ak
import pandas as pd

from compass.data.database import Database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 字段映射：akshare Sina 列名 → dic_stock 表列名
# ---------------------------------------------------------------------------
_FIELD_MAP = {
    "代码": "code",
    "名称": "stock_name",
    "最新价": "latest_price",
    "涨跌幅": "change_percentage",
    "涨跌额": "change_amount",
    "成交量": "volume",
    "成交额": "turnover",
    "振幅": "amplitude",
    "最高": "highest",
    "最低": "lowest",
    "今开": "open_today",
    "昨收": "close_yesterday",
    "换手率": "turnover_rate",
    "市盈率-动态": "pe_ratio_dynamic",
    "市净率": "pb_ratio",
    "总市值": "total_market_value",
    "流通市值": "circulating_market_value",
}

# UPSERT 涉及的 dic_stock 列（固定值 status 不在 map 中，单独处理）
_UPSERT_COLUMNS = [
    "code", "stock_name", "latest_price", "change_percentage",
    "change_amount", "volume", "turnover", "amplitude", "highest",
    "lowest", "open_today", "close_yesterday", "turnover_rate",
    "pe_ratio_dynamic", "pb_ratio", "total_market_value",
    "circulating_market_value", "status",
]

_BATCH_SIZE = 500


def _fetch_stock_list() -> pd.DataFrame:
    """获取 A 股股票列表（代码 + 名称）。"""
    logger.info("Fetching A-share stock list via akshare...")
    df = ak.stock_info_a_code_name()
    logger.info("Got %d stocks from stock_info_a_code_name()", len(df))
    return df


def _fetch_spot_data() -> pd.DataFrame:
    """获取 A 股实时行情数据（Sina 数据源）。"""
    logger.info("Fetching A-share spot data via akshare...")
    df = ak.stock_zh_a_spot()
    logger.info("Got %d rows from stock_zh_a_spot()", len(df))
    return df


def _map_dataframe(df: pd.DataFrame) -> list[dict]:
    """将 akshare DataFrame 映射为 dic_stock 记录列表。

    缺失字段自动映射为 None，不会因字段缺失而跳过股票。
    """
    records = []
    for _, row in df.iterrows():
        record = {}
        for ak_col, db_col in _FIELD_MAP.items():
            value = row.get(ak_col)
            # pandas NaN check: use pd.isna for robustness
            if value is None or (isinstance(value, float) and value != value):
                record[db_col] = None
            else:
                record[db_col] = value
        # status 固定值 0（活跃）
        record["status"] = 0
        # 确保 code 不为空
        if record.get("code"):
            records.append(record)
    return records


def _build_upsert_sql() -> str:
    """构建 INSERT ... ON DUPLICATE KEY UPDATE 语句模板。"""
    cols = ", ".join(_UPSERT_COLUMNS)
    placeholders = ", ".join(["%s"] * len(_UPSERT_COLUMNS))
    # ON DUPLICATE KEY UPDATE 需更新除 code 以外的所有字段
    update_cols = [c for c in _UPSERT_COLUMNS if c != "code"]
    update_clause = ", ".join(f"{c} = VALUES({c})" for c in update_cols)
    return (
        f"INSERT INTO dic_stock ({cols}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {update_clause}"
    )


def _batch_upsert(records: list[dict]) -> int:
    """批量 UPSERT 写入 dic_stock，返回成功写入数。"""
    if not records:
        return 0

    sql = _build_upsert_sql()
    total_batches = (len(records) + _BATCH_SIZE - 1) // _BATCH_SIZE
    synced = 0

    for i in range(0, len(records), _BATCH_SIZE):
        batch = records[i: i + _BATCH_SIZE]
        batch_num = i // _BATCH_SIZE + 1
        logger.info("Syncing batch %d/%d (%d stocks)...", batch_num, total_batches, len(batch))

        try:
            params_list = []
            for r in batch:
                params_list.append(tuple(r.get(c) for c in _UPSERT_COLUMNS))

            with Database() as db:
                for params in params_list:
                    db.execute(sql, params)
                synced += len(batch)
        except Exception as e:
            logger.error("Batch %d/%d failed: %s", batch_num, total_batches, e)

    return synced


def sync_dic_stock() -> dict:
    """执行 dic_stock 全量同步。

    Returns
    -------
    dict
        同步摘要：{
            "total": 总处理数,
            "synced": 成功写入数,
            "failed": 失败数,
            "duration_seconds": 耗时,
            "source": "akshare-sina"
        }
    """
    start = time.time()

    # Step 1: 获取股票列表（验证 akshare 可用性）
    try:
        stock_list = _fetch_stock_list()
    except Exception as e:
        logger.error("Failed to fetch stock list: %s", e)
        return {
            "total": 0,
            "synced": 0,
            "failed": 0,
            "duration_seconds": round(time.time() - start, 2),
            "source": "akshare-sina",
        }

    # Step 2: 获取实时行情（速率控制：与上次调用间隔至少 1 秒）
    time.sleep(1)
    try:
        spot_df = _fetch_spot_data()
    except Exception as e:
        logger.error("Failed to fetch spot data: %s", e)
        return {
            "total": 0,
            "synced": 0,
            "failed": 0,
            "duration_seconds": round(time.time() - start, 2),
            "source": "akshare-sina",
        }

    # Step 3: 字段映射
    records = _map_dataframe(spot_df)
    total = len(records)

    # Step 4: 批量 UPSERT
    synced = _batch_upsert(records)
    failed = total - synced

    duration = round(time.time() - start, 2)
    logger.info("Synced %d stocks in %ss", synced, duration)

    return {
        "total": total,
        "synced": synced,
        "failed": failed,
        "duration_seconds": duration,
        "source": "akshare-sina",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = sync_dic_stock()
    print(f"Sync result: {result}")
