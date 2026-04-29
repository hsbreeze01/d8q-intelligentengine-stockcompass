#!/usr/bin/python
# -*- coding: UTF-8 -*-

import pymysql
import tushare as ts
import pandas as pd
import datetime
import numpy

from time import perf_counter as clock

# class StockDataDaily(object):
#     def __init__(self,code,user="gamer",password="123456"):
#         # self.aaa = aaa
#         self.hdata_date=[]
#         self.user=user
#         self.password=password
#         self.code = code

#     def get_conn(self):
#         conn = pymysql.connect(host="localhost", user=self.user, passwd=self.password, database="stock" )
#         return conn

#     def db_disconnect(self):
#         self.conn.close()

#     def db_get_maxdate_of_stock(self):#获取某支股票的最晚日期
#         conn = self.get_conn()
#         cur = conn.cursor()

#         cur.execute("select max(record_time) from stock_data_daily where stock_code="+"\'"+self.code+"\';")
#         ans=cur.fetchall()
        
#         conn.commit()
#         conn.close()

#         if(len(ans)==0):
#             return None
        
#         return ans[0][0]
    
#     def fetchData(self):
#         lastUpdateDate = self.db_get_maxdate_of_stock()
#         if lastUpdateDate == None:
#             lastUpdateDate = "2000-01-01"
#             lastUpdateDate= datetime.datetime.strptime(lastUpdateDate,'%Y-%m-%d').date()
            
#         nowdate = datetime.datetime.now().date()

#         conn = self.get_conn()
#         cur = conn.cursor()

#         print("start fetch data",lastUpdateDate, nowdate,"code",self.code)
#         df = ts.get_k_data(self.code, start=str(lastUpdateDate+datetime.timedelta(1)), end=str(nowdate), index=False, ktype='D')

#         count = 0
#         for index in df.index:
#             # print(df.loc[index]["code"])
#             if(df.loc[index]["code"] != self.code):
#                 print("===========error")
#                 break
#             #旧数据没有换手率，2018-5月后的数据用 #hist_data = ts.get_hist_data("600036", str(maxdate+datetime.timedelta(1)),str(nowdate), 'D', 3, 0.001) 获取
#             cur.execute(self.db_insertsql(df.loc[index]["code"],df.loc[index]["date"],df.loc[index]["open"],df.loc[index]["close"],df.loc[index]["high"],df.loc[index]["low"],df.loc[index]["volume"],0,0,0,0,0,0,0,0,0))
#             count += 1

#         conn.commit()
#         conn.close()
#         print("end fetch data row:",count)

#     def db_insertsql(self,stock_code,record_time,open,close,high,low,volume,price_change,p_change,ma5,ma10,ma20,v_ma5,v_ma10,v_ma20,turnover):#返回的是插入语句
#         sql_temp = '''
#             insert into stock_data_daily (stock_code,record_time,open,close,high,low,volume,price_change,p_change,
#             ma5,ma10,ma20,v_ma5,v_ma10,v_ma20,turnover) values (
#             '''+"\'"+stock_code+"\',\'"+record_time+"\',"+numpy.str(open)+","+numpy.str(close)+","+numpy.str(high)+","+numpy.str(low)+","+numpy.str(volume)+","+numpy.str(price_change)+","+numpy.str(p_change)+","+numpy.str(ma5)+","+numpy.str(ma10)+","+numpy.str(ma20)+","+numpy.str(v_ma5)+","+numpy.str(v_ma10)+","+numpy.str(v_ma20)+","+numpy.str(turnover)+");"
        
#         # print(sql_temp)
#         return sql_temp


#     def get_all_hdata_of_stock(self):#将数据库中的数据读取并转为dataframe格式返回
#         conn = self.get_conn()

#         cur = conn.cursor()

#         sql_temp="select * from stock_data_daily where stock_code="+"\'"+self.code+"\';"
#         cur.execute(sql_temp)
#         rows = cur.fetchall()

#         conn.commit()
#         conn.close()

#         dataframe_cols=[tuple[0] for tuple in cur.description]#列名和数据库列一致
#         df = pd.DataFrame(rows, columns=dataframe_cols)
#         return df
#         pass


    
    # def __db_hdata_date_create(self):
    #     conn = pymysql.connect(host="localhost", user=self.user, passwd=self.password, database="stock" )
    #     cur = conn.cursor()

    #     # 创建stocks表
    #     cur.execute('''
    #             drop table if exists stock_data_daily;
    #             create table stock_data_daily(stock_code varchar,record_date date,
    #                 open float,high float,close float,low float,
    #                 volume float,
    #                 price_change float,p_change float,
    #                 ma5 float,ma10 float,ma20 float,
    #                 v_ma5 float,v_ma10 float,v_ma20 float,
    #                 turnover float
    #             );
    #             alter table hdata_date add primary key(stock_code,record_date);
    #             ''')
    #     conn.commit()
    #     conn.close()
    #     print("db_hdata_date_create finish")
    #     pass

