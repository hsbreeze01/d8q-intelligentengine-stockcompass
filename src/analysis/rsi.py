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

class RSIAnalysis(Analysis):
    logger = logging.getLogger("my_logger")
    """
    RSI指标分析
    """

    def __init__(self,code):
        Analysis.__init__(self, code)  #继承父类的构造方法，也可以写成：super(Chinese,self).__init__(name,age)
        pass

    def analysis(self):
        """
        分析数据
        """
        pd = self.data()

        #追加列

        pd["st0"]='' #量比前日高,少于2倍
        pd["st1"]='' #rsi1斜率比前一天高
        pd["st2"]='' #rsi1大于前一日
        pd["st3"]='' ##rsi1大于rsi2
        pd["st4"]='' #rsi1在合理区间 x>=70 and x<=90
        pd["st5"]='' #金叉(rsi_1,rsi_2出现反转)

        pd["rsi_0_4"]=''
        pd["rsi_0_5"]=''

        period = 2 #st3的周期
        bonus = Decimal(1.01)#盈利百分比

        self.win = {}

        #获取n日内的最大值
        if(len(pd) <= period):
            print("== to short",len(pd))
            return
        
        #数据处理 去掉头2天（因为数据要倒回2天） 去掉最后1天（因为盈利要看买入的第2天数据）
        for index in pd.index[period:-1]:
            # print(index,pd.loc[index]["record_time"])
            #记录操作结果
            result={}
            
            #数据整理
            pd.at[index,"st0"] = (pd.loc[index]["volume"] > pd.loc[index-1]["volume"]) and (pd.loc[index]["volume"]/2 < pd.loc[index-1]["volume"])
            pd.at[index,"st1"] = (pd.loc[index]["rsi_1"] - pd.loc[index-1]["rsi_1"]) > (pd.loc[index-1]["rsi_1"] - pd.loc[index-2]["rsi_1"])
            pd.at[index,"st2"] = pd.loc[index]["rsi_1"] > pd.loc[index-1]["rsi_1"]
            pd.at[index,"st3"] = pd.loc[index]["rsi_1"] > pd.loc[index]["rsi_2"]
            pd.at[index,"st4"] = pd.loc[index]["rsi_1"] >=70 and pd.loc[index]["rsi_1"] <=90
            pd.at[index,"st5"] = pd.loc[index-1]["rsi_1"] < pd.loc[index-1]["rsi_2"] and pd.loc[index]["rsi_1"] > pd.loc[index]["rsi_2"]
            
            #记录今天购买是否获胜
            win = pd.loc[index+1]["high"] > pd.loc[index]["close"]*bonus

            #策略实施统计
            if(pd.loc[index]["st0"] and pd.loc[index]["st1"] and pd.loc[index]["st2"] and pd.loc[index]["st3"] and pd.loc[index]["st4"]):
                result['rsi_0_4'] = win
                pd.at[index,"rsi_0_4"] = win
                pass
            
            if(pd.loc[index]["st0"] and pd.loc[index]["st1"] and pd.loc[index]["st2"] and pd.loc[index]["st3"] and pd.loc[index]["st4"] and pd.loc[index]["st5"]):
                result['rsi_0_5'] = win
                pd.at[index,"rsi_0_5"] = win
                pass
            
            if(len(result) > 0):
                result['nexthigh'] = pd.loc[index+1]["high"]
                result['close'] = pd.loc[index]["close"]
                self.win[pd.loc[index]["date"]] = result
            pass

        pass
    
    def saveToDB(self):
        """
        保存数据
        """
        conn = self.get_conn()
        cur = conn.cursor()

        stlist = ["rsi_0_4", "rsi_0_5"]

        for key in self.win.keys():
            result = self.win[key]
            buy_date = key.strftime("%Y-%m-%d")

            for st in stlist:
                if(result.get(st,-1) == -1):
                    continue
                high = result.get('nexthigh')
                close = result.get('close')
                buy_price = close
                sale_price = 0

                win = 0
                lose = 1
                if(result.get(st)):#失败 不获得分数 获胜 买价*1.01
                    sale_price = buy_price*Decimal(1.01)
                    win = 1
                    lose = 0
                    pass

                cur.execute(self.parseStrategySQL(self.code,st,buy_date,close,high,buy_price,sale_price,win,lose))
                pass
            pass

        conn.commit()
        conn.close()

        pass

    def getSQL(self):#返回的是插入语句
        # sql_temp = '''
        #     select a.stock_code,a.date,a.open,a.`close`,a.high,a.low,a.volume,c.ma5,c.ma10,c.ma20,c.ma30,c.ma60,b.rsi_1,b.rsi_2,b.rsi_3
        #     from stock_data_daily a,indicators_rsi_daily b,indicators_ma_daily c where a.stock_code =
        #     '''+ "\'"+self.code +"\' and a.stock_code = b.stock_code and a.stock_code = c.stock_code  and a.date = b.record_time and a.date = c.record_time order by a.date;"
        # # print(sql_temp)

        sql_temp = '''
            select a.stock_code,a.date,a.open,a.`close`,a.high,a.low,a.volume,b.ma5,b.ma10,b.ma20,b.ma30,b.ma60,b.rsi_6 as rsi_1,b.rsi_12 as rsi_2,b.rsi_24 as rsi_3
            from stock_data_daily a,indicators_daily b where a.stock_code = \'''' + self.code + '''\' and a.stock_code = b.stock_code and a.date = b.date  order by a.date;
        '''

        return sql_temp

    # 预测趋势 RSI 的值范围是 -100 到 100，因此趋势按照线性回归预测的最大绝对值是 100
    # 返回的格式 {'rsi_1': -8.539820000000002, 'rsi_2': 0.9152569696969699, 'rsi_3': 0.2926642857142857}
    def predict_linear_trend(self, date=None):
        """
        预测趋势
        rsi1 6日均线 rsi2 12日均线 rsi3 24日均线
        """
        if date is None:#没有参数默认使用当前日期
            date = datetime.date.today().strftime('%Y%m%d')

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%Y%m%d').date()
        
        # print('预测日期',date)
        pd = self.data()
        # print(pd)
        # print('=======')
        #因为rsi分别是6天12天24天的，根据趋势需要根据MA的趋势来看，因此按照MA的时间来定义趋势的观测跨度
        period = {"rsi_1": 5, "rsi_2": 10, "rsi_3": 20}

        # 去掉date > date的数据
        # pd = pd[pd["date"] <= date]

        if len(pd) < period['rsi_3']:
            self.logger.debug("数据不足")
            # print("数据不足")
            return 0
        
        aData = []

        for index in reversed(pd.index):
            #大于分析日期的不进入队列
            if pd.loc[index]["date"] > date:
                continue
            
            aData.append(pd.loc[index])
            #只需要筛选出够用的最长期间的数据即可
            if len(aData) >= period['rsi_3']:
                break
        

        # print(aData)
        #根据周期，使用线性回归算法预测回归的趋势
        result = {}
        for key, days in period.items():
            # Extract the last 'days' rsi values
            rsi_values = list(reversed([data[key] for data in aData[:days]]))
            # Prepare the data for linear regression
            X = np.array(range(len(rsi_values))).reshape(-1, 1)  # X轴的长度必须按照实际rsi的值来定，因为初期的时候会不足某个天数
            y = np.array(rsi_values).reshape(-1, 1)  # rsi values as dependent variable

            # Perform linear regression
            model = LinearRegression()
            model.fit(X, y)

            # print(key,y)

            # Get the slope (coefficient) of the line
            slope = model.coef_[0][0]
            result[key] = {'data':y,'slope':slope}

       
        return result, aData[0]["date"].strftime('%Y%m%d')


    def determine_strength(self, date=None):
        """
        判定股票多空双方的强弱
        """
        if date is None:#没有参数默认使用当前日期
            date = datetime.date.today().strftime('%Y%m%d')

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%Y%m%d').date()
        
        # print('预测日期',date)
        pd = self.data()
        # print(pd)
        # print('=======')
        #判定rsi指标5日内每天的强弱
        period = {"rsi_1": 5,}

        if len(pd) < period['rsi_1']:
            self.logger.debug("数据不足")
            return 0
        
        aData = []

        for index in reversed(pd.index):
            #大于分析日期的不进入队列
            if pd.loc[index]["date"] > date:
                continue
            
            aData.append(pd.loc[index])
            #只需要筛选出够用的最长期间的数据即可
            if len(aData) >= period['rsi_1']:
                break
        # print(aData)
        #根据周期，使用线性回归算法预测回归的趋势
        result = {}
        for key, days in period.items():
            # Extract the last 'days' rsi values
            rsi_values = list(reversed([data[key] for data in aData[:days]]))
            y = []
            # Determine the strength for each RSI value
            for rsi_value in rsi_values:
                if rsi_value > 80:
                    y.append([rsi_value, "超买"])
                elif rsi_value > 50:
                    y.append([rsi_value, "强"])
                elif rsi_value == 50:
                    y.append([rsi_value, "平"])
                elif rsi_value < 15:
                    y.append([rsi_value, "超卖-转折点"])
                elif rsi_value < 20:
                    y.append([rsi_value, "超卖"])
                elif rsi_value < 50:
                    y.append([rsi_value, "弱"])

            result[key] = {'data':y}

       
        return result, aData[0]["date"].strftime('%Y%m%d')
    
    def check_cross(self, date=None):
        """
        判定rsi的指标是否在rsi的低位20或者高位80出现金叉或者死叉
        """
        if date is None:  # 没有参数默认使用当前日期
            date = datetime.date.today().strftime('%Y%m%d')

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%Y%m%d').date()

        # print('检查日期', date)
        # self.logger.debug('检查日期' + date)
        pd = self.data()

        period = {"rsi_1": 5, "rsi_2": 5}

        if len(pd) < period['rsi_2']:
            self.logger.debug("数据不足")
            return 0
        
        aData = []

        for index in reversed(pd.index):
            #大于分析日期的不进入队列
            if pd.loc[index]["date"] > date:
                continue
            
            aData.append(pd.loc[index])
            #只需要筛选出够用的最长期间的数据即可
            if len(aData) >= period['rsi_2']:
                break
            pass
            
        
        result = {}

        aData = list(reversed(aData))

        for i in range(1, len(aData)):
            d = aData[i]['date'].strftime('%Y%m%d')
            
            rsi_1_today = aData[i]["rsi_1"]
            rsi_2_today = aData[i]["rsi_2"]
            rsi_1_yesterday = aData[i - 1]["rsi_1"]
            rsi_2_yesterday = aData[i - 1]["rsi_2"]

            # print(d,rsi_1_today, rsi_2_today, rsi_1_yesterday, rsi_2_yesterday)

            if rsi_1_today > rsi_2_today and rsi_1_yesterday <= rsi_2_yesterday:
                result[d] = "金叉"
                if rsi_1_today < 20:
                    result[d] = "低位金叉"
                elif rsi_1_today > 80:
                    result[d] = "高位金叉"

            if rsi_1_today < rsi_2_today and rsi_1_yesterday >= rsi_2_yesterday:
                result[d] = "死叉"
                if rsi_1_today < 20:
                    result[d] = "低位死叉"
                elif rsi_1_today > 80:
                    result[d] = "高位死叉"

        return result