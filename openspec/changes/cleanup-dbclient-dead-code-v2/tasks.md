# Tasks: 清理 DBClient 死代码

## 1. 死代码清理

- [x] 1.1 移除 `buy/DBClient.py` 中 `close()` 方法内的注释块（`# try:` ~ `# self.log.debug(e)`）及 `__init__` 末尾的 `# self.log.debug("===...init 7")` 注释，验证 ruff 和功能正常
