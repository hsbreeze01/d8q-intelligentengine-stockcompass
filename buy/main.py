#!/usr/bin/python
# -*- encoding: utf-8 -*-

"""
Description: 
Version: 1.0
Autor: Sam Zhu
Date: 2020-12-19 23:00:46
LastEditTime: 2021-01-02 14:34:40
""" 

import sys 
import os

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
path = os.path.split(rootPath)[0]
print(curPath,rootPath,path)

sys.path.append(path) # 这句是为了导入_config
sys.path.append(rootPath)

import logging
logger = logging.getLogger("mainModule")
logger.setLevel(level = logging.DEBUG)

handler = logging.FileHandler("log.txt")
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
 
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
console.setFormatter(formatter)
 
logger.addHandler(handler)
logger.addHandler(console)

logger.info("creating an instance of subModule.subModuleClass")

import time
import schedule #pip install schedule
import threading

from Config import taskConfig as config
from DBClient import *
from task import *

def job(name='sf'):
    localtime = time.localtime(time.time())
    print(name,localtime)

def run_threaded(job_func):
     job_thread = threading.Thread(target=job_func)
     job_thread.start()

def job2():
    mc = DBClient()
    # time.sleep(5)
    sql1 = 'SELECT * FROM dic_stock'
    c,b = mc.select_one(sql1)
    mc.close()
    print(b)    

def main():
    """
    分析策略虚拟盘的启动入口
    """
    print(config.getBaseSchedule())

    

    #启动第一次手动进行基础股票信息检查（股票基础信息接口被屏蔽暂时不用）
    #task = BaseStockCheckTask()
    #task.action()

    #补全股票每日基础数据
    task = DailyStockCheckTask()
    task.action()

    #当前股票信息
    # task = CurrentStockTask()
    # task.action()

    # schedule.every(10).seconds.do(run_threaded,job)
    # schedule.every(5).seconds.do(run_threaded,job)
    

    #TODO 考虑是否需要一个库来记录所有事件执行的状态（最简单每次都从颗粒度最小的数据来进行时间判定）

    #检测dic_stock表中的基础数据是否健全(是不是有新的股票可以入池),创建一个任务并手动触发
    
    # BaseStockCheckTask.action()
    # logger.info("base stock checked!")

    # #检查股票的信息是不是最新的（不用计算是否为开盘日，只要知道每个股票最后一天的记录然后调用接口补全即可） TODO 考虑是否中间会有空数据
    # StockRecordTask.action()
    # logger.info("data checked!")


    # #股票分析数据是否所有都已经更新到最新
    # Analysis.action()
    # logger.info("analysis checked!")

    # #1.构造一个定时任务执行器（找是否有合适的任务框架可以直接用）
    # #2.添加可执行事件进去
    # #3.可执行事件
    # createJob(BaseStockCheckTask)#每天凌晨3点执行
    # createJob(StockRecordTask)#每天收盘后下午5点执行，如果当天执行完成则不再执行，注意不用多线程（否则会被外部接口屏蔽）
    # createJob(Analysis)#每天收盘数据获取后重新生成指标 #TODO 如果盘中监测一直在执行，还有必要清理掉重新计算吗？还是说只重新计算并check即可？

    # logger.info("task created!")
    # ###################################### 基础数据检测和每日任务创建结束#################################################
    # logger.info("start daily action!")
    # while(True):
    #     # checkAllJob()
    #     schedule.run_pending()
    #     time.sleep(20)
    #     print('123')


    logger.info("exit!")
    pass

if __name__ == '__main__':
    main()