## ADDED Requirements

### Requirement: DataFactory serves all Compass frontend pages
DataFactory (8088) SHALL render all former Compass Jinja2 templates, making it the sole web frontend entry point. No HTML pages SHALL be served directly by Compass (8087).

#### Scenario: User accesses compass index page through factory
- **WHEN** user navigates to `http://47.99.57.152:8088/compass/`
- **THEN** DataFactory renders the compass index.html template with stock list data fetched from Compass API

#### Scenario: User accesses strategy discover page through factory
- **WHEN** user navigates to `http://47.99.57.152:8088/strategy/discover/`
- **THEN** DataFactory renders the strategy discover.html template with strategy group data fetched from Compass API

#### Scenario: User accesses strategy event detail through factory
- **WHEN** user navigates to `http://47.99.57.152:8088/strategy/events/1/`
- **THEN** DataFactory renders the event_detail.html template with event data fetched from Compass API

### Requirement: Compass templates are stored in DataFactory compass subdirectory
All Compass templates SHALL be placed under `templates/compass/` in the DataFactory project. Static resources SHALL be placed under `static/compass/`. This avoids naming conflicts with existing DataFactory templates.

#### Scenario: Template file organization
- **WHEN** migration is complete
- **THEN** compass templates exist at `datafactory/templates/compass/*.html` and `datafactory/templates/compass/strategy/*.html`
- **AND** compass static files exist at `datafactory/static/compass/css/`, `datafactory/static/compass/admin/`

### Requirement: Page routes use Compass API proxy for data
DataFactory page routes SHALL NOT directly access Compass's MySQL database. All data fetching SHALL go through `compass_request()` API proxy calls.

#### Scenario: Dashboard page data fetching
- **WHEN** DataFactory renders `/compass/dashboard`
- **THEN** it calls Compass API endpoints via compass_request() to fetch dashboard data
- **AND** does NOT use Database() or any direct MySQL connection to Compass's database

### Requirement: Authentication uses DataFactory session system
All page routes SHALL use DataFactory's existing auth system (SQLite-based session). Compass login/register pages SHALL NOT be migrated; users login through DataFactory's existing `/login` route.

#### Scenario: Unauthenticated user accesses protected page
- **WHEN** user navigates to `/strategy/discover/` without valid DataFactory session
- **THEN** user is redirected to DataFactory's `/login` page

#### Scenario: Authenticated user accesses protected page
- **WHEN** user navigates to `/strategy/discover/` with valid DataFactory session
- **THEN** page renders normally with user context from DataFactory session

### Requirement: Strategy admin routes require admin role
Strategy group admin pages (`/strategy/admin/*`) SHALL check that the logged-in user has admin role in DataFactory's auth system.

#### Scenario: Non-admin user accesses strategy admin
- **WHEN** non-admin user navigates to `/strategy/admin/groups/`
- **THEN** user receives 403 Forbidden or is redirected

#### Scenario: Admin user accesses strategy admin
- **WHEN** admin user navigates to `/strategy/admin/groups/`
- **THEN** admin strategy list page renders normally

### Requirement: Template API paths work through DataFactory proxy
All JavaScript fetch/XMLHttpRequest calls in migrated templates SHALL use paths that are served by DataFactory's existing API proxy routes. No direct calls to Compass (8087) from the browser.

#### Scenario: Strategy page JS calls API
- **WHEN** strategy event detail page JavaScript calls `/api/strategy/events/1/`
- **THEN** the request goes to DataFactory (8088) which proxies it to Compass (8087)
- **AND** the response is returned to the browser

### Requirement: All migrated routes and pages
The following page routes SHALL be available on DataFactory after migration:

| Route | Template | Description |
|---|---|---|
| `/compass/` | `compass/index.html` | Stock list page |
| `/compass/dashboard` | `compass/dashboard.html` | Compass dashboard |
| `/compass/recommended/<date>` | `compass/recommended_stocks.html` | Recommended stocks |
| `/compass/report` | `compass/report.html` | Report page |
| `/compass/policy` | `compass/policy.html` | Policy page |
| `/strategy/discover/` | `compass/strategy/discover.html` | Strategy discover |
| `/strategy/my/` | `compass/strategy/my_strategies.html` | My strategies |
| `/strategy/events/<id>/` | `compass/strategy/event_detail.html` | Event detail |
| `/strategy/admin/groups/` | `compass/strategy/admin_list.html` | Admin strategy list |
| `/strategy/admin/groups/new` | `compass/strategy/admin_edit.html` | New strategy |
| `/strategy/admin/groups/<id>/edit` | `compass/strategy/admin_edit.html` | Edit strategy |

#### Scenario: Complete route coverage
- **WHEN** migration is complete
- **THEN** all routes listed above return 200 with correct HTML content on DataFactory port 8088
