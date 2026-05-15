"""测试 init_tables 韧性化 + 聚合器 LLM 超时保护"""
from unittest.mock import MagicMock, call, patch

import pytest


# ============================================================================
# Test: init_tables 韧性 — 单表失败不中断
# ============================================================================

class TestInitTablesResilience:
    """init_tables 遇到单张表失败时继续创建后续表"""

    @patch("compass.strategy.db.Database")
    def test_single_failure_continues(self, MockDB):
        """signal_snapshot 失败后，group_event 和 trend_tracking 仍被创建"""
        from compass.strategy.db import _TABLES, init_tables

        mock_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        # 让 signal_snapshot 的 execute 抛异常
        call_count = {"n": 0}

        def fake_execute(sql):
            call_count["n"] += 1
            if "signal_snapshot" in sql:
                raise RuntimeError("DDL 临时错误")

        mock_conn.execute = fake_execute
        mock_conn.commit = MagicMock()

        # 不应抛异常
        init_tables()

        # 应该遍历所有表
        assert call_count["n"] == len(_TABLES)

    @patch("compass.strategy.db.Database")
    def test_all_tables_succeed(self, MockDB):
        """所有表创建成功，无 ERROR 日志"""
        from compass.strategy.db import _TABLES, init_tables

        mock_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        mock_conn.execute = MagicMock()
        mock_conn.commit = MagicMock()

        # Mock 迁移检查返回 None
        mock_conn.select_one.return_value = (0, None)

        init_tables()

        # 每张表都执行了一次 DDL
        assert mock_conn.execute.call_count >= len(_TABLES)

    @patch("compass.strategy.db.Database")
    def test_all_tables_fail_no_exception(self, MockDB):
        """所有表都失败时，init_tables 仍正常返回"""
        from compass.strategy.db import init_tables

        mock_conn = MagicMock()
        MockDB.return_value.__enter__ = MagicMock(return_value=mock_conn)
        MockDB.return_value.__exit__ = MagicMock(return_value=False)

        mock_conn.execute = MagicMock(side_effect=RuntimeError("权限不足"))
        mock_conn.commit = MagicMock()

        # 不应抛异常
        init_tables()


# ============================================================================
# Test: Aggregator LLM 超时保护
# ============================================================================

class TestLLMTimeout:
    """聚合器 _trigger_llm_analysis 超时保护"""

    def test_llm_timeout_skips_event(self):
        """LLM 分析超时时跳过，记录 WARNING"""
        import concurrent.futures
        from compass.strategy.services.aggregator import Aggregator

        agg = Aggregator()

        with patch(
            "compass.strategy.services.aggregator.concurrent.futures.ThreadPoolExecutor"
        ) as MockPool:
            mock_future = MagicMock()
            mock_future.result.side_effect = concurrent.futures.TimeoutError()

            mock_executor = MagicMock()
            mock_executor.__enter__ = MagicMock(return_value=mock_executor)
            mock_executor.__exit__ = MagicMock(return_value=False)
            mock_executor.submit.return_value = mock_future
            MockPool.return_value = mock_executor

            # 不应抛异常
            agg._trigger_llm_analysis(42)

            # submit 被调用
            mock_executor.submit.assert_called_once()

    def test_llm_connection_error_skips_event(self):
        """LLM 连接失败时跳过，记录 WARNING"""
        from compass.strategy.services.aggregator import Aggregator

        agg = Aggregator()

        with patch(
            "compass.strategy.services.aggregator.concurrent.futures.ThreadPoolExecutor"
        ) as MockPool:
            mock_future = MagicMock()
            mock_future.result.side_effect = ConnectionError("Doubao 不可用")

            mock_executor = MagicMock()
            mock_executor.__enter__ = MagicMock(return_value=mock_executor)
            mock_executor.__exit__ = MagicMock(return_value=False)
            mock_executor.submit.return_value = mock_future
            MockPool.return_value = mock_executor

            # 不应抛异常
            agg._trigger_llm_analysis(99)

            mock_executor.submit.assert_called_once()

    def test_llm_success_normal(self):
        """LLM 正常完成时，结果正常返回"""
        from compass.strategy.services.aggregator import Aggregator

        agg = Aggregator()

        with patch(
            "compass.strategy.services.aggregator.concurrent.futures.ThreadPoolExecutor"
        ) as MockPool:
            mock_future = MagicMock()
            mock_future.result.return_value = {"event_id": 42, "structured": {}}

            mock_executor = MagicMock()
            mock_executor.__enter__ = MagicMock(return_value=mock_executor)
            mock_executor.__exit__ = MagicMock(return_value=False)
            mock_executor.submit.return_value = mock_future
            MockPool.return_value = mock_executor

            agg._trigger_llm_analysis(42)

            mock_future.result.assert_called_once()
