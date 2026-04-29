#!/usr/bin/python
# -*- coding: UTF-8 -*-

import tushare as ts
import pymysql
import numpy

# class DicStocks(object):#这个类表示"股票们"的整体(不是单元)
#     def __init__(self,user,password):
#         # self.aaa = aaa
#         self.basics_all=[]
#         self.user=user
#         self.password=password

#     def get_today_all(self):
#         #pro = ts.pro_api()
#         #pro.stock_basic()
#         self.basics_all = ts.get_stock_basics()

#     def get_conn(self):
#         conn = pymysql.connect(host="localhost", user=self.user, passwd=self.password, database="stock" )
#         return conn

#     def get_codestock_local(self):#从本地获取所有股票代号和名称
#         conn = self.get_conn()
#         cur = conn.cursor()

#         # 创建stocks表
#         cur.execute('''
#                 select * from dic_stock;
#                ''')
#         rows =cur.fetchall()
        
#         conn.commit()
#         conn.close()
#         return rows


#     def db_perstock_insertsql(self,stock_code,cns_name,industry,area,pe,outstanding,totals,totalAssets):#返回的是插入语句
#         sql_temp="insert into dic_stock(stock_code,stock_name,industry,area,pe,outstanding,totals,totalAssets,last_update_time) values("
#         sql_temp+="\'"+stock_code+"\',\'"+cns_name+"\',\'"+industry+"\',\'"+area+"\',"+str(pe)+","+str(outstanding)+","+str(totals)+","+str(totalAssets) +", now()"
#         sql_temp +=");"
#         print(sql_temp)
#         return sql_temp

# #更新stock表数据，返回新增的stock数据
#     def db_stocks_update(self):# 根据getbasics_all的情况插入原表中没的。。getbasics_all中有的源表没的保留不删除#返回新增行数
#         ans=0
#         conn = self.get_conn()
#         cur = conn.cursor()
#         self.get_today_all()

#         print("len:",len(self.basics_all))

#         for code in self.basics_all.index:
#             sql_temp='''select * from dic_stock where stock_code='''
#             sql_temp+="\'"+code+"\';"
#             cur.execute(sql_temp)
#             rows=cur.fetchall()

#             if(len(rows)==0):
#                 #如果股票代码没找到就插
#                 ans+=1
#                 cur.execute(self.db_perstock_insertsql(code,self.basics_all.loc[code]["name"],
#                 self.basics_all.loc[code]["industry"],self.basics_all.loc[code]["area"],self.basics_all.loc[code]["pe"],self.basics_all.loc[code]["outstanding"],self.basics_all.loc[code]["totals"],self.basics_all.loc[code]["totalAssets"]))
#                 pass
            
#             pass

#         # for i in range(0,len(self.basics_all)):
#         #     sql_temp='''select * from dic_stock where stock_code='''
#         #     sql_temp+="\'"+self.basics_all["code"][i]+"\';"
#         #     cur.execute(sql_temp)
#         #     rows=cur.fetchall()
            
#         #     if(len(rows)==0):
#         #         #如果股票代码没找到就插
#         #         ans+=1
#         #         cur.execute(self.db_perstock_insertsql(self.basics_all["code"][i],self.basics_all["name"][i],
#         #         self.basics_all["industry"][i],self.basics_all["area"][i],self.basics_all["pe"][i],self.basics_all["outstanding"][i],self.basics_all["totals"][i],self.basics_all["totalAssets"][i]))
#         #         pass

#         conn.commit()
#         conn.close()
#         print("db_stocks_update finish")
#         return ans


# #创建stock表
#     def db_stocks_create(self):
#         conn = self.get_conn()
#         cur = conn.cursor()
#         # 创建stocks表
#         cur.execute('''
#             drop table if exists dic_stock;
#             create table dic_stock(stock_code varchar primary key,cns_name varchar);
#         ''')
#         conn.commit()
#         conn.close()
#         print("db_stocks_create finish")
#         pass
