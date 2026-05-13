# Delta Spec: Unify Compass Service

## MODIFIED Requirements

### Requirement: Compass service SHALL be managed by a single systemd unit

The StockCompass application SHALL be managed exclusively by `d8q-compass.service`. No other systemd unit SHALL control the compass process.

#### Scenario: Legacy service is removed

- **Given** `stockcompass.service` exists as a systemd unit file
- **When** the migration is executed
- **Then** `stockcompass.service` SHALL be stopped and disabled
- **And** `/etc/systemd/system/stockcompass.service` SHALL be removed
- **And** the systemd daemon SHALL be reloaded

#### Scenario: Canonical service takes over

- **Given** `d8q-compass.service` unit file exists and is correctly configured
- **When** the migration is executed
- **Then** `d8q-compass.service` SHALL be enabled
- **And** `d8q-compass.service` SHALL be started
- **And** the compass application SHALL respond to `GET /health` with status 200 on port 8087

#### Scenario: No duplicate compass processes

- **Given** `d8q-compass.service` is active
- **When** checking running processes
- **Then** there SHALL be exactly one compass process group
- **And** no orphaned compass processes from the legacy service SHALL remain

## REMOVED Requirements

### Requirement: stockcompass.service as a service unit

The legacy `stockcompass.service` unit SHALL no longer exist on the system. All compass lifecycle management MUST go through `d8q-compass.service`.
