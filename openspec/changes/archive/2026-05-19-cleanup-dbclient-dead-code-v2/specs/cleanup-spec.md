# Delta Spec: 清理 DBClient 死代码

## MODIFIED Requirements

### Requirement: DBClient 源码可读性

DBClient (`buy/DBClient.py`) SHALL 不包含已注释掉的废弃代码块。

#### Scenario: 移除 close() 方法中的注释掉的 try/except 块

- **Given** DBClient.py 的 `close()` 方法包含一段以 `# try:` 开头、以 `# self.log.debug(e)` 结尾的注释掉的代码块
- **When** 执行清理
- **Then** 该注释块（第 79-84 行区间）SHALL 被完全移除
- **And** 其上方的空行及 `close(self):` 方法签名 SHALL 保持不变
- **And** 其下方的活跃代码（`with DBClient.lock:` 块）SHALL 保持不变

#### Scenario: 移除 __init__ 末尾的 debug 注释

- **Given** `__init__` 方法末尾有一行 `# self.log.debug("===...init 7")` 注释
- **When** 执行清理
- **Then** 该行 SHALL 被移除

#### Scenario: 保留所有活跃代码

- **Given** 文件中存在大量活跃的 Python 代码（非注释）
- **When** 执行清理
- **Then** 所有活跃代码 SHALL 保持原样，行为不变
