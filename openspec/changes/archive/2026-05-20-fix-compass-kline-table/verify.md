Verdict: PASS

Completeness: ✓ All three spec requirements are implemented — DBClient pool auto-reset on OperationalError/ConnectionRefusedError (buy/DBClient.py), restart script (scripts/restart_pipeline.sh), and comprehensive test coverage (tests/test_dbclient_pool.py with 4 test classes covering pool reset, error recording, pool recreation after reset, and generic-error non-reset).

Correctness: ✓ The `__get_conn()` handler correctly catches `(pymysql.OperationalError, ConnectionRefusedError)` before the generic `Exception` handler, sets `_pool = None` to force fresh pool creation, records `_last_error`, and re-raises so callers see the failure. The restart script kills all daemon PIDs via `pgrep -f`, waits 2 seconds, starts a fresh nohup daemon, and verifies the new PID is alive. Both match the design spec exactly.

Coherence: ✓ The pool-reset is placed at the correct layer (DBClient.__get_conn) where connections are acquired, ensuring any stale pool is invalidated before the next instantiation recreates it. The ordering of except clauses (specific DB errors first, generic Exception second) is correct and verified by `test_pool_not_reset_on_generic_error`. The restart script logs actions and exits non-zero on failure.

Issues:
  1. [WARNING] The spec mentions retry logic (up to 3 attempts with backoff) for transient failures during a running job, but the implementation does not add retry logic — it only resets the pool. This is acceptable because the design doc explicitly chose pool-reset-only (no retry at DBClient level), and the daemon's per-stock error handling in pipeline.py (which was not modified per design constraint) provides the necessary resilience at the job level.
