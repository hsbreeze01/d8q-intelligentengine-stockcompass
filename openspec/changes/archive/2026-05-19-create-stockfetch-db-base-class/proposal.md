# Proposal: Create a unified StockDBBase base class in stockfetch/db_base.py that encapsulates PooledDB connection pooling, context manager-based connection lifecycle (_get_conn), parameterized query methods (_query_one, _query_all, _execute_many), and automatic connection cleanup. This class will be the foundation for refactoring all stockfetch/db_*.py modules to eliminate raw pymysql.connect() calls, manual conn.close(), and SQL string concatenation. The base class should use the existing buy/Config.py taskConfig for DB connection parameters and dbutils.pooled_db.PooledDB for connection pooling.

## Summary
Create a unified StockDBBase base class in stockfetch/db_base.py that encapsulates PooledDB connection pooling, context manager-based connection lifecycle (_get_conn), parameterized query methods (_query_one, _query_all, _execute_many), and automatic connection cleanup. This class will be the foundation for refactoring all stockfetch/db_*.py modules to eliminate raw pymysql.connect() calls, manual conn.close(), and SQL string concatenation. The base class should use the existing buy/Config.py taskConfig for DB connection parameters and dbutils.pooled_db.PooledDB for connection pooling.

## Motivation

## Expected Behavior

