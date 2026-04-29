#! /usr/bin/python
# -*- coding: utf-8 -*-
#

import numpy as np
import os

import sys

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
path = os.path.split(rootPath)[0]
print(curPath,rootPath,path)

sys.path.append(path) # 这句是为了导入_config
sys.path.append(rootPath)

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
from stockfetch.db_ma import *

from stockfetch.dic_stock import *
from src.analysis import *


def test_000001():
    # set_data_backend(TushareDataBackend())
    code = "600036"
    endDate = "20241227"
    
    #设置数据来源
    set_data_backend(DBDataBackend())

    #获取数据
    T(endDate)#日期必须是开盘日（有数据的那一天）
    S(code)


    # T("20161216")
    # S("000001.XSHG")

    # print("=======================================")
    print("CLOSE",CLOSE,C)
    # print("CLOSE",CLOSE[3],C[4432])
    # print("DATETIME",DATETIME)
    # k,d,j = KDJ()

    #kdj
    # kdjdaily = KDJDaily(code)
    # kdjdaily.insert(KDJ(),DATETIME)


    # kdjdaily = KDJDaily(code,"522")
    # kdjdaily.insert(KDJ(5,2,2),DATETIME)


    #asi
    # asidaily = ASIDaily("600036")
    # asidaily.insert(ASI(),DATETIME)

    #bias
    # asidaily = BIASDaily("600036")
    # asidaily.insert(BIAS(),DATETIME)
    
    # boll
    # daily = BOLLDaily("600036")
    # daily.insert(BOLL(),DATETIME)

    # macd 数据貌似几个网站都不同
    # daily = MACDDaily("600036")
    # daily.insert(MACD(),DATETIME)

    # daily = RSIDaily("600036")
    # daily.insert(RSI(),DATETIME)
    # daily = RSIDaily("600036","3612")
    # daily.insert(RSI(3,6,12),DATETIME)

    # daily = VRDaily("600036")
    # daily.insert(VR(),DATETIME)

    #daily = WRDaily("600036")
    #daily.insert(WR(),DATETIME)

    # daily = MADaily("600036")
    # daily.insert(MA(CLOSE,5),MA(CLOSE,10),MA(CLOSE,20),MA(CLOSE,30),MA(CLOSE,60),DATETIME)


    # print("k len",len(k),len(DATETIME))
    # for index in reversed(range(len(DATETIME))):
    #     try:
    #         if(math.isnan(k[index].value)):
    #             print(k[index])
    #             continue

    #         print(index,k[index],d[index],j[index],DATETIME[index],get_str_date_from_int(DATETIME[index].value/1000000))
    #     except IndexError as identifier:
    #         print(identifier)
    #         pass

    #     pass


    # print("OPEN",OPEN)
    # print("MA5",MA(CLOSE,5))
    # print("MA10",MA(CLOSE,10))
    # print("MA30",MA(CLOSE,30))

    # SHORT = 12
    # LONG = 26
    # print(EMA(CLOSE, SHORT))
    # print(EMA(CLOSE, LONG))

    print("MACD",MACD())
    # print(HHV(HIGH, 5))
    # print(LLV(LOW, 5))
    # print(COUNT(CLOSE > OPEN, 5))
    # print("KDJ",KDJ())
    # print("RSI",RSI())
    # print("BOLL",BOLL())
    # print("WR",WR())
    # print("ASI",ASI())
    # print("BIAS",BIAS())#wrong
    # print("VR",VR())
    # assert np.equal(round(MACD().value, 2), -37.18)
    # assert np.equal(round(HHV(HIGH, 5).value, 2), 3245.09)
    # assert np.equal(round(LLV(LOW, 5).value, 2), 3100.91)
    # assert COUNT(CLOSE > OPEN, 5) == 2


#test_000001()



#刷新所有股票的kdj指标
def flushKDJ():
    stocks=DicStocks("gamer","123456")

    #owdate = datetime.datetime.now().date()
    #所有本地股票代码列表
    codes = stocks.get_codestock_local()

    for record in codes:
        calcAndinsertKDJ(record[1],"20201028")
        pass

    pass


#根据股票行情计算asi数据
def calcAndinsertASI(code,endDate):
     #设置数据来源
    set_data_backend(DBDataBackend())
    #获取数据
    T(endDate)#日期必须是开盘日（有数据的那一天）
    S(code)
    print("==START[",code,endDate,"]==",len(C))

    #没有100天的开盘记录不计算指标
    if(len(C) < 100):
        return

    daily = ASIDaily(code)
    daily.insert(ASI(),DATETIME)

    print("==END[",code,endDate,"]==")
    pass

def calcAndinsertBIAS(code,endDate):
     #设置数据来源
    set_data_backend(DBDataBackend())
    #获取数据
    T(endDate)#日期必须是开盘日（有数据的那一天）
    S(code)
    print("==START[",code,endDate,"]==BIAS",len(C))

    #没有100天的开盘记录不计算指标
    if(len(C) < 100):
        return

    daily = BIASDaily(code)
    daily.insert(BIAS(),DATETIME)

    print("==END[",code,endDate,"]==BIAS")
    pass

def calcAndinsertRSI(code,endDate):
     #设置数据来源
    set_data_backend(DBDataBackend())
    #获取数据
    T(endDate)#日期必须是开盘日（有数据的那一天）
    S(code)
    print("==START[",code,endDate,"]==RSI",len(C))

    #没有100天的开盘记录不计算指标
    if(len(C) < 100):
        return

    daily = RSIDaily(code)
    daily.insert(RSI(),DATETIME)

    print("==END[",code,endDate,"]==RSI")
    pass


def calcAndinsertBOLL(code,endDate):
     #设置数据来源
    set_data_backend(DBDataBackend())
    #获取数据
    T(endDate)#日期必须是开盘日（有数据的那一天）
    S(code)
    print("==START[",code,endDate,"]==BOLL",len(C))

    #没有100天的开盘记录不计算指标
    if(len(C) < 100):
        return

    daily = BOLLDaily(code)
    daily.insert(BOLL(),DATETIME)

    print("==END[",code,endDate,"]==RSI")
    pass


#根据股票行情计算kdj数据
def calcAndinsertKDJ(code,endDate):
     #设置数据来源
    set_data_backend(DBDataBackend())
    #获取数据
    T(endDate)#日期必须是开盘日（有数据的那一天）
    S(code)
    print("==START[",code,endDate,"]==",len(C))

    #没有100天的开盘记录不计算指标
    if(len(C) < 100):
        return

    kdjdaily = KDJDaily(code)
    kdjdaily.insert(KDJ(),DATETIME)

    kdjdaily = KDJDaily(code,"522")
    kdjdaily.insert(KDJ(5,2,2),DATETIME)

    print("==END[",code,endDate,"]==")
    pass


#根据股票行情计算kdj数据
def calcAndinsertMA(code,endDate):
     #设置数据来源
    set_data_backend(DBDataBackend())
    #获取数据
    T(endDate)#日期必须是开盘日（有数据的那一天）
    S(code)
    print("==START[",code,endDate,"]==",len(C))

    #没有100天的开盘记录不计算指标
    if(len(C) < 100):
        return

    daily = MADaily(code)
    daily.insert(MA(CLOSE,5),MA(CLOSE,10),MA(CLOSE,20),MA(CLOSE,30),MA(CLOSE,60),DATETIME)

   

    print("==END[",code,endDate,"]==")
    pass


#flushKDJ()



def testIndicators():
    arr = [1.0,3.0,5.0,1.0,3.0,5.0,1.0,3.0,5.0,1.0,3.0,5.0]
    arr = []
    for i in range(10):
        arr.append(i*i*1.0)
    arr = np.array(arr)

    print (arr)

    result = talib.EMA(arr,3*2-1)
    print (result)

    result = talib.EMA(result,3*2-1)
    print (result)


    result = talib.MA(arr,3*2-1)
    print (result)

    pass

#testIndicators()


def testAnalysis():
    stocks=DicStocks("gamer","123456")

    #owdate = datetime.datetime.now().date()
    #所有本地股票代码列表
    codes = stocks.get_codestock_local()
    
    for record in codes:
        # if record[0]<=1500:
        #     continue
        #     pass
        # #插入ma数据
        # calcAndinsertMA(record[1],"20201028")
        # calcAndinsertBIAS(record[1],"20201028")
        # calcAndinsertRSI(record[1],"20201028")
        # calcAndinsertBOLL(record[1],"20201028")
        
        analysis = StrategyAggregation(record[1])
        # analysis = BOLLAnalysis(record[1])
        # analysis = BIASAnalysis(record[1])
        # analysis = RSIAnalysis(record[1])
        # analysis = ASIAnalysis("600036")
        analysis.action()
        # analysis.executeStrategy()
        print("save:",record)
        pass        
    pass


def testAnalysisSingle():
    stocks=DicStocks("gamer","123456")
    analysis = RSIAnalysis("600036")
    analysis.action()
    pass


    # win = {}

    # for i in range(10):
    #     result ={}
    #     result['a'] = i
    #     result['b'] = i*2

    #     if(i % 2 == 0):
    #         result['c'] = i > 5
    #     win[i] = result
    #     pass
    
    # for key in win.keys():
    #     result = win[key]
    #     print(key,result.get('a',-1),result.get('b',-1),result.get('c',-1))
    #     pass
    
    # print(win)
   

testAnalysis()

# testAnalysisSingle()

#TODO bias，rsi，boll的需要统计