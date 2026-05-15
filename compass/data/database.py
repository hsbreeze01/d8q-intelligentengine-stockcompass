"""数据库连接池 — 基于 DBUtils + PyMySQL"""
import threading
import logging
import datetime

import pymysql
from dbutils.pooled_db import PooledDB

from compass.config import get_config

logger = logging.getLogger("compass.database")


class Database:
    """MySQL 连接池管理器"""

    __pool = None
    _lock = threading.Lock()

    def __init__(self):
        cfg = get_config()
        self._conn = None
        self._cursor = None
        self._init_pool(cfg)

    def _init_pool(self, cfg):
        if self.__class__.__pool is not None:
            self._acquire_conn()
            return

        with self._lock:
            if self.__class__.__pool is not None:
                self._acquire_conn()
                return

            self.__class__.__pool = PooledDB(
                pymysql,
                mincached=cfg.DB_POOL_MIN,
                maxcached=cfg.DB_POOL_MAX,
                maxshared=10,
                maxconnections=100,
                blocking=True,
                maxusage=0,
                setsession=None,
                reset=True,
                ping=1,
                host=cfg.MYSQL_HOST,
                port=cfg.MYSQL_PORT,
                db=cfg.MYSQL_DATABASE,
                user=cfg.MYSQL_USER,
                passwd=cfg.MYSQL_PASSWORD,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
            )
            logger.info("DB pool initialized: %s:%s/%s", cfg.MYSQL_HOST, cfg.MYSQL_PORT, cfg.MYSQL_DATABASE)
            self._acquire_conn()

    def _acquire_conn(self):
        self._conn = self.__pool.connection()
        self._cursor = self._conn.cursor()

    def close(self):
        try:
            if self._cursor:
                self._cursor.close()
            if self._conn:
                self._conn.close()
        except Exception:
            pass

    def execute(self, sql, params=()):
        count = self._cursor.execute(sql, params)
        return count, self._cursor.lastrowid

    def select_one(self, sql, params=()):
        count = self._cursor.execute(sql, params)
        result = self._cursor.fetchone()
        return count, result

    def select_many(self, sql, params=()):
        count = self._cursor.execute(sql, params)
        result = self._cursor.fetchall()
        return count, result

    def select_many_cols(self, sql, params=()):
        count = self._cursor.execute(sql, params)
        result = self._cursor.fetchall()
        columns = [col[0] for col in self._cursor.description]
        return count, result, columns

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
