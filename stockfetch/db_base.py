"""Unified database base class for the stockfetch subsystem.

Provides a process-wide PooledDB connection pool with context-manager
and explicit open/close lifecycle support.
"""
import logging
import threading

import pymysql
from dbutils.pooled_db import PooledDB

logger = logging.getLogger("stockfetch.db_base")


class StockDBBase:
    """Reusable database access foundation with class-level connection pool.

    The pool is initialised lazily on first instantiation using parameters
    from ``buy/Config.py`` (``taskConfig.getDBconnection()``) unless
    explicit keyword arguments are supplied.

    Supports both ``with`` statement and explicit ``open()`` / ``close()``.
    """

    __pool: PooledDB | None = None
    _lock = threading.Lock()

    # ------------------------------------------------------------------
    # Construction & pool initialisation
    # ------------------------------------------------------------------

    def __init__(self, **db_kwargs):
        self._conn = None
        self._cursor = None
        self._init_pool(db_kwargs)

    def _init_pool(self, db_kwargs: dict):
        """Ensure the class-level pool exists, then acquire a connection."""
        if self.__class__.__pool is not None:
            return

        with self._lock:
            if self.__class__.__pool is not None:
                return

            params = self._resolve_db_params(db_kwargs)
            self.__class__.__pool = PooledDB(
                pymysql,
                mincached=5,
                maxcached=20,
                maxconnections=100,
                blocking=True,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                **params,
            )
            logger.info(
                "StockDBBase pool initialised: %s:%s/%s",
                params.get("host"),
                params.get("port"),
                params.get("db"),
            )

    @staticmethod
    def _resolve_db_params(db_kwargs: dict) -> dict:
        """Build the keyword dict accepted by PooledDB / pymysql.connect."""
        if db_kwargs:
            return {
                "host": db_kwargs.get("host"),
                "port": db_kwargs.get("port", 3306),
                "user": db_kwargs.get("user"),
                "passwd": db_kwargs.get("passwd") or db_kwargs.get("password"),
                "db": db_kwargs.get("db") or db_kwargs.get("database"),
            }

        # Fallback: read from buy/Config.py
        from buy.Config import taskConfig  # noqa: WPS433 — intentional late import

        cfg = taskConfig.getDBconnection()
        return {
            "host": cfg["host"],
            "port": cfg.get("port", 3306),
            "user": cfg["user"],
            "passwd": cfg["password"],
            "db": cfg["database"],
        }

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self):
        self._acquire_conn()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                self.rollback()
            else:
                self.commit()
        finally:
            self._release_conn()

    # ------------------------------------------------------------------
    # Explicit lifecycle
    # ------------------------------------------------------------------

    def open(self):
        """Explicitly acquire a connection from the pool."""
        self._acquire_conn()

    def close(self):
        """Release the current connection back to the pool (safe to call twice)."""
        self._release_conn()

    # ------------------------------------------------------------------
    # Internal connection helpers
    # ------------------------------------------------------------------

    def _acquire_conn(self):
        if self._conn is None:
            self._conn = self.__class__.__pool.connection()
            self._cursor = self._conn.cursor()

    def _release_conn(self):
        try:
            if self._cursor is not None:
                self._cursor.close()
        except Exception:
            pass
        self._cursor = None

        try:
            if self._conn is not None:
                self._conn.close()
        except Exception:
            pass
        self._conn = None

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def _ensure_active(self):
        if self._cursor is None or self._conn is None:
            raise RuntimeError("No active database connection. Use 'with' or open() first.")

    def _query_one(self, sql: str, params=()):
        """Execute SELECT and return ``(row_count, row | None)``."""
        self._ensure_active()
        count = self._cursor.execute(sql, params)
        row = self._cursor.fetchone()
        return count, row

    def _query_all(self, sql: str, params=()):
        """Execute SELECT and return ``(row_count, list_of_rows)``."""
        self._ensure_active()
        count = self._cursor.execute(sql, params)
        rows = self._cursor.fetchall()
        return count, rows

    def _execute_many(self, sql: str, params=()):
        """Execute a write statement and return ``(affected_rows, last_row_id)``."""
        self._ensure_active()
        self._cursor.execute(sql, params)
        return self._cursor.rowcount, self._cursor.lastrowid

    # ------------------------------------------------------------------
    # Transaction control
    # ------------------------------------------------------------------

    def commit(self):
        self._ensure_active()
        self._conn.commit()

    def rollback(self):
        self._ensure_active()
        self._conn.rollback()
