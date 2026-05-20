# Delta Spec: Pipeline Daemon DB Connection Recovery

## ADDED Requirements

### Requirement: Pipeline daemon SHALL recover from transient MySQL outages

The pipeline daemon runs via APScheduler in `--mode daemon`. When MySQL restarts or the
connection is temporarily lost, the daemon's DBClient connection pool becomes stale and
all subsequent scheduled jobs fail with `OperationalError: Connection refused`.

The system SHALL survive MySQL restarts without manual intervention.

#### Scenario: MySQL restarts while daemon is idle (between cron runs)

- **Given** the pipeline daemon is running in `--mode daemon`
- **And** the APScheduler cron job has not yet triggered for the day
- **When** MySQL is restarted (systemctl restart mysqld)
- **And** the cron job triggers after MySQL is back online
- **Then** the job SHALL successfully connect to MySQL
- **And** `run_daily()` SHALL process stocks normally
- **And** the log SHALL show "DAILY MODE START" followed by successful stock processing

#### Scenario: MySQL is briefly unavailable during a running job

- **Given** the pipeline daemon is processing stocks in `run_daily()`
- **When** a DBClient connection attempt fails with `OperationalError` or `ConnectionRefusedError`
- **Then** the system SHALL retry the connection (up to 3 attempts with backoff)
- **And** the individual stock SHALL be logged as failed (not crash the daemon)
- **And** the daemon SHALL continue processing remaining stocks

### Requirement: DBClient connection pool SHALL auto-reset on persistent failures

The `buy/DBClient.py` `PooledDB` singleton (`DBClient._pool`) caches connections that
become stale when MySQL restarts. The pool SHALL be reset when a connection failure is
detected so subsequent requests create fresh connections.

#### Scenario: Stale pool detects connection failure

- **Given** `DBClient._pool` is initialized with connections to MySQL
- **When** `__get_conn()` raises `OperationalError` with errno 2003 or 2006
- **Then** `DBClient._pool` SHALL be set to `None`
- **And** the next `DBClient()` instantiation SHALL create a fresh pool
- **And** `DBClient._last_error` SHALL be updated with the error message

### Requirement: Pipeline daemon process SHALL be restartable via a single command

The ops team MUST be able to restart the pipeline daemon without manually finding
and killing PIDs.

#### Scenario: Operator restarts the daemon

- **Given** one or more pipeline daemon processes are running
- **When** the operator runs the restart command
- **Then** all existing daemon processes SHALL be terminated
- **And** exactly one new daemon process SHALL be started
- **And** the new process SHALL write logs to `/var/log/d8q/datapipeline.log`
