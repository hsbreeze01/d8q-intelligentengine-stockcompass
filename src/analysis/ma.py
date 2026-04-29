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


class MAAnalysis(Analysis):
    """
    MA指标分析
    """

    def __init__(self,code):
        Analysis.__init__(self, code)  #继承父类的构造方法，也可以写成：super(Chinese,self).__init__(name,age)
        pass

    def getSQL(self):#返回的是插入语句
        # sql_temp = '''
        #     select a.stock_code,a.date,a.open,a.`close`,a.high,a.low,a.volume,c.ma5,c.ma10,c.ma20,c.ma30,c.ma60,b.rsi_1,b.rsi_2,b.rsi_3
        #     from stock_data_daily a,indicators_rsi_daily b,indicators_ma_daily c where a.stock_code =
        #     '''+ "\'"+self.code +"\' and a.stock_code = b.stock_code and a.stock_code = c.stock_code  and a.date = b.record_time and a.date = c.record_time order by a.date;"
        # # print(sql_temp)
        
        sql_temp = '''
            select a.stock_code,a.date,a.open,a.`close`,a.high,a.low,a.volume,b.ma5,b.ma10,b.ma20,b.ma30,b.ma60,b.rsi_6 as rsi_1,b.rsi_12 as rsi_2,b.rsi_24 as rsi_3
            from stock_data_daily a,indicators_daily b where a.stock_code = \'''' + self.code + '''\' and a.stock_code = b.stock_code and a.date = b.date order by a.date;
        '''
        
        return sql_temp

    # 预测趋势 MA
    # 返回的格式 {'ma5': -8.539820000000002, 'ma10': 0.9152569696969699, 'ma20': 0.2926642857142857}
    def predict_linear_trend(self, date=None):

        if date is None:#没有参数默认使用当前日期
            date = datetime.date.today().strftime('%Y%m%d')

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%Y%m%d').date()
        
        # print('预测日期',date)
        pd = self.data()
        # print(pd)
        # print('=======')
        #因为rsi分别是6天12天24天的，根据趋势需要根据MA的趋势来看，因此按照MA的时间来定义趋势的观测跨度
        period = {"ma5": 5, "ma10": 10, "ma20": 20}

        if len(pd) < period['ma20']:
            print("数据不足")
            return 0
        
        aData = []

        for index in reversed(pd.index):
            #大于分析日期的不进入队列
            if pd.loc[index]["date"] > date:
                continue
            
            aData.append(pd.loc[index])
            #只需要筛选出够用的最长期间的数据即可
            if len(aData) >= period['ma20']:
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
