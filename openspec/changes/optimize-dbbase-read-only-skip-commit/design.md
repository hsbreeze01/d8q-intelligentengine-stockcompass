# Design: Read-Only Context Skip Commit

## Overview

Add an internal `_dirty` flag to `StockDBBase` so that `__exit__` can
distinguish read-only sessions from write sessions and skip the unnecessary
`commit()` call when no writes occurred.

## Architecture Decision

**Flag-based approach over call-counting** — A single boolean is sufficient
because we only need to know *whether* any write happened, not *how many*.
This keeps the implementation minimal and zero-cost for read paths.

## Data Flow

```
__init__()        →  _dirty = False
__enter__()       →  _acquire_conn()           (unchanged)
  _query_one()    →  _dirty unchanged           (read)
  _query_all()    →  _dirty unchanged           (read)
  _execute_many() →  cursor.execute() + _dirty = True  (write)
__exit__(clean)   →  if _dirty: commit() + _dirty=False  else: skip
__exit__(error)   →  rollback() + _dirty=False  (unchanged behaviour)
_release_conn()   →  _dirty = False              (reset for reuse)
```

## Files to Modify

| File | Change |
|---|---|
| `stockfetch/db_base.py` | Add `_dirty` flag; guard `commit()` in `__exit__`; set flag in `_execute_many`; reset in `_release_conn` |

No new files are needed. No database schema changes. No external dependency changes.
