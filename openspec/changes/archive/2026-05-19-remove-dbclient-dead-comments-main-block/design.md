# Design: Remove Dead Code from DBClient

## Summary

Pure deletion change — remove 5 commented-out lines and the `if __name__ == "__main__"` block from `buy/DBClient.py`. No behavioral change, no new files, no dependencies affected.

## What is being removed

| Location | Content | Reason |
|---|---|---|
| Line 53 | `# self.log.debug(f"Connection opened...")` | Dead debug comment |
| Line 95 | `# self.log.debug(f"Connection closed...")` | Dead debug comment |
| Line 114 | `# result = self.__dict_datetime_obj_to_str(result)` | Dead data-transform comment |
| Line 127 | `# [self.__dict_datetime_obj_to_str(row_dict)...` | Dead data-transform comment |
| Line 141 | `# [self.__dict_datetime_obj_to_str(row_dict)...` | Dead data-transform comment |
| Lines 153–181 | `if __name__ == "__main__": ...` | Test/demo code not belonging in production |

## Files modified

- `buy/DBClient.py` — delete 6 code regions; all active logic stays untouched

## Impact

- Zero runtime impact — only comments and unreachable `__main__` block removed
- No import changes, no new dependencies
- No other files reference the removed code
