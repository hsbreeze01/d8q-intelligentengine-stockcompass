# Spec: dic_stock 同步脚本

## ADDED Requirements

### Requirement: A股股票列表获取

系统 SHALL 通过 `akshare.stock_info_a_code_name()` 获取全部 A 股股票列表（代码 + 名称），作为同步的基础数据源。

#### Scenario: 正常获取股票列表

- **Given** akshare API 可用
- **When** 同步脚本启动并请求股票列表
- **Then** 系统 SHALL 返回包含所有 A 股代码和名称的列表（约 5200 条）
- **And** 每条记录 SHALL 包含 `code` 和 `name` 字段

#### Scenario: akshare API 不可用

- **Given** akshare API 超时或返回错误
- **When** 同步脚本请求股票列表
- **Then** 系统 SHALL 记录错误日志并终止同步流程
- **And** SHALL NOT 对数据库执行任何写入操作

---

### Requirement: 实时行情数据获取

系统 SHALL 通过 `akshare.stock_zh_a_spot()` 获取全部 A 股实时行情数据（Sina 数据源），并将其映射到 `dic_stock` 表字段。

#### Scenario: 正常获取行情数据

- **Given** akshare Sina 行情 API 可用
- **When** 同步脚本请求实时行情
- **Then** 系统 SHALL 返回包含所有 A 股实时行情的 DataFrame（约 5200 条）
- **And** SHALL 在 30 秒内完成数据获取

#### Scenario: 行情数据字段映射

- **Given** 行情数据获取成功
- **When** 系统处理行情数据
- **Then** 系统 SHALL 按以下映射关系将行情字段对应到 `dic_stock` 表列：
  | dic_stock 列 | 行情字段 |
  |---|---|
  | `code` | 股票代码 |
  | `stock_name` | 名称 |
  | `latest_price` | 最新价 |
  | `change_percentage` | 涨跌幅 |
  | `change_amount` | 涨跌额 |
  | `volume` | 成交量 |
  | `turnover` | 成交额 |
  | `amplitude` | 振幅 |
  | `highest` | 最高 |
  | `lowest` | 最低 |
  | `open_today` | 今开 |
  | `close_yesterday` | 昨收 |
  | `turnover_rate` | 换手率 |
  | `pe_ratio_dynamic` | 市盈率-动态 |
  | `pb_ratio` | 市净率 |
  | `total_market_value` | 总市值 |
  | `circulating_market_value` | 流通市值 |
  | `status` | 固定值 0（活跃） |

#### Scenario: 行情字段缺失

- **Given** 行情数据中部分字段不存在（如市盈率、市净率）
- **When** 系统映射字段
- **Then** 系统 SHALL 将缺失字段设为 NULL
- **And** SHALL NOT 因字段缺失而跳过该股票

---

### Requirement: 批量 UPSERT 写入

系统 SHALL 将同步数据以 UPSERT 方式批量写入 MySQL `dic_stock` 表，确保重复执行不会产生重复记录。

#### Scenario: 批量写入

- **Given** 已获取并映射完成的股票数据
- **When** 系统执行数据库写入
- **Then** 系统 SHALL 每批次写入 500 条记录
- **And** 每批次 SHALL 使用 `INSERT ... ON DUPLICATE KEY UPDATE` 语义
- **And** `code` 列 SHALL 作为唯一键判断依据

#### Scenario: 大数据量同步

- **Given** 股票列表包含 5200 条记录
- **When** 系统执行完整同步
- **Then** 系统 SHALL 分为 11 批次完成写入（10 × 500 + 1 × 200）
- **And** 每批次 SHALL 记录进度日志："Syncing batch X/N (500 stocks)..."

#### Scenario: 单批次写入失败

- **Given** 某批次写入时数据库连接异常
- **When** 系统捕获到写入异常
- **Then** 系统 SHALL 记录该批次失败的错误日志
- **And** SHALL 继续处理下一批次
- **And** 最终汇总报告 SHALL 包含失败批次数

---

### Requirement: 同步摘要报告

系统 SHALL 在同步完成后输出摘要信息。

#### Scenario: 同步完成摘要

- **Given** 全部批次写入完成
- **When** 同步脚本结束
- **Then** 系统 SHALL 记录日志："Synced X stocks in Ys"
- **And** SHALL 返回包含以下字段的摘要字典：
  - `total`: 总处理股票数
  - `synced`: 成功写入数
  - `failed`: 失败数
  - `duration_seconds`: 耗时（秒）
  - `source`: 数据源标记（"akshare-sina"）

---

### Requirement: CLI 运行模式

同步脚本 SHALL 支持独立命令行运行。

#### Scenario: 通过 Python 模块运行

- **Given** 项目依赖已安装
- **When** 用户执行 `python -m compass.sync.dic_stock_sync`
- **Then** 系统 SHALL 执行完整同步流程
- **And** SHALL 在标准输出打印进度和摘要信息

#### Scenario: 作为模块函数调用

- **Given** 其他模块导入 `compass.sync.dic_stock_sync`
- **When** 调用 `sync_dic_stock()` 函数
- **Then** 系统 SHALL 返回同步摘要字典
- **And** SHALL NOT 在模块级别自动执行同步

---

### Requirement: 同步触发 API 端点

系统 SHALL 提供 HTTP API 端点用于手动触发 dic_stock 同步。

#### Scenario: 管理员触发同步

- **Given** 用户已登录且具有管理员权限
- **When** 用户发送 `POST /api/sync/dic-stock`
- **Then** 系统 SHALL 异步执行同步流程
- **And** SHALL 立即返回 `{"message": "Sync started"}` 和 HTTP 202

#### Scenario: 非管理员触发同步

- **Given** 用户未登录或不具有管理员权限
- **When** 用户发送 `POST /api/sync/dic-stock`
- **Then** 系统 SHALL 返回 HTTP 403 和 `{"error": "Forbidden"}`

#### Scenario: 同步已在进行中

- **Given** 上一次同步尚未完成
- **When** 用户发送 `POST /api/sync/dic-stock`
- **Then** 系统 SHALL 返回 HTTP 409 和 `{"error": "Sync already in progress"}`

---

### Requirement: 速率控制

系统 SHALL 对外部 API 调用实施速率控制，避免被封禁。

#### Scenario: API 调用间隔

- **Given** 同步脚本正在进行数据获取
- **When** 系统调用 akshare API
- **Then** 连续两次调用之间 SHALL 至少间隔 1 秒
