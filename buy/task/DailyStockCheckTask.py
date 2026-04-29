#!/usr/bin/python
# -*- encoding: utf-8 -*-

"""
Description: 每日检测股票交易信息
Version: 1.0
Autor: Sam Zhu
Date: 2020-12-19 23:07:10
LastEditTime: 2020-12-27 21:20:53
"""

import sys

import logging
from .Task import Task
from bean import *

from DBClient import DBClient
from utils import *
import tushare as ts
import numpy
from cache import *
import requests
import json
import pandas
import time

class DailyStockCheckTask(Task):
    logger = logging.getLogger("mainModule.DailyStockCheckTask")

    def __init__(self, startTime=0, period=60, repeat=0, name="DailyStockCheckTask"):
        # 继承父类的构造方法，也可以写成：super(Chinese,self).__init__(name,age)
        Task.__init__(self, startTime, period, repeat, name)
        # 获取上次执行时间
        mc = DBClient()
        record = mc.select_one('select * from task_record where id=%s', (2))
        self.lastTime = record[1].get("last_action_time")
        mc.close()
        pass


    def action(self):
        """[summary]
        执行基础数据补全的任务，每天执行一次或启动时执行
        如果抓取数据期间被安全策略封禁，则过5分钟再尝试一次
        
        Returns:
            [type]: [description]
        """
        
        # 当日执行过
        if dayDif(datetime.date.today(), self.lastTime) <= 0:
            self.logger.info("exec failed! last action time:", self.lastTime, " now:", datetime.date.today())
            return

        block = False
         # 每次更新重新读库保证数据一致
        dicStock.reload()

        try:
            mc = DBClient()
           
            pd = dicStock.data

            visiturl = 0
            
            for index in pd.index:
                
              
                                    
                #比较数据是否今天更新过
                if dayDif(datetime.datetime.now(), pd.at[index,"last_update_time"]) <= 0:
                    self.logger.debug(pd.at[index,"stock_code"]+" update in "+ str(pd.at[index,"last_update_time"]))
                    continue
                
                
                # 根据股票id补全每日股票数据
                stockcode = pd.loc[index]["stock_code"]
                url = getHistoryUrls(stockcode)
                print(url)
                response = requests.get(url)
                #访问网址计数
                visiturl = visiturl + 1
                                
                if response.status_code != 200:
                    self.logger.debug(url+" visit error："+ str(response.status_code))
                    if response.status_code == 456:
                        block = True
                        #后续触发稍后再实验一次的动作
                        break
                    continue
                
                #异常判定
                if len(response.text) < 20:
                    continue
                
                content = json.loads(response.text)
                
                stockDays = {}
                # 汇总所有当日数据
                for record in content:
                    # print(record)
                    day = getDate(record['day'])
                    if day not in stockDays:
                        stockDays[day] = StockToday(stockcode, day)
                    stockDays[day].appendRecord(record)
                    
                # 清洗当日数据并落库
                keys = list(stockDays.keys())
                keys.sort(reverse=True)
                for key in keys:
                    existData = mc.select_one(
                        'select * from stock_data_daily where stock_code=%s and record_time=%s', (stockcode, key))
                    # 如果已经存在某个股票的当日记录，不再继续
                    if existData[0] > 0:
                        break

                    record = stockDays[key]
                    record.calc()
                    sql = self.db_insertsql(record.code, record.day, record.open, record.close,
                                            record.high, record.low, record.volume, 0, 0, 0, 0, 0, 0, 0, 0, 0)
                    mc.execute(sql)
                    pass

                # 更新最新数据，同时更新股票的最后刷新时间
                pd.at[index,"last_update_time"] = pandas.Timestamp(datetime.datetime.now())
                sql = "update dic_stock set last_update_time= '"+ datetime.datetime.strftime(datetime.datetime.now(),'%Y-%m-%d %H:%M:%S') +"' where stock_code='"+stockcode+"';"
                mc.execute(sql)
                mc.commit()
                
                #追加执行n次之后停30秒看看多长时间封禁(目前233，之前一次最多111)
                if (index+1) % 50 == 0:
                    time.sleep(60)
                
                
                pass
        except Exception as ex:
            print(ex)
            mc.rollback()
            return False
        finally:
            mc.close()
            pass

        return True



    # 上次统计20201030日最后
    def db_insertsql(self, stock_code, record_time, open, close, high, low, volume, price_change, p_change, ma5, ma10, ma20, v_ma5, v_ma10, v_ma20, turnover):  # 返回的是插入语句
        sql_temp = '''
            insert into stock_data_daily (stock_code,record_time,open,close,high,low,volume,price_change,p_change,
            ma5,ma10,ma20,v_ma5,v_ma10,v_ma20,turnover) values (
            '''+"\'"+stock_code+"\',\'"+record_time+"\',"+numpy.str(open)+","+numpy.str(close)+","+numpy.str(high)+","+numpy.str(low)+","+numpy.str(volume)+","+numpy.str(price_change)+","+numpy.str(p_change)+","+numpy.str(ma5)+","+numpy.str(ma10)+","+numpy.str(ma20)+","+numpy.str(v_ma5)+","+numpy.str(v_ma10)+","+numpy.str(v_ma20)+","+numpy.str(turnover)+");"

        # print(sql_temp)
        return sql_temp


if __name__ == '__main__':
    t = DailyStockCheckTask()
    t.action()
    print('股票策略version1.0 start')
