# Proposal: Refactor scripts/fetch_valuation.py: Replace all raw pymysql.connect() with the existing DBClient connection pool from buy/DBClient.py. Wrap all database operations in try/finally to ensure connections are always closed even on exceptions. Use parameterized queries instead of string formatting. Key changes:
1. get_db() should return a DBClient() instance instead of raw pymysql.connect()
2. All conn = get_db() should be in try/finally: finally: conn.close()
3. All cursor.execute() should use %s parameterized queries
4. In fetch_market_pe/fetch_market_pb, use try/finally for conn lifecycle
5. In fetch_individual_batch, keep single connection for the batch but add try/finally
6. Keep the same public interface and behavior

## Summary
Refactor scripts/fetch_valuation.py: Replace all raw pymysql.connect() with the existing DBClient connection pool from buy/DBClient.py. Wrap all database operations in try/finally to ensure connections are always closed even on exceptions. Use parameterized queries instead of string formatting. Key changes:
1. get_db() should return a DBClient() instance instead of raw pymysql.connect()
2. All conn = get_db() should be in try/finally: finally: conn.close()
3. All cursor.execute() should use %s parameterized queries
4. In fetch_market_pe/fetch_market_pb, use try/finally for conn lifecycle
5. In fetch_individual_batch, keep single connection for the batch but add try/finally
6. Keep the same public interface and behavior

## Motivation

## Expected Behavior

