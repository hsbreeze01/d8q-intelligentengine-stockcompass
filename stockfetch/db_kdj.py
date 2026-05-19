#!/usr/bin/python
# -*- coding: UTF-8 -*-

import datetime
import math

import pandas as pd

from funcat import DATETIME as _DATETIME  # noqa: F401 – side-effect init required
from funcat.utils import get_str_date_from_int

from stockfetch.db_base import StockDBBase


class KDJDaily(StockDBBase):
    """KDJ daily indicator — inherits StockDBBase for pooled DB access.

    The ``param`` attribute selects the target table:
    - ``"522"`` → ``indicators_kdj_daily_522``
    - otherwise  → ``indicators_kdj_daily``
    """

    def __init__(self, code, param="933", **db_kwargs):
        super().__init__(**db_kwargs)
        self.code = code
        self.param = param

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _table_name(self):
        """Return the target table based on ``self.param``."""
        if self.param == "522":
            return "indicators_kdj_daily_522"
        return "indicators_kdj_daily"

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def db_get_maxdate(self):
        """Return max(date) from stock_data_daily for the current stock code."""
        with self:
            _, row = self._query_one(
                "SELECT max(date) FROM stock_data_daily WHERE stock_code = %s",
                (self.code,),
            )
        if row is None:
            return None
        return row.get("max(date)")

    def getData(self):
        """Return a DataFrame of KDJ indicators up to the last known daily date."""
        last_update = self.db_get_maxdate()
        if last_update is None:
            last_update = datetime.date(2000, 1, 1)

        table = self._table_name()
        with self:
            _, rows = self._query_all(
                f"SELECT * FROM {table} "
                "WHERE stock_code = %s AND record_time <= %s",
                (self.code, last_update),
            )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def insert(self, KDJ, DATETIME):
        """Batch-insert KDJ indicator values, skipping NaN on j."""
        k = KDJ[0]
        d = KDJ[1]
        j = KDJ[2]

        table = self._table_name()
        with self:
            for index in reversed(range(len(DATETIME))):
                try:
                    v_j = j[index].value
                    if math.isnan(v_j):
                        continue
                    v_k = k[index].value
                    v_d = d[index].value
                    record_time = get_str_date_from_int(
                        DATETIME[index].value / 1000000
                    )
                    self._execute_many(
                        f"REPLACE INTO {table} "
                        "(stock_code, k, d, j, record_time) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (self.code, v_k, v_d, v_j, record_time),
                    )
                except IndexError:
                    pass
