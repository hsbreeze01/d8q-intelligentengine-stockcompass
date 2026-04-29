#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
Description: 
Version: 1.0
Autor: Sam Zhu
Date: 2020-12-27 18:54:01
LastEditTime: 2020-12-27 18:54:02
""" 
"""
使用DBUtils数据库连接池中的连接，操作数据库
OperationalError: (2006, ‘MySQL server has gone away’)
"""

import json
import pymysql
import datetime
from dbutils.pooled_db import PooledDB
import pymysql
import logging
import threading
from .Config import taskConfig as config

class DBClient(object):
    __pool = None
    _connection_count = 0  # Add counter
    lock = threading.Lock()
    log = logging.getLogger("my_logger")

    def __init__(self, mincached=10, maxcached=20, maxshared=10, maxconnections=100, blocking=True,
                 maxusage=0, setsession=None, reset=True,
                 host=config.getDBconnection()['host'], port=config.getDBconnection()['port'], db=config.getDBconnection()['database'],
                 user=config.getDBconnection()['user'], passwd=config.getDBconnection()['password'], charset='utf8mb4'):
        
        """
        :param mincached:连接池中空闲连接的初始数量
        :param maxcached:连接池中空闲连接的最大数量
        :param maxshared:共享连接的最大数量
        :param maxconnections:创建连接池的最大数量
        :param blocking:超过最大连接数量时候的表现，为True等待连接数量下降，为false直接报错处理
        :param maxusage:单个连接的最大重复使用次数
        :param setsession:optional list of SQL commands that may serve to prepare
            the session, e.g. ["set datestyle to ...", "set time zone ..."]
        :param reset:how connections should be reset when returned to the pool
            (False or None to rollback transcations started with begin(),
            True to always issue a rollback for safety's sake)
        :param host:数据库ip地址
        :param port:数据库端口
        :param db:库名
        :param user:用户名
        :param passwd:密码
        :param charset:字符编码
        """
        with DBClient.lock:
            DBClient._connection_count += 1
            # self.log.debug(f"Connection opened. Total connections: {DBClient._connection_count}")

        #python的查找顺序是子类->父类->类，因此下面的代码如果第2次初始化其实self.__pool是没有的，会找类的.__pool属性
        # self.log.debug("=======================================init 0")
        if not self.__pool:
            # self.log.debug("=======================================init 1")

            DBClient.lock.acquire()
            # self.log.debug("=======================================init 2")

            if not self.__pool:
                # self.log.debug("=======================================init 3")
                self.log.debug(f"mincached: {mincached}, maxcached: {maxcached}, maxshared: {maxshared}, maxconnections: {maxconnections}, blocking: {blocking}, maxusage: {maxusage}, setsession: {setsession}, reset: {reset}, host: {host}, port: {port}, db: {db}, user: {user}, passwd: {passwd}, charset: {charset}")
                self.__class__.__pool = PooledDB(pymysql,
                                                mincached, maxcached,
                                                maxshared, maxconnections, blocking,
                                                maxusage, setsession, reset,
                                                host=host, port=port, db=db,
                                                user=user, passwd=passwd,
                                                charset=charset,
                                                cursorclass=pymysql.cursors.DictCursor
                                                )
                # self.log.debug("=======================================init 4")
                
            DBClient.lock.release()
            # self.log.debug("=======================================init 5")

        # self.log.debug("=======================================init 6")

        self._conn = None
        self._cursor = None
        self.__get_conn()
        # self.log.debug("=======================================init 7")

    @classmethod
    def get_connection_count(cls):
        return cls._connection_count

    def __get_conn(self):
        # self.log.debug("=======================================init conn")
        self._conn = self.__pool.connection()
        # self.log.debug("=======================================init conn done")
        self._cursor = self._conn.cursor()

    def close(self):
        # try:
        #     self._cursor.close()
        #     self._conn.close()
        # except Exception as e:
        #     # DBFactory.log.error(e)
        #     self.log.debug(e)
        
        with DBClient.lock:
            if hasattr(self, '_conn') and self._conn:
                self._cursor.close()
                self._conn.close()
                DBClient._connection_count -= 1
                # self.log.debug(f"Connection closed. Total connections: {DBClient._connection_count}")

    def __execute(self, sql, param=()):
        count = self._cursor.execute(sql, param)
        return count

    @staticmethod
    def __dict_datetime_obj_to_str(result_dict):
        """把字典里面的datatime对象转成字符串，使json转换不出错"""
        if result_dict:
            result_replace = {k: v.__str__() for k, v in result_dict.items() if isinstance(v, datetime.datetime)}
            result_dict.update(result_replace)
        return result_dict

    def select_one(self, sql, param=()):
        """查询单个结果"""
        count = self.__execute(sql, param)
        result = self._cursor.fetchone()
        """:type result:dict"""
        # result = self.__dict_datetime_obj_to_str(result)
        return count, result

    def select_many(self, sql, param=()):
        """
        查询多个结果
        :param sql: qsl语句
        :param param: sql参数
        :return: 结果数量和查询结果集
        """
        count = self.__execute(sql, param)
        result = self._cursor.fetchall()
        """:type result:list"""
        # [self.__dict_datetime_obj_to_str(row_dict) for row_dict in result]/
        return count, result
    
    def select_many_cols(self, sql, param=()):
        """
        查询多个结果
        :param sql: qsl语句
        :param param: sql参数
        :return: 结果数量和查询结果集和列
        """
        count = self.__execute(sql, param)
        result = self._cursor.fetchall()
        dataframe_cols=[tuple[0] for tuple in self._cursor.description]#列名和数据库列一致
        """:type result:list"""
        # [self.__dict_datetime_obj_to_str(row_dict) for row_dict in result]/
        return count, result,dataframe_cols
    
    def execute(self, sql, param=()):
        count = self.__execute(sql, param)
        id = self._cursor.lastrowid
        return count,id

    def commit(self):
        self._conn.commit()
    
    def rollback(self):
        self._conn.rollback()


if __name__ == "__main__":
    mc = DBClient()

    # sql1 = 'SELECT * FROM dic_stock'
    # c,b = mc.select_one(sql1)
    # print(b)

    # sql2 = 'SELECT * FROM dic_stock  WHERE  id IN (%s,%s,%s)'
    # param = (2, 3, 4)

    # result = mc.select_many(sql2, param)

    for index in range(500):
        sql3 = 'replace into param (id,name) values(%s,%s)'
        param = (index,'insert322222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222222'+str(index))
        result = mc.execute(sql3,param)
        print(result)
        # if(index %2 == 0):
        #     mc.rollback()
        # else:
        #     mc.commit()
        pass

    mc.commit()
    mc.close()
    