# Design: 修复策略订阅 user_id 类型不匹配

## 问题描述

Factory 代理通过 `X-Forwarded-User` header 传递字符串用户名（如 `"admin"`），
但 `strategy_subscription` 表的 `user_id` 列为 `INT NOT NULL`，导致 INSERT 时 MySQL 报错。

## 架构决策

### 决策 1：user_id 列改为 VARCHAR(100)

**选择**: 将 `strategy_subscription.user_id` 从 `INT` 改为 `VARCHAR(100)`

**理由**:
- `_require_login()` 已改为从 `X-Forwarded-User` 读取用户名（字符串）
- `db.py` 中所有 subscription 相关函数的 type hint 为 `int` 但 Python 运行时不强制
- VARCHAR(100) 可同时兼容整型字符串 `"1"` 和用户名 `"admin"`
- 不影响唯一约束 `uk_user_strategy (user_id, strategy_group_id)` 的语义

**替代方案（否决）**:
- 在 route 层将用户名解析为 int — 不可行，用户名本身不是数字
- 新增 username 列 — 过度设计，当前只有 subscription 表受影响

### 决策 2：通过 ALTER TABLE 迁移而非重建表

**选择**: 在 `init_tables()` 中添加 ALTER TABLE 逻辑

**理由**:
- 现有数据需保留，DROP + CREATE 会丢失订阅记录
- MySQL `ALTER TABLE ... MODIFY COLUMN` 会自动将 INT 值转为 VARCHAR 字符串
- 使用 `SHOW COLUMNS` 检测列类型，仅当为 INT 时才执行 ALTER，幂等安全

## 数据流

```
Factory → X-Forwarded-User: "admin"
       → _require_login() 返回 "admin"
       → db.insert_subscription("admin", group_id)
       → INSERT INTO strategy_subscription (user_id, strategy_group_id) VALUES ("admin", 1)
       → MySQL VARCHAR 列，正常写入 ✓
```

## 变更文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `compass/strategy/db.py` | 修改 | 1) `_TABLES["strategy_subscription"]` DDL: `user_id INT` → `user_id VARCHAR(100)` |
| `compass/strategy/db.py` | 修改 | 2) `init_tables()` 添加 ALTER TABLE 迁移逻辑 |
| `compass/strategy/db.py` | 修改 | 3) subscription 相关函数的 type hint: `user_id: int` → `user_id`（去掉 int hint，保持动态） |
