# Design: Cleanup DBClient Dead Code

## Summary

Pure dead-code removal from `buy/DBClient.py`. No behavioral changes, no new files, no new dependencies.

## Target File

- `buy/DBClient.py` — sole file to modify

## Changes

### 1. `close()` method — remove commented-out try/except block

Remove any lines that are comments forming a dead try/except structure:

```python
# try:
#     ...
# except Exception as e:
#     self.log.debug(e)
```

### 2. Module-wide — remove commented-out debug log lines

Remove any lines matching `# self.log.debug("===...` pattern scattered in the file.

## What Stays Unchanged

- All active (uncommented) code in `DBClient`
- The existing `self.log.debug(f"mincached: ...")` call in `__init__` (this is **active** code, not dead code)
- Class structure, method signatures, imports, docstrings

## Risk Assessment

**Risk: None.** This is a comment-only change. Python bytecode is unaffected. No test coverage needed for removing comments.

## Verification

- `ruff check buy/DBClient.py` — must pass with zero errors
- Grep for `# self.log.debug` — must return zero matches
- Grep for `# try:` — must return zero matches in DBClient.py
