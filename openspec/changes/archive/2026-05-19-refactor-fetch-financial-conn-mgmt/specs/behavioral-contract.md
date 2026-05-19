# Delta Spec: Behavioral Contract

## MODIFIED Requirements

### Requirement: Preserved Public Interface

The refactored `scripts/fetch_financial.py` SHALL maintain the same public
interface and observable behavior as the original.

#### Scenario: CLI execution produces identical output

- **Given** the script is invoked via `python scripts/fetch_financial.py`
- **When** it runs against the same database and market data
- **Then** it SHALL process the same set of stocks (top 20 from `stock_basic`)
- **And** it SHALL write the same financial records to `stock_financial`
- **And** log output format SHALL remain consistent

#### Scenario: Same akshare data fetching logic

- **Given** `fetch_one_stock` is called with a stock code
- **When** it fetches profit, balance sheet, cash flow, and abstract data
- **Then** it SHALL use the same akshare API calls in the same order
- **And** it SHALL store results through the same INSERT/UPDATE logic
- **And** row limits (`.head(4)` for profit/balance, `.head(2)` for cash flow)
  SHALL be preserved

---

### Requirement: No New Dependencies

The refactoring SHALL NOT introduce any new external packages.

#### Scenario: Only existing imports used

- **Given** the refactored `scripts/fetch_financial.py`
- **When** its import list is inspected
- **Then** it SHALL NOT contain any dependency not already present in
  `requirements.txt` or `pyproject.toml`
- **And** `pymysql` SHALL only appear as an indirect dependency (via `DBClient`)
  — not as a direct import for `pymysql.connect()`
