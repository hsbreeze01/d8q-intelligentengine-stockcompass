#!/usr/bin/python
# -*- coding: UTF-8 -*-

import talib
import numpy as np
import tushare as ts
import pandas as pd


talib.OBV

#pro = ts.pro_api()

df=ts.get_k_data('600036')
#df['MA10_rolling'] = pd.rolling_mean(df['close'],10)
df['MA10_rolling'] = pd.Series.rolling(df['close'],10)
close = [float(x) for x in df['close']]
# 调用talib计算10日移动平均线的值
df['MA10_talib'] = talib.MA(np.array(close), timeperiod=10) 
print(df.tail(12))


