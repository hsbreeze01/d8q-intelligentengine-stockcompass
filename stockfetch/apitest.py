#!/usr/bin/python
# -*- coding: UTF-8 -*-

import tushare as ts


pro = ts.pro_api("7a689f4bfe301b0aafb619edd9858d44db3722fc7d0c47725ec0056c")

df = pro.daily(ts_code='000001.SZ', start_date='20170812', 
                 end_date='20200208')
print(df)

print("==============")
# 股票列表
data = pro.query('stock_basic', exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
print(data)

