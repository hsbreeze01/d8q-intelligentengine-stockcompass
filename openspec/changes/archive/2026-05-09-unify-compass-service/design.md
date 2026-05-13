# Design: Unify Compass Service

## Architecture Decision

**Decision**: Use `d8q-compass.service` as the sole systemd unit for compass, remove `stockcompass.service`.

**Rationale**:
- All other d8q projects follow the `d8q-<name>.service` naming convention (d8q-agent, d8q-factory, d8q-infopublisher, d8q-stockshark).
- `d8q-compass.service` already has proper settings: `PYTHONUNBUFFERED=1`, `StandardOutput/StandardError=journal`.
- The legacy `stockcompass.service` is in a restart loop, indicating it is stale or misconfigured.
- Having two service files for the same application creates ambiguity and risk of port conflicts.

## Execution Plan

This is a pure operations change — **no application code is modified**.

### Steps

1. **Stop & disable legacy service**
   - `systemctl stop stockcompass.service`
   - `systemctl disable stockcompass.service`

2. **Remove legacy unit file**
   - `rm /etc/systemd/system/stockcompass.service`

3. **Reload systemd daemon**
   - `systemctl daemon-reload`

4. **Enable & start canonical service**
   - `systemctl enable d8q-compass.service`
   - `systemctl start d8q-compass.service`

5. **Verify**
   - `systemctl status d8q-compass.service` → active (running)
   - `curl http://localhost:8087/health` → `{"status": "ok", "service": "compass"}`
   - `systemctl status stockcompass.service` → could not be found (expected)

## Files Affected

| Action | Path | Notes |
|--------|------|-------|
| DELETE | `/etc/systemd/system/stockcompass.service` | Legacy unit file |
| USE | `/etc/systemd/system/d8q-compass.service` | Already exists, no modification needed |

## Rollback

If `d8q-compass.service` fails to start:
1. `systemctl stop d8q-compass.service`
2. Re-create `stockcompass.service` from known working config
3. `systemctl daemon-reload && systemctl start stockcompass.service`
