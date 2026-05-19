# Design: 清理 DBClient 死代码

## 架构决策

纯删除操作，无架构变更。仅移除 `buy/DBClient.py` 中的注释掉的无用代码。

## 需要修改的文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `buy/DBClient.py` | MODIFY | 删除注释掉的死代码 |

## 具体删除目标

1. **`close()` 方法内注释块**（约第 79-84 行）：
   ```python
   # try:
   #     self._cursor.close()
   #     self._conn.close()
   # except Exception as e:
   #     # DBFactory.log.error(e)
   #     self.log.debug(e)
   ```
   共 6 行注释，以及其后的空行。

2. **`__init__` 末尾 debug 注释**（约第 75 行）：
   ```python
   # self.log.debug("=======================================init 7")
   ```

## 不修改的内容

- 所有活跃代码（非注释行）保持原样
- `__main__` 块中的注释保留（属于示例用法说明，非死代码）
- `select_one` / `select_many` 中的 `# result = ...` 注释保留（标记已移除的转换逻辑）
