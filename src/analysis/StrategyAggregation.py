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

from .IndicatorAnalysis import Analysis

import pandas as pd


class StrategyAggregationDao():

    def __init__(self,code,buydate,win,lose):
        self.code = code
        self.buydate = buydate
        self.win = win
        self.lose = lose
        self.actionTimes = 0

        self.asi_0_4 = '0'
        self.asi_1_5 = '0'
        self.asi_15 = '0'
        self.asi_235 = '0'
        self.bias_0_2 = '0'
        self.bias_0_3 = '0'
        self.boll_2 = '0'
        self.kdj_14_522 = '0'
        self.kdj_14 = '0'
        self.kdj_15 = '0'
        self.kdj_15_522 = '0'
        self.rsi_0_4 = '0'
        self.rsi_0_5 = '0'
        pass

    def incrActionTimes(self):
        self.actionTimes += 1
    


class StrategyAggregation(Analysis):
    """
    聚合指标分析
    """

    def __init__(self,code):
        Analysis.__init__(self, code)  #继承父类的构造方法，也可以写成：super(Chinese,self).__init__(name,age)
        pass

    def analysis(self):
        """
        分析数据
        """
        pd = self.data()

        self.record = {}

        #遍历记录做聚合
        for index in pd.index:
            #按照购买日期定义数据聚合对象,同一日期的胜负任何策略都是相同的
            if(pd.loc[index]["buy_date"] not in self.record):
                self.record[pd.loc[index]["buy_date"]] = StrategyAggregationDao(pd.loc[index]["stock_code"],pd.loc[index]["buy_date"].strftime("%Y-%m-%d"),pd.loc[index]["win"],pd.loc[index]["lose"])
                pass

            sa = self.record[pd.loc[index]["buy_date"]]
            
            #查找是否有该记录的数据
            if pd.loc[index]["strategy"] == 'asi_0_4':
                sa.asi_0_4 = '1'
                sa.incrActionTimes()
                pass
            elif pd.loc[index]["strategy"] == 'asi_1_5':
                sa.asi_1_5 = '1'
                sa.incrActionTimes()
                pass
            elif pd.loc[index]["strategy"] == 'asi_15':
                sa.asi_15 = '1'
                sa.incrActionTimes()
                pass
            elif pd.loc[index]["strategy"] == 'asi_235':
                sa.asi_235 = '1'
                sa.incrActionTimes()
                pass
            elif pd.loc[index]["strategy"] == 'bias_0_2':
                sa.bias_0_2 = '1'
                sa.incrActionTimes()
                pass
            elif pd.loc[index]["strategy"] == 'bias_0_3':
                sa.bias_0_3 = '1'
                sa.incrActionTimes()
                pass
            elif pd.loc[index]["strategy"] == 'boll_2':
                sa.boll_2 = '1'
                sa.incrActionTimes()
                pass
            elif pd.loc[index]["strategy"] == 'kdj_14_522':
                sa.kdj_14_522 = '1'
                sa.incrActionTimes()
                pass
            elif pd.loc[index]["strategy"] == 'kdj_14':
                sa.kdj_14 = '1'
                sa.incrActionTimes()
                pass
            elif pd.loc[index]["strategy"] == 'kdj_15':
                sa.kdj_15 = '1'
                sa.incrActionTimes()
                pass
            elif pd.loc[index]["strategy"] == 'kdj_15_522':
                sa.kdj_15_522 = '1'
                sa.incrActionTimes()
                pass
            elif pd.loc[index]["strategy"] == 'rsi_0_4':
                sa.rsi_0_4 = '1'
                sa.incrActionTimes()
                pass
            elif pd.loc[index]["strategy"] == 'rsi_0_5':
                sa.rsi_0_5 = '1'
                sa.incrActionTimes()
                pass
        pass
    
    def saveToDB(self):
        """
        保存数据
        """
        conn = self.get_conn()
        cur = conn.cursor()

        for key in self.record:
            result = self.record[key]
            # buy_date = key.strftime("%Y-%m-%d")
            sql = self.parseAggregationSQL(result)
            cur.execute(sql)

        conn.commit()
        conn.close()
        pass

    def getSQL(self):#返回的是插入语句
        sql_temp = '''
            select stock_code,strategy,buy_date,win,lose 
            from stat_strategy 
            where stock_code = 
            '''+ "\'"+self.code +"\'  order by buy_date,strategy;"
        print(sql_temp)
        return sql_temp


    def parseAggregationSQL(self,sa):
        sql_temp = '''
        insert into stat_strategy_aggregation (stock_code,buy_date,asi_0_4,asi_1_5,asi_15,asi_235,bias_0_2,bias_0_3,boll_2,kdj_14_522,kdj_14,kdj_15,kdj_15_522,rsi_0_4,rsi_0_5,win,lose,action_times) values (
        '''+"\'"+sa.code+"\',\'"+sa.buydate+"\',"+sa.asi_0_4+","+sa.asi_1_5+","+sa.asi_15+","+sa.asi_235+","+sa.bias_0_2+","+sa.bias_0_3+","+sa.boll_2+","+sa.kdj_14_522+","+sa.kdj_14+","+sa.kdj_15+","+sa.kdj_15_522+","+sa.rsi_0_4+","+sa.rsi_0_5+","+str(sa.win)+","+str(sa.lose)+","+str(sa.actionTimes)+");"
        
        return sql_temp

if __name__ == '__main__':
    print ('作为主程序运行')
    st = StrategyAggregation('600036')
    st.action()

