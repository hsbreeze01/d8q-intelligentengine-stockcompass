# Tasks: Read-Only Context Skip Commit

## 1. Backend — Dirty flag implementation

- [x] 1.1 Add `_dirty` flag to `StockDBBase` (`__init__`, `_execute_many`, `__exit__`, `_release_conn`)
  - `__init__`: set `self._dirty = False`
  - `_execute_many`: set `self._dirty = True` after `cursor.execute`
  - `__exit__`: guard `commit()` behind `if self._dirty`; always reset `_dirty = False` in finally
  - `_release_conn`: reset `self._dirty = False`

## 2. Verification

- [x] 2.1 Run ruff check on `stockfetch/db_base.py` and fix any lint issues
