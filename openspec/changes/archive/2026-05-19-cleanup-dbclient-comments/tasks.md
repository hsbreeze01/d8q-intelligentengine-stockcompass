# Tasks: Clean up buy/DBClient.py

## 1. Dead code removal

- [x] 1.1 Remove all commented-out dead code from `buy/DBClient.py` (commented-out `try`/`except` blocks in `close()`, commented-out `# self.log.debug(...)` lines throughout the file) while keeping every active code line unchanged
- [x] 1.2 Verify: run `ruff check buy/DBClient.py` and project tests to confirm no regressions
