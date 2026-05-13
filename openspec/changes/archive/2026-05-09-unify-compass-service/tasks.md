# Tasks: Unify Compass Service

All tasks are pure system operations — no application code changes.

## 1. Service Migration

- [x] 1.1 Stop and disable legacy stockcompass.service, remove unit file, reload systemd daemon, enable and start d8q-compass.service
- [x] 1.2 Verify d8q-compass.service is active, health check on port 8087 passes, and stockcompass.service no longer exists
