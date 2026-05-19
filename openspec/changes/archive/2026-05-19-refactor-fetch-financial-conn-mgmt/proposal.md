# Proposal: Refactor scripts/fetch_financial.py: Replace all raw pymysql.connect() with the existing DBClient connection pool from buy/DBClient.py. Wrap all database operations in try/finally to ensure connections are always closed. Use parameterized queries. Key changes:
1. get_db() should return DBClient() instead of raw pymysql.connect()
2. All conn = get_db() should use try/finally: finally: conn.close()
3. All cursor.execute() should use %s parameterized queries
4. store_profit/store_balance: keep connection lifecycle in try/finally
5. main(): use try/finally for connection lifecycle
6. Keep same public interface and behavior

## Summary
Refactor scripts/fetch_financial.py: Replace all raw pymysql.connect() with the existing DBClient connection pool from buy/DBClient.py. Wrap all database operations in try/finally to ensure connections are always closed. Use parameterized queries. Key changes:
1. get_db() should return DBClient() instead of raw pymysql.connect()
2. All conn = get_db() should use try/finally: finally: conn.close()
3. All cursor.execute() should use %s parameterized queries
4. store_profit/store_balance: keep connection lifecycle in try/finally
5. main(): use try/finally for connection lifecycle
6. Keep same public interface and behavior

## Motivation

## Expected Behavior

