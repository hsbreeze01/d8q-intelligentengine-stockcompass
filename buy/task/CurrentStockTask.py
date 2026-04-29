#!/usr/bin/python
# -*- encoding: utf-8 -*-

"""
Description: 当日最新各个股票的价格（实时数据）
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


class CurrentStockTask(Task):
    logger = logging.getLogger("mainModule.CurrentStockTask")

    def __init__(self, startTime=0, period=60, repeat=0, name="CurrentStockTask"):
        # 继承父类的构造方法，也可以写成：super(Chinese,self).__init__(name,age)
        Task.__init__(self, startTime, period, repeat, name)
        # 获取上次执行时间
        mc = DBClient()
        record = mc.select_one('select * from task_record where id=%s', (3))
        self.lastTime = record[1].get("last_action_time")
        mc.close()
        pass


    def action(self):
        """[summary]
        获取所有股票当前数据
        Returns:
            [type]: [description]
        """
        
        # 当日执行过
        if dayDif(datetime.date.today(), self.lastTime) <= 0:
            self.logger.info("exec failed! last action time:", self.lastTime, " now:", datetime.date.today())
            return

        urls = getCurrentUrls(50)
        
        count = 0
        
        mc = DBClient()
        #每次执行先清理当日临时表
        mc.execute("truncate table stock_today")
         
        try:
            for url in urls:
                response = requests.get(url)
                if response.status_code != 200:
                    self.logger.debug(url+" visit error："+ str(response.status_code))
                    if response.status_code == 456:
                        block = True
                        #后续触发稍后再实验一次的动作
                        break
                    continue

                content = json.loads(response.text)
                for record in content:
                    print(record)
                    sql = self.db_insertsql(record['code'],record['ticktime'], record['open'], record['trade'],
                                                    record['high'], record['low'], record['volume'], record['amount'], record['turnoverratio'])
                    print(sql)
                    mc.execute(sql)
            
            mc.commit()
        except Exception as ex:
            print(ex)
            mc.rollback()
            return False
        finally:
            mc.close()
            pass 
                
        return True



    # 上次统计20201030日最后
    def db_insertsql(self, stock_code, record_time, open, trade, high, low, volume,amount,turnoverratio):  # 返回的是插入语句
        sql_temp = '''
            insert into stock_today (stock_code,tick_time,open,trade,high,low,volume,amount,turnoverratio,
            update_date) values (
            '''+"\'"+stock_code+"\',\'"+record_time+"\',"+numpy.str(open)+","+numpy.str(trade)+","+numpy.str(high)+","+numpy.str(low)+","+numpy.str(volume)+","+numpy.str(amount)+","+numpy.str(turnoverratio)+",now());"

        return sql_temp
    

if __name__ == '__main__':
    t = CurrentStockTask()
    t.action()
    print('股票策略version1.0 start')
