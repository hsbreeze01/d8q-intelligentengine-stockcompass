# Spec: Cleanup DBClient Dead Code

## MODIFIED Requirements

### Requirement: DBClient source code cleanliness

The `buy/DBClient.py` module SHALL contain only active (uncommented) production code.
All commented-out code blocks and debug logging remnants SHALL be removed.

#### Scenario: No commented-out code in close() method

- **Given** the `DBClient.close()` method in `buy/DBClient.py`
- **When** a developer reads the method body
- **Then** there SHALL be no lines beginning with `# try:`, `# except`, or `# self.log.debug(e)` that form a commented-out try/except block
- **And** the active `close()` logic (cursor close, connection close, counter decrement) SHALL remain unchanged

#### Scenario: No commented-out debug log lines

- **Given** the full contents of `buy/DBClient.py`
- **When** a developer searches for lines starting with `# self.log.debug("===`
- **Then** zero such lines SHALL exist in the file

#### Scenario: Functional behavior preserved

- **Given** the `DBClient` class after cleanup
- **When** any existing caller uses `DBClient` (construction, query, close)
- **Then** all runtime behavior SHALL be identical to before the cleanup
- **And** no active (uncommented) code SHALL have been modified or removed
