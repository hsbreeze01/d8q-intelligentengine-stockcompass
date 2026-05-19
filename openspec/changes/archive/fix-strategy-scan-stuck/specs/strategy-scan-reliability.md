# Delta Spec: 策略扫描可靠性保障

## ADDED Requirements

### REQ-SCAN-001: 连接池获取超时

系统 SHALL 在 DBUtils PooledDB 初始化时设置连接获取超时（30 秒），
防止 daemon thread 在 `blocking=True` 模式下无限等待连接。

#### Scenario: 连接池耗尽时扫描线程不卡死

- **Given** DB 连接池已达到 maxconnections 上限且所有连接均在占用
- **When** 后台扫描线程尝试 `Database()` 获取连接
- **Then** 系统在 30 秒内抛出连接超时异常（而非无限等待）
- **And** 该异常被捕获后 run 记录被标记为 `status=failed`，`error_message` 包含超时描述

#### Scenario: 正常负载下连接获取不受影响

- **Given** DB 连接池有可用连接
- **When** 任何代码路径调用 `Database()` 获取连接
- **Then** 连接在毫秒级返回，不影响正常功能

---

### REQ-SCAN-002: 后台扫描健康检查使用独立连接

系统 SHALL 在 `_run_scan_background` 的健康检查中使用独立的、
非连接池的短连接进行 `SELECT 1` 验证，确保健康检查本身不会因
连接池耗尽而阻塞。

#### Scenario: 连接池不可用时健康检查快速失败

- **Given** DB 连接池已耗尽或所有连接 stale
- **When** 后台扫描线程启动并执行健康检查
- **Then** 健康检查使用 `pymysql.connect()` 直接创建短连接（不经过连接池）
- **And** 若短连接也失败，run 记录被标记为 `failed`，后台线程立即退出

#### Scenario: 健康检查成功后扫描使用连接池

- **Given** 健康检查短连接成功
- **When** 后续扫描逻辑调用 `Database()` 获取连接池连接
- **Then** 扫描正常使用连接池，不受健康检查短连接的影响

---

### REQ-SCAN-003: APScheduler 定时扫描超时保护

系统 SHALL 对 APScheduler 回调 `_run_scan()` 增加与手动扫描相同的
超时保护机制（内层线程 + 300 秒超时），防止 cron 触发的扫描线程
阻塞 APScheduler 工作线程。

#### Scenario: 定时扫描正常完成

- **Given** 一个 active 策略组配置了 `scan_cron = "30 17 * * mon-fri"`
- **And** APScheduler 在指定时间触发 `_run_scan()`
- **When** 扫描在 300 秒内完成
- **Then** run 记录被标记为 `completed`
- **And** APScheduler 工作线程被释放，可执行后续调度

#### Scenario: 定时扫描超时

- **Given** APScheduler 触发了定时扫描
- **When** 扫描执行超过 300 秒
- **Then** run 记录被标记为 `failed`，`error_message` 为超时描述
- **And** APScheduler 工作线程被释放（不因超时扫描而永久阻塞）

---

### REQ-SCAN-004: Pipeline 数据更新后触发策略扫描

系统 SHALL 在 pipeline 每日数据更新任务（DailyAnalysisTask）完成后，
自动触发所有 active 策略组的扫描，确保扫描基于当日最新数据执行。

#### Scenario: 每日数据更新完成后自动扫描

- **Given** pipeline 每日定时任务已配置在 `SCHEDULE_HOUR:SCHEDULE_MINUTE` 执行
- **And** 至少有一个 `status=active` 的策略组
- **When** `DailyAnalysisTask.run()` 成功完成
- **Then** 系统遍历所有 active 策略组，依次触发扫描（trigger_type=`cron`）
- **And** 每个策略组的扫描结果（成功/失败）被独立记录，不互相影响

#### Scenario: 单个策略组扫描失败不影响其他组

- **Given** 有 3 个 active 策略组（A、B、C）
- **When** 策略组 B 的扫描失败（抛出异常）
- **Then** 策略组 A 的扫描结果正常保留
- **And** 策略组 C 的扫描继续执行
- **And** B 的失败被记录到日志和 run 记录中

#### Scenario: 无 active 策略组时跳过扫描

- **Given** 不存在 `status=active` 的策略组
- **When** pipeline 每日数据更新完成
- **Then** 系统跳过策略扫描步骤
- **And** 日志记录 "无 active 策略组，跳过扫描"

---

## MODIFIED Requirements

### REQ-SCAN-005: 启动时清理 stale run 记录（增强）

系统 SHALL 在应用启动时清理所有超过 10 分钟仍处于 `status=running`
的记录（原阈值 30 分钟），标记为 `failed`。

#### Scenario: 启动时发现 stale run

- **Given** `strategy_group_run` 表中存在 `status=running` 且 `started_at` 超过 10 分钟的记录
- **When** 应用启动并执行 `init_strategy_engine()`
- **Then** 这些记录被更新为 `status=failed`
- **And** `error_message` 设为 `"stale run cleaned on startup"`
