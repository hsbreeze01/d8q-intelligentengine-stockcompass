#!/usr/bin/python
# -*- coding: UTF-8 -*-

import pymysql #使用的是PostgreSQL数据库
import tushare as ts
import os
import sys

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
path = os.path.split(rootPath)[0]
print(curPath,rootPath,path)

sys.path.append(path) # 这句是为了导入_config
sys.path.append(rootPath)


from dic_stock import *
from stock_data_daily import *
from db_kdj import * 

import datetime
import sys
import time

from funcat import *
from funcat.utils import *
import talib
import math
from stockfetch.db_kdj import *
from stockfetch.db_asi import *
from stockfetch.db_bias import *
from stockfetch.db_boll import *
from stockfetch.db_macd import *
from stockfetch.db_rsi import *
from stockfetch.db_vr import *
from stockfetch.db_wr import *



def fetchAll():
    
    stocks=DicStocks("gamer","123456")

    #如果需要更新股票列表打开下面注释
    stocks.db_stocks_update()#根据todayall的情况更新stocks表

    #hdata.db_hdata_date_create()

    nowdate = datetime.datetime.now().date()
    #所有本地股票代码列表
    codes = stocks.get_codestock_local()

    for record in codes:
        print(record[0],record[1],record)
        if(record[0] < 746):
            continue
        hdata = StockDataDaily(record[1])
        hdata.fetchData()
        time.sleep(1)
        pass

    return

#更新所有数据
# fetchAll()


def test():
    kdj = KDJDaily("600036")
    pd = kdj.getData()
    print(pd,type(pd),pd.at[1,'k'],pd.iat[1,0],len(pd))

    ##
    



test()





# hist_data = ts.get_hist_data("600036", str(maxdate+datetime.timedelta(1)),str(nowdate), 'D', 3, 0.001)
# print(hist_data)
# df = ts.get_k_data("600036", start=str(maxdate+datetime.timedelta(1)), end=str(nowdate), index=False, ktype='D')
# print(df)




# hdata.db_connect()#由于每次连接数据库都要耗时0.0几秒，故获取历史数据时统一连接
# for i in range(0,len(codestock_local)):
#     nowcode=codestock_local[i][0]

#     #print(hdata.get_all_hdata_of_stock(nowcode))

#     print(i,nowcode,codestock_local[i][1])

#     maxdate=hdata.db_get_maxdate_of_stock(nowcode)
#     print(maxdate, nowdate)
#     if(maxdate):
#         if(maxdate>=nowdate):#maxdate小的时候说明还有最新的数据没放进去
#             continue
#         hist_data=ts.get_hist_data(nowcode, str(maxdate+datetime.timedelta(1)),str(nowdate), 'D', 3, 0.001)
#         hdata.insert_perstock_hdatadate(nowcode, hist_data)
#     else:#说明从未获取过这只股票的历史数据
#         hist_data = ts.get_hist_data(nowcode, None, str(nowdate), 'D', 3, 0.001)
#         hdata.insert_perstock_hdatadate(nowcode, hist_data)

# hdata.db_disconnect()
