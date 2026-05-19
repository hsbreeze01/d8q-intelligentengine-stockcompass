# Proposal: Refactor three stockfetch indicator modules to inherit from stockfetch.db_base.StockDBBase:
1. stockfetch/db_ma.py — MADaily class: remove raw pymysql.connect(), manual conn.close(), SQL string concatenation. Use parameterized queries via base class helpers.
2. stockfetch/db_macd.py — MACDDaily class: same treatment.
3. stockfetch/db_rsi.py — RSIDaily class: same treatment.

Each file follows the same pattern as the already-refactored db_bias.py:
- Inherit from StockDBBase
- Constructor takes code + **db_kwargs, calls super().__init__(**db_kwargs)
- Use 'with self:' context manager for all DB operations
- Use _query_one, _query_all, _execute_many with parameterized queries
- Keep the same public interface (get_conn -> removed, db_disconnect -> removed, db_get_maxdate, getData, insert)

## Summary
Refactor three stockfetch indicator modules to inherit from stockfetch.db_base.StockDBBase:
1. stockfetch/db_ma.py — MADaily class: remove raw pymysql.connect(), manual conn.close(), SQL string concatenation. Use parameterized queries via base class helpers.
2. stockfetch/db_macd.py — MACDDaily class: same treatment.
3. stockfetch/db_rsi.py — RSIDaily class: same treatment.

Each file follows the same pattern as the already-refactored db_bias.py:
- Inherit from StockDBBase
- Constructor takes code + **db_kwargs, calls super().__init__(**db_kwargs)
- Use 'with self:' context manager for all DB operations
- Use _query_one, _query_all, _execute_many with parameterized queries
- Keep the same public interface (get_conn -> removed, db_disconnect -> removed, db_get_maxdate, getData, insert)

## Motivation

## Expected Behavior

