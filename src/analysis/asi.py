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


class ASIAnalysis(Analysis):
    """
    ASI指标分析
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
        pd["st1"]='' #asi是正且高于asit
        pd["st2"]='' #asi和asit的差值为放大趋势
        pd["st3"]='' #asi在某个周期内突破了自己 参数period 
        pd["st4"]='' #前一日收盘站在 n日线上，经过参数调优暂定10日线
        pd["st5"]='' #asi到asit的金叉且绝对值大于10

        pd["asi_0_4"]=''
        pd["asi_1_5"]=''
        pd["asi_15"]=''
        pd["asi_235"]=''

        period = 20 #st3的周期
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
            pd.at[index,"st1"] = (pd.loc[index]["asi"] > 0)  and ( pd.loc[index]["asi"] > pd.loc[index-1]["asi_t"])
            pd.at[index,"st2"] = abs( pd.loc[index]["asi"] - pd.loc[index]["asi_t"]) > abs( pd.loc[index-1]["asi"] - pd.loc[index-1]["asi_t"])
            
            #记录最大值(自己前一天倒数period天的最大值)
            maxRsi = pd.loc[index-period:index-1]["asi"].max()
            pd.at[index,"st3"] = pd.loc[index]["asi"] > maxRsi

            pd.at[index,"st4"] = pd.loc[index-1]["close"] > pd.loc[index-1]["ma10"]
            pd.at[index,"st5"] = (pd.loc[index-1]["asi"] < pd.loc[index-1]["asi_t"]) and (abs(pd.loc[index]["asi"] - pd.loc[index]["asi_t"]) > 10)

            #记录今天购买是否获胜
            win = pd.loc[index+1]["high"] > pd.loc[index]["close"]*bonus

            #策略实施统计
            if(pd.loc[index]["st0"] and pd.loc[index]["st1"] and pd.loc[index]["st2"] and pd.loc[index]["st3"] and pd.loc[index]["st4"]):
                result['asi_0_4'] = win
                pd.at[index,"asi_0_4"] = win
                pass
            
            if(pd.loc[index]["st1"] and pd.loc[index]["st2"] and pd.loc[index]["st3"] and pd.loc[index]["st4"] and pd.loc[index]["st5"]):
                result['asi_1_5'] = win
                pd.at[index,"asi_1_5"] = win
                pass
            
            if(pd.loc[index]["st1"] and pd.loc[index]["st5"]):
                result['asi_15'] = win
                pd.at[index,"asi_15"] = win
                pass
            
            if(pd.loc[index]["st2"] and pd.loc[index]["st3"] and pd.loc[index]["st5"]):
                result['asi_235'] = win
                pd.at[index,"asi_235"] = win
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

        stlist = ["asi_0_4", "asi_1_5", "asi_15", "asi_235"]

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
        sql_temp = '''
           select a.stock_code,a.date,a.open,a.`close`,a.high,a.low,a.volume,c.ma5,c.ma10,c.ma20,c.ma30,c.ma60,b.asi,b.asi_t 
           from stock_data_daily a,indicators_asi_daily b,indicators_ma_daily c where a.stock_code =
            '''+ "\'"+self.code +"\' and a.stock_code = b.stock_code and a.stock_code = c.stock_code  and a.date = b.record_time and a.date = c.record_time order by a.date;"
        
        
        print(sql_temp)
        return sql_temp

    def parseStrategySQL(self,stock_code,strategy,buy_date,today_close,next_day_high,buy_price,sale_price,win,lose):
        sql_temp = '''
        replace into stat_strategy (stock_code,strategy,buy_date,today_close,next_day_high,buy_price,sale_price,win,lose) values (
        '''+"\'"+stock_code+"\',\'"+strategy+"\',\'"+buy_date+"\',"+str(today_close)+","+str(next_day_high)+","+str(buy_price)+","+str(sale_price)+","+str(win)+","+str(lose)+");"
        return sql_temp
