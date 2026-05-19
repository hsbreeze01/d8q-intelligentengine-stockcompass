# Design: Clean up buy/DBClient.py

## Summary

Pure dead-code removal in `buy/DBClient.py`. No behavioral change, no new dependencies, no structural changes.

## What changes

1. **Remove commented-out error-handling block in `close()` method** — old `try:/self._cursor.close()/except/...` lines that were superseded by the current `close()` implementation.
2. **Remove commented-out debug logging lines** — any `# self.log.debug("===...")` or equivalent commented-out debug lines throughout the file.

## What stays the same

- All active (executable) code lines remain byte-for-byte identical.
- No changes to any other file in the project.
- No changes to imports, class structure, method signatures, or logic.

## Files affected

| File | Action |
|------|--------|
| `buy/DBClient.py` | Remove commented-out dead code only |

## Risk

- **None** — this is a whitespace/comment-only change. No code paths are altered.
- Verification: run existing tests + `ruff check` to confirm no regressions.
