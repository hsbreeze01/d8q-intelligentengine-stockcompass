#!/usr/bin/python
# -*- encoding: utf-8 -*-

"""
Description: 更新股票基础信息
Version: 1.0
Autor: Sam Zhu
Date: 2020-12-19 23:07:10
LastEditTime: 2020-12-27 21:20:53
""" 

import sys 

import logging
from .Task import Task
from ..DBClient import DBClient
from utils import *
import tushare as ts
import numpy
from cache import *

class BaseStockCheckTask(Task):
    logger = logging.getLogger("mainModule.BaseStockCheckTask")
    

    def __init__(self,startTime = 0,period=60,repeat= 0,name="BaseStockCheckTask"):
        Task.__init__(self, startTime,period,repeat,name)  #继承父类的构造方法，也可以写成：super(Chinese,self).__init__(name,age)
        #获取上次执行时间
        mc = DBClient()
        record = mc.select_one('select * from task_record where id=%s',(1))
        self.lastTime = record[1].get("last_action_time")
        mc.close()
        pass    


    def action(self):
        #当日未执行过
        if dayDif(datetime.date.today(),self.lastTime) <= 0:
            self.logger.info("exec failed! last action time:",record[1].get("last_action_time")," now:",datetime.date.today())
            pass
        
        #查找实施基础股票数据
        # pro = ts.pro_api("7a689f4bfe301b0aafb619edd9858d44db3722fc7d0c47725ec0056c")
        # basics_all = pro.stock_basic()
        basics_all = ts.get_stock_basics()
        mc = DBClient()
        
        try:
            for code in basics_all.index:
                if dicStock.isExist(code):
                    BaseStockCheckTask.logger.debug(code," is exist!")
                    continue

                #如果股票代码没找到就插
                mc.execute(self.__db_perstock_insertsql(code,basics_all.loc[code]["name"],
                basics_all.loc[code]["industry"],basics_all.loc[code]["area"],basics_all.loc[code]["pe"],basics_all.loc[code]["outstanding"],basics_all.loc[code]["totals"],basics_all.loc[code]["totalAssets"]))
                pass

            #更新插入时间
            sql = "replace into task_record (id,last_action_time) values(1,now()) "
            mc.execute(sql)
            mc.commit()
            pass
        except Exception as ex:
            BaseStockCheckTask.logger.error(ex)
            mc.rollback()
            return False
        finally:
            mc.close()
            pass

        return True
    
    def __db_perstock_insertsql(self,stock_code,cns_name,industry,area,pe,outstanding,totals,totalAssets):#返回的是插入语句
        sql_temp="insert into dic_stock(stock_code,stock_name,industry,area,pe,outstanding,totals,totalAssets,last_update_time,status) values("
        sql_temp+="\'"+stock_code+"\',\'"+cns_name+"\',\'"+industry+"\',\'"+area+"\',"+numpy.str(pe)+","+numpy.str(outstanding)+","+numpy.str(totals)+","+numpy.str(totalAssets) +", now(),0"
        sql_temp +=");"
        return sql_temp

if __name__ == '__main__':
    t = BaseStockCheckTask()
    t.action()
    print ('股票策略version1.0 start')
