# Design: 补全 stock_basic.industry 字段

## 1. 问题分析

### 现状
- `stock_basic` 表已有 `industry` 列（VARCHAR(50)），但全部为空（0/5512）
- `compass/strategy/services/industry_sync.py` 已实现同步服务框架
- `compass/strategy/routes/industry_sync.py` 已注册 Blueprint 路由
- 策略组引擎的 Aggregator 已按 `stock_basic` 的 `stock_code` + `industry` 字段分组

### 根因
经代码审查，发现以下问题导致同步从未成功：

1. **`_write_to_db()` 中 rowcount 获取方式不可靠**：使用 `db._cursor.rowcount` 访问私有属性，Database 类未暴露此接口，且 Database 的 `__exit__` 会自动 commit，但 `_write_to_db` 在循环内手动 commit，与 Database 上下文管理器的 commit 重复。
2. **akshare 接口容错不足**：单行业失败后虽重试 3 次，但跳过后无后续补救，可能遗漏大量行业。
3. **路由层缺少管理员鉴权**：`POST /api/admin/industry/sync` 任何人可调用，未校验 `is_admin`。
4. **无本地 fallback JSON 文件**：`_fetch_from_local()` 引用的 `compass/data/industry_mapping.json` 不存在。

## 2. 架构决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 数据源 | akshare `stock_board_industry_name_em()` + `stock_board_industry_cons_em()` | 项目已依赖 akshare，且这是东方财富行业分类，覆盖面最全 |
| 降级方案 | 本地 JSON 文件 | akshare 接口限频/维护时作为兜底 |
| 写入方式 | 逐行业批量 UPDATE | 数据量可控（~110 个行业 × ~50 股/行业），无需复杂批量优化 |
| 鉴权方式 | 复用 `_is_admin()` 模式 | 与 sync.py、admin.py 保持一致 |

## 3. 数据流

```
akshare API
  │
  ├─ stock_board_industry_name_em() → 行业板块列表
  │
  └─ for each industry:
       stock_board_industry_cons_em(symbol=name) → 成分股代码列表
           │
           ▼
  industry_map = { "行业名": ["600001", "600002", ...], ... }
           │
           ▼ (akshare 失败时降级)
  compass/data/industry_mapping.json (本地文件)
           │
           ▼
  _write_to_db()
    for each (industry_name, codes):
      UPDATE stock_basic SET industry = %s
      WHERE stock_code IN (%s, %s, ...)
           │
           ▼
  stock_basic.industry 字段被填充
           │
           ▼
  Aggregator._load_dimension_map("industry", codes) → 正确返回行业映射
```

## 4. 文件变更清单

### 修改的文件

| 文件 | 变更说明 |
|------|----------|
| `compass/strategy/services/industry_sync.py` | 1) `_write_to_db()` 改用 `db.execute()` 返回的 count 而非 `db._cursor.rowcount`；2) 移除手动 `db.commit()`（由上下文管理器处理）；3) 增加同步后自动校验补全率逻辑 |
| `compass/strategy/routes/industry_sync.py` | 为写入端点（sync）添加 `_is_admin()` 鉴权；读取端点（status/stats）保持不变 |

### 新增的文件

| 文件 | 说明 |
|------|------|
| `compass/data/industry_mapping.json` | 本地降级行业映射 JSON 文件，格式：`{"行业名": ["600001", ...], ...}` |
| `tests/test_industry_sync.py` | 同步服务核心逻辑的单元测试 |

## 5. 关键实现细节

### 5.1 _write_to_db 修复

```python
def _write_to_db(industry_map: dict) -> int:
    updated = 0
    with Database() as db:
        for industry_name, codes in industry_map.items():
            if not codes:
                continue
            placeholders = ",".join(["%s"] * len(codes))
            count, _ = db.execute(
                f"UPDATE stock_basic SET industry = %s "
                f"WHERE stock_code IN ({placeholders})",
                tuple([industry_name] + codes),
            )
            updated += count
    return updated
```

关键变更：
- 使用 `db.execute()` 返回的 `count`（已是 affected rows），而非 `db._cursor.rowcount`
- 移除 `db.commit()` 调用，由 `Database.__exit__` 自动处理

### 5.2 路由鉴权

复用 `compass/api/routes/admin.py` 中的 `_is_admin()` 模式：

```python
def _is_admin():
    uid = session.get("uid")
    if not uid:
        return False
    try:
        with Database() as db:
            _, user = db.select_one("SELECT is_admin FROM user WHERE id = %s", (uid,))
            return user and user["is_admin"] == 1
    except Exception:
        return False
```

仅对 `POST /api/admin/industry/sync` 添加鉴权，读取端点保持开放（与现有 admin 路由的 GET 端点模式一致）。

### 5.3 同步后质量校验

在 `sync_industry_data()` 末尾调用 `get_industry_status()` 检查补全率，低于 90% 时在返回结果中添加 warning。

## 6. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| akshare 接口限频导致大面积失败 | 每行业间 sleep 0.5s；单行业重试 3 次；降级到本地 JSON |
| stock_basic 表 code 列名不一致（code vs stock_code） | 所有 compass 模块统一使用 `stock_code`，与 aggregator 保持一致 |
| 同步耗时过长导致 HTTP 超时 | 同步在后台线程执行，API 立即返回 202，通过 status 端点轮询进度 |
