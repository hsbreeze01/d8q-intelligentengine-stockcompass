# Proposal: Refactor three stockfetch indicator modules to inherit from stockfetch.db_base.StockDBBase:
1. stockfetch/db_boll.py — BOLLDaily class
2. stockfetch/db_vr.py — VRDaily class
3. stockfetch/db_wr.py — WRDaily class

Same pattern as already-refactored db_bias.py, db_ma.py, db_macd.py, db_rsi.py:
- Inherit from StockDBBase
- Constructor takes code + **db_kwargs, calls super().__init__(**db_kwargs)
- Use 'with self:' context manager for all DB operations
- Use _query_one, _query_all, _execute_many with parameterized queries
- Keep the same public interface (db_get_maxdate, getData, insert)

## Summary
Refactor three stockfetch indicator modules to inherit from stockfetch.db_base.StockDBBase:
1. stockfetch/db_boll.py — BOLLDaily class
2. stockfetch/db_vr.py — VRDaily class
3. stockfetch/db_wr.py — WRDaily class

Same pattern as already-refactored db_bias.py, db_ma.py, db_macd.py, db_rsi.py:
- Inherit from StockDBBase
- Constructor takes code + **db_kwargs, calls super().__init__(**db_kwargs)
- Use 'with self:' context manager for all DB operations
- Use _query_one, _query_all, _execute_many with parameterized queries
- Keep the same public interface (db_get_maxdate, getData, insert)

## Motivation

## Expected Behavior

