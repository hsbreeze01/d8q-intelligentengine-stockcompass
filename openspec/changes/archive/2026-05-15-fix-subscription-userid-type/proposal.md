# Proposal: 修复策略订阅 user_id 类型不匹配导致 500

## Summary
策略发现页点击订阅按钮返回 500 Internal Server Error。根因：`strategy_subscription` 表的 `user_id` 列是 `INT` 类型，但 Factory 代理通过 `X-Forwarded-User` header 传递的是字符串用户名（如 `"admin"`），MySQL 报错 `Incorrect integer value: 'admin' for column 'user_id'`。

## Motivation
订阅功能完全不可用。这是之前修复 `_require_login()` 认证后暴露的下游问题。

## Root Cause
1. 之前将 `_require_login()` 改为从 `X-Forwarded-User` header 读取用户身份
2. Factory 通过 header 传递的是 `session["username"]`（字符串，如 `"admin"`）
3. `strategy_subscription` 表的 `user_id` 列定义为 `INT NOT NULL`
4. `insert_subscription("admin", 1)` → MySQL DataError: Incorrect integer value

## Expected Behavior
- 点击订阅按钮 → 成功订阅 → toast "已订阅"
- 支持 `user_id` 为字符串用户名（如 "admin"、"zhangsan"）

## Scope
- **Compass**: `compass/strategy/db.py` — 修改 `strategy_subscription` 表 DDL，`user_id` 改为 `VARCHAR(100)`
- **Compass**: `compass/strategy/routes/strategy_subscription.py` — `insert_subscription` 调用无需改动（Python 不强制 type hint）
- **Compass**: 需要 ALTER TABLE 迁移现有表结构

## Target Projects
- d8q-intelligentengine-stockcompass

## 修复方案
1. 修改 `db.py` 中 `_TABLES["strategy_subscription"]` 的 DDL：`user_id INT NOT NULL` → `user_id VARCHAR(100) NOT NULL`
2. 添加 `ALTER TABLE` 迁移逻辑（或直接执行 ALTER）
3. 重启 compass 服务
