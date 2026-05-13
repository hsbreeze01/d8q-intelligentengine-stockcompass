# Proposal: Unify compass service to d8q-compass.service

## Summary
Remove the legacy stockcompass.service and use the standard d8q-compass.service instead.

## Motivation
There are two systemd service files for compass:
- stockcompass.service (legacy, currently active but in restart loop)
- d8q-compass.service (standard, matches d8q naming convention)

The d8q-compass.service is the canonical one — it has PYTHONUNBUFFERED, StandardOutput/Error settings consistent with other d8q services. stockcompass.service is legacy and should be removed.

## Expected Behavior
- Stop and disable stockcompass.service
- Remove /etc/systemd/system/stockcompass.service
- Reload systemd daemon
- Enable and start d8q-compass.service
- Verify compass is running on port 8087 via health check
- Verify only d8q-compass.service manages compass (no duplicate processes)
- Use  commands only — no nohup, no manual kill
