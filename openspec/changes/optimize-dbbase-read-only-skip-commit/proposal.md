# Proposal: IMPLEMENT THIS CHANGE. In stockfetch/db_base.py, optimize the __exit__ method to skip commit when the context was used only for reads (no writes executed).

Add a _dirty flag:
1. In __init__: add self._dirty = False
2. In _execute_many(): add self._dirty = True after execute
3. In __exit__: change the commit path to only commit if self._dirty is True. Reset self._dirty = False.
4. Keep rollback on exception as-is.

This avoids unnecessary commits on read-only operations like db_get_maxdate() and getData().

## Summary
IMPLEMENT THIS CHANGE. In stockfetch/db_base.py, optimize the __exit__ method to skip commit when the context was used only for reads (no writes executed).

Add a _dirty flag:
1. In __init__: add self._dirty = False
2. In _execute_many(): add self._dirty = True after execute
3. In __exit__: change the commit path to only commit if self._dirty is True. Reset self._dirty = False.
4. Keep rollback on exception as-is.

This avoids unnecessary commits on read-only operations like db_get_maxdate() and getData().

## Motivation

## Expected Behavior

