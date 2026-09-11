# -*- coding: utf-8 -*-
"""stock_data_daily 写入幂等回归测试。"""
import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PIPELINE_PATH = _PROJECT_ROOT / "scripts" / "pipeline_db.py"
sys.path.insert(0, str(_PIPELINE_PATH.parent))
spec = importlib.util.spec_from_file_location("integrity_pipeline_db", _PIPELINE_PATH)
pipeline_db = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pipeline_db
spec.loader.exec_module(pipeline_db)


class FakeDB:
    def __init__(self, fail_insert=False, lock_acquired=True):
        self.calls = []
        self.fail_insert = fail_insert
        self.lock_acquired = lock_acquired
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.records = {}
        self.next_id = 1

    def select_one(self, sql, params=()):
        compact = " ".join(sql.split())
        self.calls.append((compact, params))
        if "GET_LOCK" in compact:
            return 1, {"acquired": 1 if self.lock_acquired else 0}
        if "RELEASE_LOCK" in compact:
            return 1, {"released": 1}
        if compact.startswith("SELECT id FROM stock_data_daily"):
            key = (params[0], params[1])
            row_id = self.records.get(key)
            return (1, {"id": row_id}) if row_id else (0, None)
        raise AssertionError(f"unexpected SELECT: {compact}")

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.calls.append((compact, params))
        if self.fail_insert and compact.startswith("INSERT INTO stock_data_daily"):
            raise RuntimeError("insert failed")
        if compact.startswith("INSERT INTO stock_data_daily"):
            key = (params[1], params[0])
            self.records[key] = self.next_id
            self.next_id += 1
        return 1, self.next_id - 1

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _rows():
    return pd.DataFrame([
        {"日期": "2026-09-10", "开盘": 10, "收盘": 11, "最高": 12, "最低": 9,
         "成交量": 100, "成交额": 1000, "振幅": 3, "涨跌幅": 1, "涨跌额": 0.1, "换手率": 2},
        {"日期": "2026-09-10", "开盘": 20, "收盘": 21, "最高": 22, "最低": 19,
         "成交量": 200, "成交额": 2000, "振幅": 4, "涨跌幅": 2, "涨跌额": 0.2, "换手率": 3},
        {"日期": "2026-09-11", "开盘": 30, "收盘": 31, "最高": 32, "最低": 29,
         "成交量": 300, "成交额": 3000, "振幅": 5, "涨跌幅": 3, "涨跌额": 0.3, "换手率": 4},
    ])


def test_save_kline_deduplicates_input_and_is_idempotent_without_delete(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(pipeline_db, "_get_db", lambda: db)

    assert pipeline_db.save_kline_data("600864", _rows()) == 2
    first_inserts = [c for c in db.calls if c[0].startswith("INSERT INTO stock_data_daily")]
    assert len(first_inserts) == 2
    # 同日输入保留最后一条，不能写入第一条旧值。
    assert first_inserts[0][1][2] == 20.0
    assert len(db.records) == 2

    db.calls.clear()
    assert pipeline_db.save_kline_data("600864", _rows()) == 2
    second_inserts = [c for c in db.calls if c[0].startswith("INSERT INTO stock_data_daily")]
    second_updates = [c for c in db.calls if c[0].startswith("UPDATE stock_data_daily SET")]
    assert not second_inserts
    assert len(second_updates) == 2
    assert len(db.records) == 2

    all_sql = "\n".join(c[0] for c in db.calls)
    assert "DELETE FROM stock_data_daily" not in all_sql
    assert "REPLACE INTO stock_data_daily" not in all_sql
    assert any("GET_LOCK" in c[0] for c in db.calls)
    assert any("RELEASE_LOCK" in c[0] for c in db.calls)
    assert db.committed and not db.rolled_back and db.closed


def test_save_kline_rolls_back_whole_batch_on_insert_error(monkeypatch):
    db = FakeDB(fail_insert=True)
    monkeypatch.setattr(pipeline_db, "_get_db", lambda: db)

    with pytest.raises(RuntimeError, match="insert failed"):
        pipeline_db.save_kline_data("600864", _rows().head(1))

    assert db.rolled_back and not db.committed and db.closed
    assert any("RELEASE_LOCK" in sql for sql, _ in db.calls)


def test_save_kline_updates_latest_existing_id(monkeypatch):
    db = FakeDB()
    db.records[("600864", "2026-09-11")] = 99
    monkeypatch.setattr(pipeline_db, "_get_db", lambda: db)

    assert pipeline_db.save_kline_data("600864", _rows().tail(1)) == 1
    lookup = next(c for c in db.calls if c[0].startswith("SELECT id FROM stock_data_daily"))
    assert "ORDER BY id DESC LIMIT 1" in lookup[0]
    update = next(c for c in db.calls if c[0].startswith("UPDATE stock_data_daily SET"))
    assert update[1][-1] == 99
    assert not any(c[0].startswith("INSERT INTO stock_data_daily") for c in db.calls)


def test_save_kline_aborts_without_writes_when_lock_not_acquired(monkeypatch):
    db = FakeDB(lock_acquired=False)
    monkeypatch.setattr(pipeline_db, "_get_db", lambda: db)

    with pytest.raises(RuntimeError, match="could not acquire kline write lock"):
        pipeline_db.save_kline_data("600864", _rows().head(1))

    assert db.rolled_back and db.closed
    assert not any(c[0].startswith(("INSERT INTO stock_data_daily", "UPDATE stock_data_daily SET"))
                   for c in db.calls)
    assert not any("RELEASE_LOCK" in sql for sql, _ in db.calls)
