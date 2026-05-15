## ADDED Requirements

### Requirement: Compass serves only JSON API responses
Compass SHALL NOT serve any HTML pages or render any Jinja2 templates. All responses from Compass (8087) SHALL be JSON API responses, except for the `/health` endpoint.

#### Scenario: Accessing former page route returns 404 or redirects
- **WHEN** request is made to Compass `GET /` or `GET /dashboard`
- **THEN** Compass returns 404 (route no longer registered)

#### Scenario: API endpoints still work
- **WHEN** request is made to Compass `GET /api/strategy/groups/`
- **THEN** Compass returns JSON response with strategy group data

#### Scenario: Health endpoint works
- **WHEN** request is made to Compass `GET /health`
- **THEN** Compass returns `{"status": "ok", "service": "compass"}`

### Requirement: Compass pages blueprint is removed
The `pages_bp` Blueprint (from `compass/api/routes/pages.py`) SHALL be unregistered from the Flask app. The file `compass/api/routes/pages.py` SHALL be deleted.

#### Scenario: Pages blueprint not registered
- **WHEN** Compass app starts
- **THEN** pages_bp is NOT in the registered blueprints
- **AND** no page routes (/, /dashboard, /recommended/*, /report, /policy) are available

### Requirement: Compass strategy pages blueprint is removed
The `strategy_pages_bp` Blueprint (from `compass/strategy/routes/strategy_pages.py`) SHALL be unregistered from the Flask app. The file `compass/strategy/routes/strategy_pages.py` SHALL be deleted.

#### Scenario: Strategy pages blueprint not registered
- **WHEN** Compass app starts
- **THEN** strategy_pages_bp is NOT in the registered blueprints
- **AND** no strategy page routes (/strategy/discover/, /strategy/my/, etc.) are available

### Requirement: Compass template and static folder configuration removed
The Flask app factory SHALL NOT configure `template_folder` or `static_folder`. The `templates/` and `static/` directories in the Compass project are no longer referenced by the running application.

#### Scenario: App creation without template config
- **WHEN** `create_app()` is called
- **THEN** Flask app is created without template_folder or static_folder pointing to project templates/static directories
- **AND** all API routes return JSON responses

### Requirement: Compass API routes unchanged
All existing Compass API routes SHALL continue to function identically. This includes:
- `/api/strategy/*` — Strategy group CRUD, signals, events, subscriptions
- `/api/analysis/*` — Stock analysis
- `/api/market/*` — Market data
- `/api/auth/*` — Authentication
- `/api/favorites/*` — User favorites
- `/api/simulation/*` — Trading simulation
- `/api/backtest/*` — Backtesting
- `/api/recommendation/*` — Recommendations
- `/api/notify/*` — Notifications
- `/api/sync/*` — Data sync

#### Scenario: Strategy API still works after migration
- **WHEN** DataFactory calls Compass `GET /api/strategy/groups/`
- **THEN** Compass returns the same JSON response as before migration

#### Scenario: Auth API still works
- **WHEN** DataFactory calls Compass `POST /api/auth/login`
- **THEN** Compass processes login and returns auth response
