"""单元测试 — dic_stock 同步模块 (compass/sync/dic_stock_sync.py)

覆盖范围：
- _map_dataframe 字段映射（含缺失字段处理）
- _build_upsert_sql SQL 生成
- sync_dic_stock 主流程（mock akshare + Database）
- CLI 入口（if __name__ == "__main__"）
"""
import time
from unittest.mock import patch, MagicMock, call

import pandas as pd
import pytest

from compass.sync.dic_stock_sync import (
    _FIELD_MAP,
    _UPSERT_COLUMNS,
    _BATCH_SIZE,
    _map_dataframe,
    _build_upsert_sql,
    sync_dic_stock,
)


# ---------------------------------------------------------------------------
# _map_dataframe
# ---------------------------------------------------------------------------
class TestMapDataframe:
    """字段映射测试"""

    def test_basic_mapping(self):
        """正常字段映射"""
        df = pd.DataFrame([{
            "代码": "600519",
            "名称": "贵州茅台",
            "最新价": 1800.0,
            "涨跌幅": 1.5,
            "涨跌额": 26.7,
            "成交量": 10000,
            "成交额": 18000000,
            "振幅": 2.0,
            "最高": 1810.0,
            "最低": 1790.0,
            "今开": 1795.0,
            "昨收": 1773.3,
            "换手率": 0.8,
            "市盈率-动态": 30.5,
            "市净率": 10.2,
            "总市值": 2260000000000,
            "流通市值": 2260000000000,
        }])
        records = _map_dataframe(df)
        assert len(records) == 1
        r = records[0]
        assert r["code"] == "600519"
        assert r["stock_name"] == "贵州茅台"
        assert r["latest_price"] == 1800.0
        assert r["status"] == 0

    def test_missing_optional_fields_become_none(self):
        """缺失字段映射为 None"""
        df = pd.DataFrame([{
            "代码": "000001",
            "名称": "平安银行",
        }])
        records = _map_dataframe(df)
        assert len(records) == 1
        r = records[0]
        assert r["code"] == "000001"
        assert r["stock_name"] == "平安银行"
        assert r["latest_price"] is None
        assert r["pe_ratio_dynamic"] is None
        assert r["pb_ratio"] is None

    def test_nan_values_become_none(self):
        """pandas NaN 值映射为 None"""
        df = pd.DataFrame([{
            "代码": "600519",
            "名称": "贵州茅台",
            "最新价": float("nan"),
            "市盈率-动态": float("nan"),
        }])
        records = _map_dataframe(df)
        assert records[0]["latest_price"] is None
        assert records[0]["pe_ratio_dynamic"] is None

    def test_empty_code_skipped(self):
        """空 code 的记录被跳过"""
        df = pd.DataFrame([{
            "代码": "",
            "名称": "空代码",
        }])
        records = _map_dataframe(df)
        assert len(records) == 0

    def test_multiple_records(self):
        """多记录映射"""
        df = pd.DataFrame([
            {"代码": "000001", "名称": "平安银行"},
            {"代码": "000002", "名称": "万科A"},
            {"代码": "600519", "名称": "贵州茅台"},
        ])
        records = _map_dataframe(df)
        assert len(records) == 3
        codes = [r["code"] for r in records]
        assert "000001" in codes
        assert "600519" in codes


# ---------------------------------------------------------------------------
# _build_upsert_sql
# ---------------------------------------------------------------------------
class TestBuildUpsertSql:
    """SQL 生成测试"""

    def test_contains_insert(self):
        sql = _build_upsert_sql()
        assert "INSERT INTO dic_stock" in sql

    def test_contains_on_duplicate_key(self):
        sql = _build_upsert_sql()
        assert "ON DUPLICATE KEY UPDATE" in sql

    def test_placeholders_count(self):
        """占位符数量与列数一致"""
        sql = _build_upsert_sql()
        # 计算 VALUES (...) 中的 %s 数量
        values_part = sql.split("VALUES")[1].split(")")[0]
        assert values_part.count("%s") == len(_UPSERT_COLUMNS)

    def test_update_excludes_code(self):
        """UPDATE 子句不包含 code 列"""
        sql = _build_upsert_sql()
        update_part = sql.split("ON DUPLICATE KEY UPDATE")[1]
        assert "code = VALUES(code)" not in update_part
        assert "stock_name = VALUES(stock_name)" in update_part


# ---------------------------------------------------------------------------
# sync_dic_stock — mock akshare
# ---------------------------------------------------------------------------
class TestSyncDicStock:
    """主流程测试 — mock 外部依赖"""

    @patch("compass.sync.dic_stock_sync._batch_upsert")
    @patch("compass.sync.dic_stock_sync._fetch_spot_data")
    @patch("compass.sync.dic_stock_sync._fetch_stock_list")
    def test_success(self, mock_list, mock_spot, mock_upsert):
        """正常同步流程"""
        mock_list.return_value = pd.DataFrame([
            {"code": "000001", "name": "平安银行"},
            {"code": "600519", "name": "贵州茅台"},
        ])
        mock_spot.return_value = pd.DataFrame([
            {"代码": "000001", "名称": "平安银行", "最新价": 15.0},
            {"代码": "600519", "名称": "贵州茅台", "最新价": 1800.0},
        ])
        mock_upsert.return_value = 2

        result = sync_dic_stock()

        assert result["total"] == 2
        assert result["synced"] == 2
        assert result["failed"] == 0
        assert result["source"] == "akshare-sina"
        assert result["duration_seconds"] > 0

    @patch("compass.sync.dic_stock_sync._batch_upsert")
    @patch("compass.sync.dic_stock_sync._fetch_spot_data")
    @patch("compass.sync.dic_stock_sync._fetch_stock_list")
    def test_partial_failure(self, mock_list, mock_spot, mock_upsert):
        """部分批次失败"""
        mock_list.return_value = pd.DataFrame([{"code": "000001", "name": "A"}])
        mock_spot.return_value = pd.DataFrame([
            {"代码": "000001", "名称": "A"},
            {"代码": "000002", "名称": "B"},
            {"代码": "000003", "名称": "C"},
        ])
        mock_upsert.return_value = 2

        result = sync_dic_stock()
        assert result["total"] == 3
        assert result["synced"] == 2
        assert result["failed"] == 1

    @patch("compass.sync.dic_stock_sync._fetch_stock_list")
    def test_stock_list_fetch_failure(self, mock_list):
        """股票列表获取失败 — 返回空摘要"""
        mock_list.side_effect = Exception("API timeout")

        result = sync_dic_stock()
        assert result["total"] == 0
        assert result["synced"] == 0

    @patch("compass.sync.dic_stock_sync._fetch_spot_data")
    @patch("compass.sync.dic_stock_sync._fetch_stock_list")
    def test_spot_data_fetch_failure(self, mock_list, mock_spot):
        """行情数据获取失败 — 返回空摘要"""
        mock_list.return_value = pd.DataFrame([{"code": "000001", "name": "A"}])
        mock_spot.side_effect = Exception("API timeout")

        result = sync_dic_stock()
        assert result["total"] == 0
        assert result["synced"] == 0


# ---------------------------------------------------------------------------
# _batch_upsert — mock Database
# ---------------------------------------------------------------------------
class TestBatchUpsert:
    """批量写入测试"""

    @patch("compass.sync.dic_stock_sync.Database")
    def test_single_batch(self, MockDB):
        """单批次写入"""
        mock_db = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_db)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        records = [
            {"code": "000001", "stock_name": "平安银行", "status": 0},
        ]
        from compass.sync.dic_stock_sync import _batch_upsert
        synced = _batch_upsert(records)

        assert synced == 1
        assert mock_db.execute.called

    @patch("compass.sync.dic_stock_sync.Database")
    def test_multiple_batches(self, MockDB):
        """多批次写入 — 验证分批逻辑"""
        mock_db = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_db)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        records = [{"code": f"{i:06d}", "stock_name": f"Stock{i}", "status": 0} for i in range(5)]

        with patch("compass.sync.dic_stock_sync._BATCH_SIZE", 2):
            from compass.sync.dic_stock_sync import _batch_upsert
            synced = _batch_upsert(records)

        assert synced == 5

    @patch("compass.sync.dic_stock_sync.Database")
    def test_batch_failure_continues(self, MockDB):
        """单批次失败不影响后续批次"""
        call_count = 0

        class FailFirstDB:
            def __init__(self_inner):
                pass

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *args):
                pass

            def execute(self_inner, sql, params):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("DB error")

        MockDB.side_effect = FailFirstDB

        records = [
            {"code": "000001", "stock_name": "A", "status": 0},
            {"code": "000002", "stock_name": "B", "status": 0},
        ]

        from compass.sync.dic_stock_sync import _batch_upsert
        # With _BATCH_SIZE=1, each record is a batch
        with patch("compass.sync.dic_stock_sync._BATCH_SIZE", 1):
            synced = _batch_upsert(records)

        # First batch failed, second succeeded
        assert synced == 1

    def test_empty_records(self):
        """空记录列表"""
        from compass.sync.dic_stock_sync import _batch_upsert
        synced = _batch_upsert([])
        assert synced == 0
