#! /usr/bin/python
# -*- coding: utf-8 -*-

import logging
import yaml #pip3 install pyyaml
import os

class TaskConfig(object):
    """
    docstring
    """
    log = logging.getLogger("my_logger")

    def __init__(self):
        self.env = os.getenv('DevENV', 'dev')

        print(f"Environment: {self.env}")
        if self.env == 'prod':
            file="config/config_prod.yaml"
        elif self.env == 'stg':
            file="config/config_stg.yaml"
        else:
            file="config/config_dev.yaml"

        curPath = os.path.dirname(os.path.realpath(__file__)) # 获取当前脚本所在文件夹路径
        ymlPath = os.path.join(curPath, file) # 获取yaml文件路径
        # 用open方法打开直接读取
        f = open(ymlPath, 'r')
        cfg = f.read()
        self.log.info(type(cfg)) # 读取的结果是 字符串
        self.log.info(cfg)

        self.config = yaml.load(cfg,yaml.FullLoader) # 用load方法转字典
        self.log.info(self.config)
        pass    
    pass

    def __getProperty(self, name):
        return self.config.get(name)

    def getDBconnection(self):
        return self.__getProperty("DBConnection")

    def getBaseSchedule(self):
        return self.__getProperty("baseAction")

    def getStrategySchedule(self):
        return self.__getProperty("strategyAction")
    
    def getCloseSchedule(self):
        return self.__getProperty("closeAction")
    
    def getHost(self):
        return self.__getProperty("host")
    
    def getWx(self):
        return self.__getProperty("wx")
    
    def getEnv(self):
        return self.env

taskConfig = TaskConfig()

if __name__ == '__main__':
    print(taskConfig.getHost()['port'])
    print(taskConfig.getEnv())