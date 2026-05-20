# Design: Fix Pipeline Daemon DB Connection Recovery

## Problem Analysis

The proposal referenced a missing `kline` table, but investigation reveals:

1. **No `kline` table exists in code or is needed.** The pipeline writes to `stock_data_daily`
   (which exists with 2.96M rows). The function is named `save_kline_data()` but the target
   table is `stock_data_daily`.
2. **The real issue is stale DB connections.** The daemon started May 19, MySQL restarted
   May 20, and the `DBClient._pool` (PooledDB singleton) holds dead connections that
   fail with `Connection refused`.
3. **Two daemon PIDs exist** (1137155 and 1137477), both started May 19 and both unable
   to connect.

## Architecture Decision

### DBClient Pool Auto-Recovery

**Decision**: Add connection failure detection to `buy/DBClient.__get_conn()` that resets
the shared pool when MySQL is unreachable.

**Rationale**: The `DBClient` uses a class-level `_pool` singleton. When MySQL restarts,
all cached connections in the pool become invalid. Setting `_pool = None` forces a fresh
pool creation on the next `DBClient()` instantiation.

**Change**:
```python
# In buy/DBClient.__get_conn():
def __get_conn(self):
    try:
        self._conn = DBClient._pool.connection()
        self._conn.ping(reconnect=True)
        self._cursor = self._conn.cursor()
        DBClient._last_error = None
    except (pymysql.OperationalError, ConnectionRefusedError) as e:
        DBClient._last_error = str(e)
        DBClient._pool = None  # Force pool recreation
        raise
```

### Daemon Restart Script

**Decision**: Create `scripts/restart_pipeline.sh` as a single command to kill all daemon
processes and start a fresh one.

**Rationale**: Eliminates the need for operators to manually find PIDs and construct the
`nohup` command. The existing init scripts (`init_full.sh`) don't cover daemon restart.

## Data Flow (unchanged)

```
APScheduler cron (16:30 daily)
  → run_daily()
    → for each stock:
      → fetch_kline_daily() → akshare API
      → save_kline_data() → stock_data_daily (REPLACE INTO)
      → calc_and_save_indicators() → indicators_daily (REPLACE INTO)
      → analyze_and_save() → stock_analysis (INSERT ON DUPLICATE KEY UPDATE)
    → trigger strategy scanner
```

## Files to Modify

| File | Change |
|------|--------|
| `buy/DBClient.py` | Add pool auto-reset on connection failure in `__get_conn()` |
| `scripts/restart_pipeline.sh` | **New file** — daemon restart script |

## Files NOT Modified

- `scripts/pipeline.py` — per proposal constraint "Do NOT modify pipeline.py logic"
- `scripts/pipeline_db.py` — no changes needed
- `scripts/pipeline_config.py` — no changes needed

## Verification

1. After restarting the daemon, check logs for successful cron trigger
2. Run `mysql -u root -p'password' -e "SELECT COUNT(*) FROM stock_analysis_system.stock_data_daily"`
3. Verify no connection errors in `/var/log/d8q/datapipeline.log`
