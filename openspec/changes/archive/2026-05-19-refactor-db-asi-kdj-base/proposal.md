# Proposal: Refactor two remaining stockfetch indicator modules to inherit from stockfetch.db_base.StockDBBase:
1. stockfetch/db_asi.py — ASIDaily class
2. stockfetch/db_kdj.py — KDJDaily class

Same pattern as all other already-refactored db_*.py files:
- Inherit from StockDBBase
- Constructor takes code + **db_kwargs, calls super().__init__(**db_kwargs)
- Use 'with self:' context manager for all DB operations
- Use _query_one, _query_all, _execute_many with parameterized queries
- Keep the same public interface (db_get_maxdate, getData, insert)

## Summary
Refactor two remaining stockfetch indicator modules to inherit from stockfetch.db_base.StockDBBase:
1. stockfetch/db_asi.py — ASIDaily class
2. stockfetch/db_kdj.py — KDJDaily class

Same pattern as all other already-refactored db_*.py files:
- Inherit from StockDBBase
- Constructor takes code + **db_kwargs, calls super().__init__(**db_kwargs)
- Use 'with self:' context manager for all DB operations
- Use _query_one, _query_all, _execute_many with parameterized queries
- Keep the same public interface (db_get_maxdate, getData, insert)

## Motivation

## Expected Behavior

