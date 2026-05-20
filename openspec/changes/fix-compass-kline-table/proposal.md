# Proposal: Fix compass kline Data Table Missing

## Summary

The `stock_analysis_system.kline` table does not exist on this server's MySQL, causing the compass pipeline daemon to fail on every run.

## Motivation

The compass pipeline daemon (`scripts/pipeline.py --mode daemon`) is running but failing because the `kline` table is missing. It consumes ~129 MB RSS but produces no useful output.

## Implementation

1. **Schema Discovery**: Search the compass project for kline model/ORM definitions or INSERT statements:
   ```bash
   grep -rn "kline" compass/models/ scripts/pipeline.py
   find . -name "*.sql" | xargs grep -l kline
   ```

2. **Create Table**: Execute DDL on MySQL:
   ```sql
   USE stock_analysis_system;
   CREATE TABLE IF NOT EXISTS kline (...)
   ```
   Schema must match what pipeline.py expects.

3. **Restart Pipeline Daemon**:
   ```bash
   kill $(pgrep -f "pipeline.py --mode daemon")
   cd /home/ecs-assist-user/d8q-intelligentengine-stockcompass
   nohup venv/bin/python scripts/pipeline.py --mode daemon >> /var/log/d8q/compass-pipeline.log 2>&1 &
   ```

4. **Verify**: Check logs for successful processing.

## Expected Behavior
- kline table exists
- Pipeline daemon processes data successfully
- No more "Table doesn't exist" errors

## Constraints
- Scope: project=compass
- MySQL access: `mysql -u root` (systemctl managed)
- Do NOT modify pipeline.py logic
