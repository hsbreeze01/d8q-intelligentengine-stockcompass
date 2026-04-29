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


class BOLLAnalysis(Analysis):
    """
    BOLL指标分析
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
        pd["st0"]='' #量在可信区间
        pd["st1"]='' #盘整期趋势向上时,中值高于5日平均
        pd["st2"]='' #开口放大超过10% (upper_v-lower_v)/mid_v，且比前日大（放大趋势）
        pd["st3"]='' #转折点 前一天低于10%，当天高于10%
        pd["st4"]='' #收盘价> 中值 and 收盘价 < 高值

        pd["boll_2"]='' #只有2策略成功率比较大，作为辅助指标不看其他

        period = 2 #去掉开头几天
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
            if( pd.loc[index-1]["mid_v"] == 0):
                ulPre = 0
            else:
                ulPre = (pd.loc[index-1]["upper_v"] -  pd.loc[index-1]["lower_v"]) / pd.loc[index-1]["mid_v"]
            
            if( pd.loc[index]["mid_v"] == 0):
                ul = 0
            else:
                ul = (pd.loc[index]["upper_v"] -  pd.loc[index]["lower_v"]) / pd.loc[index]["mid_v"]

            #数据整理
            pd.at[index,"st2"] = ul > 0.1 and ul > ulPre

            #记录今天购买是否获胜
            win = pd.loc[index+1]["high"] > pd.loc[index]["close"]*bonus

            #策略实施统计
            if(pd.loc[index]["st2"] ):
                result['boll_2'] = win
                pd.at[index,"boll_2"] = win
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

        stlist = ["boll_2"]

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
          select a.stock_code,a.date,a.open,a.`close`,a.high,a.low,a.volume,c.ma5,c.ma10,c.ma20,c.ma30,c.ma60,b.upper_v,b.mid_v,b.lower_v
           from stock_data_daily a,indicators_boll_daily b,indicators_ma_daily c where a.stock_code =
            '''+ "\'"+self.code +"\' and a.stock_code = b.stock_code and a.stock_code = c.stock_code  and a.date = b.record_time and a.date = c.record_time order by a.date;"
        print(sql_temp)
        return sql_temp
