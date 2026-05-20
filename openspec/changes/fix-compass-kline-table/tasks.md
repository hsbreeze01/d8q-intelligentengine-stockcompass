# Tasks: Fix Pipeline Daemon DB Connection Recovery

## 1. Database & Infrastructure Verification

- [x] Verify all pipeline tables exist and are accessible (`stock_basic`, `stock_data_daily`, `indicators_daily`, `stock_analysis`, `dic_stock`) and confirm MySQL is running on port 3306

## 2. DBClient Connection Pool Recovery

- [x] Modify `buy/DBClient.py` `__get_conn()` to reset `DBClient._pool = None` when catching `OperationalError` (errno 2003/2006) or `ConnectionRefusedError`, forcing fresh pool creation on next instantiation

## 3. Daemon Restart & Verification

- [x] Create `scripts/restart_pipeline.sh` that kills all existing `pipeline.py --mode daemon` processes, waits 2 seconds, and starts a fresh daemon process with nohup logging to `/var/log/d8q/datapipeline.log`
- [x] Execute the restart script, wait 30 seconds, then verify the daemon is running (single PID), logs show no connection errors, and MySQL queries succeed
