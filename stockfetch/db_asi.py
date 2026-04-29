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
from buy.Config import taskConfig as config
from time import perf_counter as clock

class ASIDaily(object):
    def __init__(self,code,host=config.getDBconnection()['host'], port=config.getDBconnection()['port'], db=config.getDBconnection()['database'],user=config.getDBconnection()['user'], passwd=config.getDBconnection()['password'], ):
        self.code = code
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

        sql_temp="select * from indicators_asi_daily where stock_code="+"\'"+self.code+"\' and record_time <=\'"+lastUpdateDate+"\';"
        cur.execute(sql_temp)
        rows = cur.fetchall()

        conn.commit()
        conn.close()

        dataframe_cols=[tuple[0] for tuple in cur.description]#列名和数据库列一致
        df = pd.DataFrame(rows, columns=dataframe_cols)
        return df

    def insert(self,ASI,DATETIME):
        conn = self.get_conn()
        cur = conn.cursor()
        
        k = ASI[0]
        d = ASI[1]
        
        for index in reversed(range(len(DATETIME))):
            try:
                if(math.isnan(d[index].value) or math.isnan(k[index].value) or k[index].value > 999999 or k[index].value < -999999 or d[index].value > 999999 or d[index].value < -999999):
                    print(k[index],d[index])
                    continue

                sql = self.db_insertsql(self.code,k[index],d[index],get_str_date_from_int(DATETIME[index].value/1000000))
                cur.execute(sql)
            except IndexError as identifier:
                # print(identifier)
                pass
        pass
        conn.commit()
        conn.close()




    def db_insertsql(self,stock_code,asi,asit,record_time,):#返回的是插入语句
        sql_temp = '''
            replace into indicators_asi_daily (stock_code,asi,asi_t,record_time) values (
            '''+"\'"+stock_code+"\',"+str(asi)+","+str(asit)+",\'"+record_time+"\');"
        
        # print(sql_temp)
        return sql_temp



