#!/usr/bin/python
# -*- coding: UTF-8 -*-

import datetime
import math

import pandas as pd

from funcat import DATETIME as _DATETIME  # noqa: F401 – side-effect init required
from funcat.utils import get_str_date_from_int

from stockfetch.db_base import StockDBBase


class VRDaily(StockDBBase):
    """VR daily indicator — inherits StockDBBase for pooled DB access."""

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
        """Return a DataFrame of VR indicators up to the last known daily date."""
        last_update = self.db_get_maxdate()
        if last_update is None:
            last_update = datetime.date(2000, 1, 1)

        with self:
            _, rows = self._query_all(
                "SELECT * FROM indicators_vr_daily "
                "WHERE stock_code = %s AND record_time <= %s",
                (self.code, last_update),
            )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def insert(self, VR, DATETIME):
        """Batch-insert VR indicator values, skipping NaN.

        Preserves the hard-coded av=100, bv=200 defaults from the original.
        """
        k = VR
        av = 100
        bv = 200

        with self:
            for index in reversed(range(len(DATETIME))):
                try:
                    v = k[index].value
                    if math.isnan(v):
                        continue
                    record_time = get_str_date_from_int(
                        DATETIME[index].value / 1000000
                    )
                    self._execute_many(
                        "REPLACE INTO indicators_vr_daily "
                        "(stock_code, vr_1, a_v, b_v, record_time) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (self.code, v, av, bv, record_time),
                    )
                except IndexError:
                    pass
