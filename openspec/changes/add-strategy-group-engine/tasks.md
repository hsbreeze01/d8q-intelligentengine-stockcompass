# Tasks: Strategy Group Engine — Phase 1 Backend Core

## 1. 基础设施（数据库 + FastAPI 骨架）

- [x] 1.1 创建数据库迁移脚本：新建 strategy_group / strategy_group_run / signal_snapshot / group_event 四张表（compass/strategy/db.py 中的 `init_tables()` 函数 + SQL 脚本）
- [x] 1.2 搭建 FastAPI 应用骨架：app.py 创建 FastAPI 实例、生命周期管理（启动时建表+加载调度）、/health 端点、统一错误处理中间件、日志配置
- [x] 1.3 创建 Pydantic 模型层：StrategyGroupCreate / StrategyGroupUpdate / StrategyGroupResponse / SignalSnapshotResponse / GroupEventResponse 等请求响应 schema（compass/strategy/models.py）
- [x] 1.4 添加启动脚本 scripts/run_strategy_engine.py 和 systemd service 文件，更新 pyproject.toml 添加 fastapi/uvicorn/apscheduler/sse-starlette 依赖

## 2. 策略组 CRUD API

- [x] 2.1 实现策略组 CRUD 路由：POST 创建 / PUT 编辑 / DELETE 软删除 / PATCH 启停状态 / GET 列表+详情，包含完整的参数校验（name 非空、signal_logic 枚举、conditions 结构、aggregation 结构）（compass/strategy/routes/strategy_groups.py）
- [x] 2.2 实现策略组数据库辅助函数：insert / update / soft_delete / update_status / list_by_status / get_by_id，封装 SQL 操作（compass/strategy/db.py）

## 3. 信号扫描引擎

- [x] 3.1 实现扫描引擎核心：Scanner 类 scan() 方法——从 indicators_daily 批量读取最新日数据、从 stock_analysis 读取 buy 值、遍历股票做条件匹配（AND/OR/SCORING 三种逻辑 + cross_above/cross_below 特殊算子）、写入 signal_snapshot 和 strategy_group_run（compass/strategy/services/scanner.py）
- [x] 3.2 实现手动触发扫描路由 `POST /api/strategy/{id}/scan` 和信号查询路由 `GET /api/signals`（按策略组/股票代码筛选）+ SSE 端点 `GET /api/signals/stream`（compass/strategy/routes/signals.py）

## 4. 群体事件聚合器

- [x] 4.1 实现聚合引擎：Aggregator 类 aggregate() 方法——按 dimension 分组 signal_snapshot、关联 stock_basic 获取行业、检测 open 事件匹配/新建、计算 avg_buy_star/max_buy_star/matched_stocks、定时关闭超时事件（compass/strategy/services/aggregator.py）
- [x] 4.2 实现群体事件查询路由：GET 列表（按策略组/dimension_value 筛选）+ GET 详情 + PATCH 关闭事件（compass/strategy/routes/events.py）

## 5. 行业数据同步

- [x] 5.1 实现行业数据同步服务：IndustrySync 类 sync() 方法——调用 akshare stock_board_industry_name_em 获取行业映射、增量更新 stock_basic.industry 为空的记录、降级到本地 JSON 文件、同步统计接口（compass/strategy/services/industry_sync.py）
- [x] 5.2 创建行业同步和状态查询路由：POST /api/admin/industry/sync + GET /api/admin/industry/stats + GET /api/admin/industry/status

## 6. 定时调度集成

- [x] 6.1 实现 APScheduler 封装：启动时加载所有 active 策略组的 scan_cron、注册定时扫描任务、策略组状态变更时动态更新调度、服务关闭时优雅停止（compass/strategy/scheduler.py）

## 7. 测试

- [x] 7.1 编写测试：策略组 CRUD 测试（创建/编辑/删除/启停/校验）、扫描引擎测试（AND/OR/SCORING 逻辑 + 快照生成）、聚合器测试（新建/追加/超时关闭）、行业同步测试（Mock akshare + 降级）（tests/test_strategy/）
