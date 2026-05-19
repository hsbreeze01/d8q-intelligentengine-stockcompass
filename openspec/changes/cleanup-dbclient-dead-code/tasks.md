# Tasks: Cleanup DBClient Dead Code

## 1. Remove dead code from buy/DBClient.py

- [x] Remove all commented-out code blocks in `buy/DBClient.py`: commented try/except in `close()`, and any `# self.log.debug("===...` lines. Keep all active code unchanged. Verify with `ruff check` and grep.
