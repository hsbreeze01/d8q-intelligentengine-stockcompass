# Tasks: 补全 stock_basic.industry 字段

## 1. 同步服务修复

- [ ] 修复 `_write_to_db()` — 使用 `db.execute()` 返回的 count 替代 `db._cursor.rowcount`，移除手动 `db.commit()` 调用，确保与 Database 上下文管理器协作正确
- [ ] 增强 `sync_industry_data()` — 同步完成后调用 `get_industry_status()` 检查补全率，低于 90% 时在返回结果中添加 warning 字段；akshare 获取阶段增加每行业间 0.5s 间隔避免限频
- [ ] 添加路由鉴权 — 在 `compass/strategy/routes/industry_sync.py` 中为 `POST /api/admin/industry/sync` 端点添加 `_is_admin()` 校验，未授权返回 403

## 2. 本地降级数据

- [ ] 创建本地降级行业映射文件 `compass/data/industry_mapping.json` — 从 akshare 预拉取或手动构造一份完整的 `{行业名: [股票代码列表]}` JSON 文件，作为 akshare 不可用时的兜底数据源

## 3. 测试与验证

- [ ] 编写 `tests/test_industry_sync.py` — 覆盖 `_write_to_db()` 的 UPDATE 逻辑（mock Database）、`get_industry_status()` 补全率计算、`_fetch_from_local()` 文件读取、同步状态流转、路由鉴权拦截
- [ ] 端到端验证 — 执行同步，确认 stock_basic.industry 非空率 > 90%，确认 Aggregator `_load_dimension_map()` 能正确返回行业映射
