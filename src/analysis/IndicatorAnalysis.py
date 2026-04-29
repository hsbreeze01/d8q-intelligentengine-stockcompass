#! /usr/bin/python
# -*- coding: utf-8 -*-
#

import numpy
import math
import pymysql
import pandas as pd
import datetime
from buy.Config import taskConfig as config

class Analysis(object):
    """
    分析函数的基类
    """
    def __init__(self,code,user=config.getDBconnection()['user'],password=config.getDBconnection()['password']):
        self.code = code
        self.user = user
        self.password=password
        self.code = code
        pass    

    def get_conn(self):
        conn = pymysql.connect(host=config.getDBconnection()['host'],port=config.getDBconnection()['port'], user=self.user, passwd=self.password, database=config.getDBconnection()['database'] )
        return conn
    
    def db_disconnect(self):
        self.conn.close()
    
    def action(self):
        """
        执行分析动作
        """
        # self.analysis()
        # self.saveToDB()
        pass

    #获取所有数据
    def data(self):
        # conn = self.get_conn()
        # cur = conn.cursor()

        conn = self.get_conn()
        cur = conn.cursor()

        sql = self.getSQL()
        cur.execute(sql)
        
        rows = cur.fetchall()

        conn.commit()
        conn.close()

        dataframe_cols=[tuple[0] for tuple in cur.description]#列名和数据库列一致
        df = pd.DataFrame(rows, columns=dataframe_cols)

        return df
    
    def analysis(self):
        """
        分析数据
        """
        raise NotImplementedError

    def saveToDB(self):
        """
        保存数据
        """
        raise NotImplementedError

    def getSQL(self):
        """
        获取要执行的sql
        """
        raise NotImplementedError
        pass

    def executeStrategy(self):
        """
        按照策略执行并存盘
        """
        raise NotImplementedError
        pass

    
    def parseStrategySQL(self,stock_code,strategy,buy_date,today_close,next_day_high,buy_price,sale_price,win,lose):
        sql_temp = '''
        replace into stat_strategy (stock_code,strategy,buy_date,today_close,next_day_high,buy_price,sale_price,win,lose) values (
        '''+"\'"+stock_code+"\',\'"+strategy+"\',\'"+buy_date+"\',"+str(today_close)+","+str(next_day_high)+","+str(buy_price)+","+str(sale_price)+","+str(win)+","+str(lose)+");"
        return sql_temp


