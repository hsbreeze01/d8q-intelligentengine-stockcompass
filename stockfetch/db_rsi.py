#!/usr/bin/python
# -*- coding: UTF-8 -*-

import pymysql
# import tushare as ts
import pandas as pd
import datetime
# import numpy
import math
from funcat import *
from funcat.utils import *

from time import perf_counter as clock
from buy.Config import taskConfig as config

class RSIDaily(object):
    def __init__(self,code,param="61224",host=config.getDBconnection()['host'], port=config.getDBconnection()['port'], db=config.getDBconnection()['database'],user=config.getDBconnection()['user'], passwd=config.getDBconnection()['password'], ):
        self.code = code
        self.param = param
        self.host = host
        self.port = port
        self.db = db
        self.user = user
        self.password = passwd

    def get_conn(self):
        conn = pymysql.connect(host=self.host,port=self.port,user=self.user, passwd=self.password, database=self.db )
        return conn

    def db_disconnect(self):
        self.conn.close()

    def db_get_maxdate(self):#获取某支股票的最晚日期
        conn = self.get_conn()
        cur = conn.cursor()

        cur.execute("select max(date) from stock_data_daily where stock_code="+"\'"+self.code+"\';")
        ans=cur.fetchall()
        
        conn.commit()
        conn.close()

        if(len(ans)==0):
            return None
        
        return ans[0][0]
    
    def getData(self):
        lastUpdateDate = self.db_get_maxdate()

        if lastUpdateDate == None:
            lastUpdateDate = "2000-01-01"
            lastUpdateDate= datetime.datetime.strptime(lastUpdateDate,'%Y-%m-%d').date()

        conn = self.get_conn()
        cur = conn.cursor()

        sql_temp="select * from indicators_rsi_daily where stock_code="+"\'"+self.code+"\' and record_time <=\'"+lastUpdateDate+"\';"
        cur.execute(sql_temp)
        rows = cur.fetchall()

        conn.commit()
        conn.close()

        dataframe_cols=[tuple[0] for tuple in cur.description]#列名和数据库列一致
        df = pd.DataFrame(rows, columns=dataframe_cols)
        return df

    def insert(self,RSI,DATETIME):
        conn = self.get_conn()
        cur = conn.cursor()
        
        k = RSI[0]
        d = RSI[1]
        j = RSI[2]
        
        for index in reversed(range(len(DATETIME))):
            try:
                if(math.isnan(k[index].value) or math.isnan(d[index].value) or math.isnan(j[index].value)):
                    print(k[index],d[index],j[index])
                    continue

                sql = self.db_insertsql(self.code,k[index],d[index],j[index],get_str_date_from_int(DATETIME[index].value/1000000))
                cur.execute(sql)
            except IndexError as identifier:
                # print(identifier)
                pass
        pass
        conn.commit()
        conn.close()




    def db_insertsql(self,stock_code,b1,b2,b3,record_time,):#返回的是插入语句
        
        if(self.param == "3612"):
            sql_temp = '''
            replace into indicators_rsi_daily_3612 (stock_code,rsi_1,rsi_2,rsi_3,record_time) values (
            '''+"\'"+stock_code+"\',"+str(b1)+","+str(b2)+","+str(b3)+",\'"+record_time+"\');"
        
        else:
            sql_temp = '''
            replace into indicators_rsi_daily (stock_code,rsi_1,rsi_2,rsi_3,record_time) values (
            '''+"\'"+stock_code+"\',"+str(b1)+","+str(b2)+","+str(b3)+",\'"+record_time+"\');"
            pass  


        # print(sql_temp)
        return sql_temp



