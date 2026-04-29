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

class BOLLDaily(object):
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

        sql_temp="select * from indicators_boll_daily where stock_code="+"\'"+self.code+"\' and record_time <=\'"+lastUpdateDate+"\';"
        cur.execute(sql_temp)
        rows = cur.fetchall()

        conn.commit()
        conn.close()

        dataframe_cols=[tuple[0] for tuple in cur.description]#列名和数据库列一致
        df = pd.DataFrame(rows, columns=dataframe_cols)
        return df

    def insert(self,BOLL,DATETIME):
        conn = self.get_conn()
        cur = conn.cursor()
        
        up  = BOLL[0]
        mid = BOLL[1]
        low = BOLL[2]
        
        for index in reversed(range(len(DATETIME))):
            try:
                if(math.isnan(up[index].value) or math.isnan(mid[index].value) or math.isnan(low[index].value)):
                    print(up[index],mid[index],low[index])
                    continue

                sql = self.db_insertsql(self.code,up[index],mid[index],low[index],get_str_date_from_int(DATETIME[index].value/1000000))
                cur.execute(sql)
            except IndexError as identifier:
                # print(identifier)
                pass
        pass
        conn.commit()
        conn.close()




    def db_insertsql(self,stock_code,p1,p2,p3,record_time,):#返回的是插入语句
        sql_temp = '''
            replace into indicators_boll_daily (stock_code,upper_v,mid_v,lower_v,record_time) values (
            '''+"\'"+stock_code+"\',"+str(p1)+","+str(p2)+","+str(p3)+",\'"+record_time+"\');"
        
        # print(sql_temp)
        return sql_temp



