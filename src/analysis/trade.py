#! /usr/bin/python
# -*- coding: utf-8 -*-
#

import os
import sys

import numpy

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
path = os.path.split(rootPath)[0]
sys.path.append(path) # 这句是为了导入_config
sys.path.append(rootPath)

import math
from decimal import Decimal

from .IndicatorAnalysis import Analysis
import pandas as pd
import datetime
from sklearn.linear_model import LinearRegression
import numpy as np
import logging

class TradeAnalysis(Analysis):
    logger = logging.getLogger("my_logger")
    """
    交易分析
    """

    def __init__(self,code):
        Analysis.__init__(self, code)  #继承父类的构造方法，也可以写成：super(Chinese,self).__init__(name,age)
        pass

    def getSQL(self):#返回的是插入语句
        # sql_temp = '''
        #     select a.stock_code,a.date,a.open,a.`close`,a.high,a.low,a.volume,a.turnover_rate,c.ma5,c.ma10,c.ma20,c.ma30,c.ma60,b.upper_v,b.mid_v,b.lower_v
        #     ,d.macd,e.rsi_1,f.k
        #     from stock_data_daily a,indicators_boll_daily b,indicators_ma_daily c ,indicators_macd_daily d,indicators_rsi_daily e,indicators_kdj_daily f where a.stock_code =
        #     '''+ "\'"+self.code +"\' and a.stock_code = b.stock_code and a.stock_code = c.stock_code and a.stock_code = d.stock_code and a.stock_code = e.stock_code and a.stock_code = f.stock_code  and a.date = b.record_time and a.date = c.record_time and a.date = d.record_time and a.date = e.record_time and a.date = f.record_time order by a.date;"
        # # print(sql_temp)

        sql_temp = '''
            select a.stock_code,a.date,a.open,a.`close`,a.high,a.low,a.volume,a.turnover_rate,b.ma5,b.ma10,b.ma20,b.ma30,b.ma60,b.boll_up as upper_v,b.boll_mid as mid_v,b.boll_low as lower_v
            ,b.macd_macd as macd,b.rsi_6 as rsi_1,b.kdj_k as k
            from stock_data_daily a,indicators_daily b where a.stock_code = \'''' + self.code + '''\' and a.stock_code = b.stock_code and a.date = b.date order by a.date;
        '''
        return sql_temp
    
    def getHistoryHighLow(self, date=None):
        """
        获取历史60天最高价和最低价
        """
        if date is None:
            date = datetime.date.today().strftime('%Y%m%d')
        
        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%Y%m%d').date()

        startdate = date - datetime.timedelta(days=60)#获取60天的数据
        # self.logger.debug('开始日期 %s 结束日期 %s', startdate, date)

        conn = self.get_conn()
        cur = conn.cursor()

        sql = f"select max(high), min(low) from stock_data_daily where date between '{startdate.strftime('%Y%m%d')}' and '{date.strftime('%Y%m%d')}' and stock_code = '{self.code}'"
        cur.execute(sql)
        
        rows = cur.fetchall()

        conn.commit()
        conn.close()

        return rows[0][0],rows[0][1]


    def predict_trade(self, date=None):
        """
        判定rsi的指标是否在rsi的低位20或者高位80出现金叉或者死叉
        """

        hishigh,hislow = self.getHistoryHighLow(date)

        if date is None:  # 没有参数默认使用当前日期
            date = datetime.date.today().strftime('%Y%m%d')

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%Y%m%d').date()

        # print('检查日期', date)
        pd = self.data()
        # print('=======')

        period = {"trade": 6}

        if len(pd) < period['trade']:
            print("数据不足")
            return 0
        
        aData = []

        for index in reversed(pd.index):
            #大于分析日期的不进入队列
            if pd.loc[index]["date"] > date:
                continue
            
            aData.append(pd.loc[index])
            #只需要筛选出够用的最长期间的数据即可
            if len(aData) >= period['trade']:
                break
            pass
        
        result = {}

        aData = list(reversed(aData))

        for i in range(1, len(aData)):
            d = aData[i]['date'].strftime('%Y%m%d')
            today = aData[i]
            yesterday = aData[i - 1]

            # 初始化 result 字典中的日期键
            if d not in result:
                result[d] = {}

            #判定今天股价是创新高或者创新低
            if today["high"] >= hishigh:
                result[d]['judge_high'] = "创新高"
                if today["macd"] <= yesterday["macd"]:
                    result[d]['judge_high_macd'] = "macd背离"
                    result[d]['judge_high'] += " macd背离"
                if today["rsi_1"] <= yesterday["rsi_1"]:
                    result[d]['judge_high_rsi'] = "rsi背离"
                    result[d]['judge_high'] += " rsi背离"
                if today["k"] <= yesterday["k"]:
                    result[d]['judge_high_kdj'] = "kdj背离"
                    result[d]['judge_high'] += " kdj背离"
                if today["volume"] <= yesterday["volume"]:
                    result[d]['judge_high_volume'] = "volume背离"
                    result[d]['judge_high'] += " volume背离"
                if today["turnover_rate"] <= yesterday["turnover_rate"]:
                    result[d]['judge_high_turnover_rate'] = "turnover_rate背离"
                    result[d]['judge_high'] += " turnover_rate背离"
                

            if today["low"] <= hislow:
                result[d]['judge_low'] = "创新低"
                if today["macd"] >= yesterday["macd"]:
                    result[d]['judge_low_macd'] = "macd背离"
                    result[d]['judge_low'] += " macd背离"
                if today["rsi_1"] >= yesterday["rsi_1"]:
                    result[d]['judge_low_rsi'] = "rsi背离"
                    result[d]['judge_low'] += " rsi背离"
                if today["k"] >= yesterday["k"]:
                    result[d]['judge_low_kdj'] = "kdj背离"
                    result[d]['judge_low'] += " kdj背离"
                if today["volume"] >= yesterday["volume"]:
                    result[d]['judge_low_volume'] = "volume背离"
                    result[d]['judge_low'] += " volume背离"
                if today["turnover_rate"] >= yesterday["turnover_rate"]:
                    result[d]['judge_low_turnover_rate'] = "turnover_rate背离"
                    result[d]['judge_low'] += " turnover_rate背离"

            #高开还是低开
            if today["open"] > yesterday["close"]:
                result[d]['judge_open'] = "高开"
            elif today["open"] < yesterday["close"]:
                result[d]['judge_open'] = "低开"
            else:
                result[d]['judge_open'] = "平开"

            #判定今天是涨还是跌
            if today["close"] > today["open"]:
                result[d]['judge'] = "涨"
            elif today["close"] < today["open"]:
                result[d]['judge'] = "跌"
            else:
                result[d]['judge'] = "平"

            result[d]['today'] = " open[" + str(today["open"]) + "] close[" + str(today["close"])+"] high["+str(today["high"])+"] low["+str(today["low"])+"]"
            result[d]['open'] = float(today["open"])
            result[d]['close'] = float(today["close"])
            result[d]['high'] = float(today["high"])
            result[d]['low'] = float(today["low"])

            #判定十字星
            if abs(today["open"] - today["close"]) / today["open"] <= 0.001:
                result[d]['judge_cross'] = "十字星 股价在高位要下跌 股价在低位要上涨"

            result[d]['ma5'] = today["ma5"]
            result[d]['ma10'] = today["ma10"]
            result[d]['ma20'] = today["ma20"]
            result[d]['volume'] = int(today["volume"])
            result[d]['volume_rate'] = today["volume"]/yesterday["volume"]

            result[d]['turnover_rate'] = float(today["turnover_rate"])
            #连续涨停的时候换手率会为0，这个时候换手率的对比就取100倍
            if yesterday["turnover_rate"] == 0:
                result[d]['turnover_rate_rate'] = 100
            else:
                result[d]['turnover_rate_rate'] = float(today["turnover_rate"]/yesterday["turnover_rate"])

            #判定支撑位和压力位置
            if today["close"] > today["ma5"]:
                result[d]['judge_ma5'] = "支撑"
            elif today["close"] < today["ma5"]:
                result[d]['judge_ma5'] = "压力"
            else:
                result[d]['judge_ma5'] = "平行"

            if today["close"] > today["ma10"]:
                result[d]['judge_ma10'] = "支撑"
            elif today["close"] < today["ma10"]:
                result[d]['judge_ma10'] = "压力"
            else:
                result[d]['judge_ma10'] = "平行"

            if today["close"] > today["ma20"]:
                result[d]['judge_ma20'] = "支撑"
            elif today["close"] < today["ma20"]:
                result[d]['judge_ma20'] = "压力"
            else:
                result[d]['judge_ma20'] = "平行"

            result[d]['buy_signal_ma5'] = ""
            result[d]['buy_signal_ma10'] = ""
            result[d]['buy_signal_ma20'] = ""
            #昨天在压力线下，今天在支撑线上，同时今天是涨的，买入信号
            if yesterday["close"] < yesterday["ma5"] and today["close"] > today["ma5"] and today["close"] > today["open"]:
                result[d]['buy_signal_ma5'] = "买入信号"
                
            if yesterday["close"] < yesterday["ma10"] and today["close"] > today["ma10"] and today["close"] > today["open"]:
                result[d]['buy_signal_ma10'] = "买入信号"
                
            if yesterday["close"] < yesterday["ma20"] and today["close"] > today["ma20"] and today["close"] > today["open"]:
                result[d]['buy_signal_ma20'] = "买入信号"

            # 昨天在支撑线上，今天在压力线下，卖出信号
            result[d]['sell_signal_ma5'] = ""
            result[d]['sell_signal_ma10'] = ""
            result[d]['sell_signal_ma20'] = ""

            if yesterday["close"] > yesterday["ma5"] and today["close"] < today["ma5"] :
                result[d]['sell_signal_ma5'] = "卖出信号"
                
            if yesterday["close"] > yesterday["ma10"] and today["close"] < today["ma10"] :
                result[d]['sell_signal_ma10'] = "卖出信号"
                
            if yesterday["close"] > yesterday["ma20"] and today["close"] < today["ma20"] :
                result[d]['sell_signal_ma20'] = "卖出信号"
            
            #boll价格
            result[d]['upper_v'] = today["upper_v"]
            result[d]['mid_v'] = today["mid_v"]
            result[d]['lower_v'] = today["lower_v"]

            #根据boll的上中下轨判断支撑和压力位
            result[d]['judge_boll_lower'] = ""
            result[d]['judge_boll_upper'] = ""

            if today["close"] > today["lower_v"] and today["close"] < today["mid_v"]:
                result[d]['judge_boll_lower'] = "支撑"
            
            
            if today["close"] < today["upper_v"] and today["close"] > today["mid_v"]:
                result[d]['judge_boll_upper'] = "压力"

            #根据boll的上中下轨判断买入卖出
            result[d]['sell_signal_boll'] = ""
            result[d]['buy_signal_boll'] = ""
            #当日收盘价大于上轨，卖出信号
            if today["close"] > today["upper_v"]:
                result[d]['sell_signal_boll'] = "卖出信号"
            #昨日在mid下，今天在mid上，买入信号
            if yesterday['close'] < yesterday["mid_v"] and yesterday['open'] < yesterday["mid_v"] and today["close"] > today["mid_v"]:
                result[d]['buy_signal_boll'] = "买入信号"
            pass
        
        #如果连续3天都在上涨，但是量价背离，量比前日少一半，卖出信号
        
        for i in range(2, len(aData)):
            d = aData[i]['date'].strftime('%Y%m%d')
            today = aData[i]
            yesterday = aData[i - 1]
            before_yesterday = aData[i - 2]

            result[d]['sell_signal_volume'] = ""
            if today["close"] > yesterday["close"] and yesterday["close"] > before_yesterday["close"] and today["volume"] < yesterday["volume"]/2:
                result[d]['sell_signal_volume'] = "卖出信号"
            pass

        #如果连续3天都在下跌，且是放量下跌，量比之前至少多一倍，买入信号
        for i in range(2, len(aData)):
            d = aData[i]['date'].strftime('%Y%m%d')
            today = aData[i]
            yesterday = aData[i - 1]
            before_yesterday = aData[i - 2]

            result[d]['buy_signal_volume'] = ""
            if today["close"] < yesterday["close"] and yesterday["close"] < before_yesterday["close"] and today["volume"] > yesterday["volume"]*2:
                result[d]['buy_signal_volume'] = "买入信号"
            pass

        
        return result