# Proposal: Fix buy/DBClient.py with three improvements:
1. Fix the DCL (double-checked locking) name mangling bug: 'self.__pool' uses Python name mangling to '_DBClient__pool' which is DIFFERENT from 'DBClient.__pool' at class level. The current code sets self.__pool in __init__ which may not correctly check/set the class-level pool. Fix to use explicit 'DBClient._DBClient__pool is None' checks consistently.
2. Add conn.ping(reconnect=True) in __get_conn() so stale MySQL connections are automatically reconnected.
3. Add a classmethod pool_status() that returns a dict with pool status: {status: 'active'|'not_initialized', connection_count: N}
Keep the same public interface (select_one, select_many, select_many_cols, execute, commit, rollback, close).

## Summary
Fix buy/DBClient.py with three improvements:
1. Fix the DCL (double-checked locking) name mangling bug: 'self.__pool' uses Python name mangling to '_DBClient__pool' which is DIFFERENT from 'DBClient.__pool' at class level. The current code sets self.__pool in __init__ which may not correctly check/set the class-level pool. Fix to use explicit 'DBClient._DBClient__pool is None' checks consistently.
2. Add conn.ping(reconnect=True) in __get_conn() so stale MySQL connections are automatically reconnected.
3. Add a classmethod pool_status() that returns a dict with pool status: {status: 'active'|'not_initialized', connection_count: N}
Keep the same public interface (select_one, select_many, select_many_cols, execute, commit, rollback, close).

## Motivation

## Expected Behavior

