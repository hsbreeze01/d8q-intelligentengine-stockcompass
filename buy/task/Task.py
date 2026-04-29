#!/usr/bin/python
# -*- encoding: utf-8 -*-

"""
Description: 
Version: 1.0
Autor: Sam Zhu
Date: 2020-12-19 23:08:03
LastEditTime: 2020-12-27 17:39:12
""" 

import logging
import time

class Task(object):
    logger = logging.getLogger("mainModule.Task")
    totalTask = 0
    
    '''
    description: 
    param {*} self
    param {*} startTime 任务开始时间 tick=0 表示启动就开始 ,单位秒
    param {*} period 任务间隔时间秒
    param {*} repeat 重复次数，默认0为无限
    param {*} name 任务的名称
    return {*}
    '''
    def __init__(self,startTime = 0,period=60,repeat= 0,name=""):
        self.name = name
        Task.totalTask += 1
        self.id = Task.totalTask
        self.actionTimes = 0
        self.repeat = repeat
        self.nextTime = startTime
        pass    

    #执行任务
    def run(self):
        #时间有效期检测
        if self.nextTime < time.time():
            return False

        #已经超过执行次数的上限
        if self.repeat > 0 and self.actionTimes > self.repeat:
            Task.logger.debug("self.repeat=",self.repeat," current:",self.actionTimes)
            return False
        
        #任务自定义预检测
        if not self.check():
            return False
        
        #任务执行不论成功失败都执行次数
        try:
            result = self.action()
        except Exception as e:
            Task.logger.error(e)
            pass

        Task.logger.debug(result)

        #记录执行次数和下次执行时间
        self.actionTimes += 1
        self.nextTime += self.period

        return True

    #任务执行前特殊条件检测
    def check(self):
        return True


    def action(self):
        """
        按照策略执行并存盘
        """
        raise NotImplementedError
        pass

    
  