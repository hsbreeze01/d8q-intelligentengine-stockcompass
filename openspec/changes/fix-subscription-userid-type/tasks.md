# Tasks: 修复策略订阅 user_id 类型

## 1. 数据库 Schema 变更

- [ ] 修改 `compass/strategy/db.py` — DDL + 迁移 + type hint 清理
  - 将 `_TABLES["strategy_subscription"]` 的 `user_id INT NOT NULL` 改为 `user_id VARCHAR(100) NOT NULL`
  - 在 `init_tables()` 中添加 ALTER TABLE 迁移：检测 `user_id` 列类型是否为 `int`，若是则执行 `ALTER TABLE strategy_subscription MODIFY COLUMN user_id VARCHAR(100) NOT NULL`
  - 清理 subscription 相关函数的 type hint：`insert_subscription`、`delete_subscription`、`get_subscription`、`list_user_subscriptions`、`list_strategy_groups_with_subscription` 的 `user_id: int` 参数改为去掉类型约束（或改为 `str | int`）

## 2. 验证

- [ ] 重启 compass 服务并验证订阅功能正常（手动或自动化）
  - 执行 `systemctl restart d8q-stockcompass`
  - 确认 `init_tables()` 日志输出"表 strategy_subscription 已就绪"
  - 确认现有订阅记录未丢失
