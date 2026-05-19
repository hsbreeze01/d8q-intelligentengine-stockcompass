# Proposal: Refactor stockfetch/db_bias.py: Make BIASDaily inherit from stockfetch.db_base.StockDBBase. Remove raw pymysql.connect() calls, remove manual conn.close(), eliminate SQL string concatenation. All database methods should use the base class query helpers (_query_one, _query_all, _execute_many) with parameterized queries and context manager (with self: ...). Keep the same public interface (constructor takes code, methods: db_get_maxdate, getData, insert).

## Summary
Refactor stockfetch/db_bias.py: Make BIASDaily inherit from stockfetch.db_base.StockDBBase. Remove raw pymysql.connect() calls, remove manual conn.close(), eliminate SQL string concatenation. All database methods should use the base class query helpers (_query_one, _query_all, _execute_many) with parameterized queries and context manager (with self: ...). Keep the same public interface (constructor takes code, methods: db_get_maxdate, getData, insert).

## Motivation

## Expected Behavior

