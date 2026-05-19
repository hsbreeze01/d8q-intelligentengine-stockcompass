#!/usr/bin/python
# -*- coding: UTF-8 -*-

import datetime
import math

import pandas as pd

from funcat import *
from funcat.utils import *

from stockfetch.db_base import StockDBBase


class BIASDaily(StockDBBase):
    """BIAS daily indicator — inherits StockDBBase for pooled DB access."""

    def __init__(self, code, **db_kwargs):
        super().__init__(**db_kwargs)
        self.code = code

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
        """Return a DataFrame of BIAS indicators up to the last known daily date."""
        last_update = self.db_get_maxdate()
        if last_update is None:
            last_update = datetime.date(2000, 1, 1)

        with self:
            _, rows = self._query_all(
                "SELECT * FROM indicators_bias_daily "
                "WHERE stock_code = %s AND record_time <= %s",
                (self.code, last_update),
            )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def insert(self, BIAS, DATETIME):
        """Batch-insert BIAS indicator values, skipping NaN and > 9999."""
        b1 = BIAS[0]
        b2 = BIAS[1]
        b3 = BIAS[2]

        with self:
            for index in reversed(range(len(DATETIME))):
                try:
                    v1 = b1[index].value
                    v2 = b2[index].value
                    v3 = b3[index].value
                    if math.isnan(v3) or v1 > 9999 or v2 > 9999 or v3 > 9999:
                        continue
                    record_time = get_str_date_from_int(
                        DATETIME[index].value / 1000000
                    )
                    self._execute_many(
                        "REPLACE INTO indicators_bias_daily "
                        "(stock_code, bias_1, bias_2, bias_3, record_time) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (self.code, v1, v2, v3, record_time),
                    )
                except IndexError:
                    pass
