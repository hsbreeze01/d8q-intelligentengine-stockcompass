# Tasks: dic_stock 同步脚本

## 1. 基础设施

- [x] **1.1 创建 `compass/sync` 包** — 新建 `compass/sync/__init__.py` 空文件
- [x] **1.2 创建同步核心模块** — 新建 `compass/sync/dic_stock_sync.py`，实现 `sync_dic_stock()` 函数：
  - 调用 `akshare.stock_info_a_code_name()` 获取股票列表
  - 调用 `akshare.stock_zh_a_spot()` 获取实时行情
  - 执行中文字段名 → `dic_stock` 列名的映射（含防御性缺失处理）
  - 以 500 条/批 UPSERT 到 MySQL（`ON DUPLICATE KEY UPDATE`）
  - 返回同步摘要 dict（total / synced / failed / duration_seconds / source）
  - 支持 `python -m compass.sync.dic_stock_sync` CLI 运行（`if __name__ == "__main__"` 入口）

## 2. API 端点

- [x] **2.1 创建同步触发路由** — 新建 `compass/api/routes/sync.py` Blueprint：
  - `POST /api/sync/dic-stock` — 管理员权限校验，后台线程执行同步，返回 202
  - 模块级 `threading.Lock` + `_sync_running` 标志防止并发（重复请求返回 409）
  - `GET /api/sync/dic-stock/status` — 返回最近一次同步摘要和进行中状态
- [x] **2.2 注册 sync Blueprint** — 在 `compass/api/app.py` 的 `_register_blueprints()` 中注册 sync 路由

## 3. 验证

- [x] **3.1 验证同步功能** — 启动 Flask 应用，调用 `POST /api/sync/dic-stock`，确认：
  - `dic_stock` 表写入数据（`SELECT COUNT(*) FROM dic_stock` > 0）
  - 字段映射正确（抽样检查 `SELECT * FROM dic_stock LIMIT 5`）
  - 重复调用不产生重复记录
  - ruff lint + import 通过
