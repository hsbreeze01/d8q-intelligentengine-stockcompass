#! /usr/bin/python
# -*- coding: utf-8 -*-

import numpy as np

import tushare as ts

from funcat import *

def test_000001():
    from funcat.data.tushare_backend import TushareDataBackend
    set_data_backend(TushareDataBackend())

    T("20161216")
    S("000001.XSHG")

    assert np.equal(round(CLOSE.value, 2), 3122.98)
    assert np.equal(round(OPEN[2].value, 2), 3149.38)
    assert np.equal(round((CLOSE - OPEN).value, 2), 11.47)
    assert np.equal(round((CLOSE - OPEN)[2].value, 2), -8.85)
    assert np.equal(round(((CLOSE / CLOSE[1] - 1) * 100).value, 2), 0.17)
    assert np.equal(round(MA(CLOSE, 60)[2].value, 2), 3131.08)
    assert np.equal(round(MACD()[0].value, 2), -37.18)
    assert np.equal(round(HHV(HIGH, 5).value, 2), 3245.09)
    assert np.equal(round(LLV(LOW, 5).value, 2), 3100.91)
    assert COUNT(CLOSE > OPEN, 5) == 2
    print("end test_000001")

# test_000001()

# ts.set_token("7a689f4bfe301b0aafb619edd9858d44db3722fc7d0c47725ec0056c")
# pro = ts.pro_api()
# #设置你的token
# df = pro.user(token='7a689f4bfe301b0aafb619edd9858d44db3722fc7d0c47725ec0056c')
# print(df)

# data = ts.get_hist_data('600036')
# print(data)

from buy.cache import *

dicStock = DicStockFactory()
print(dicStock.isExist("6000361"))