# Delta Spec: 行业数据同步补全

## ADDED Requirements

### Requirement: 行业数据同步执行
系统 SHALL 提供从 akshare 获取 A 股行业分类数据并批量写入 `stock_basic.industry` 字段的能力。

#### Scenario: 正常同步流程
- **Given** akshare 接口可用，stock_basic 表中有 5000+ 条股票记录
- **When** 管理员通过 API 触发行业数据同步
- **Then** 系统从 akshare 获取所有行业板块及其成分股代码
- **And** 将行业名称批量 UPDATE 到 stock_basic.industry 字段
- **And** 返回更新记录数和完成状态

#### Scenario: akshare 接口不可用时降级
- **Given** akshare 行业板块接口调用失败
- **When** 管理员触发同步
- **Then** 系统从本地 JSON 映射文件加载行业数据
- **And** 将行业名称写入 stock_basic.industry
- **And** 返回结果中标注数据来源为本地降级

#### Scenario: 全部数据源不可用
- **Given** akshare 接口不可用，且本地 JSON 映射文件不存在
- **When** 管理员触发同步
- **Then** 系统返回错误信息，不修改任何数据
- **And** 同步状态中记录错误原因

### Requirement: 同步状态查询
系统 SHALL 提供实时查询同步进度和行业补全状态的能力。

#### Scenario: 查询行业补全率
- **Given** stock_basic 表中有 N 条记录
- **When** 管理员请求行业补全状态
- **Then** 返回总记录数、已填充行业字段数、补全率百分比

#### Scenario: 查询同步进行中状态
- **Given** 同步任务正在执行中
- **When** 查询同步状态
- **Then** 返回 `running: true`，包含已处理行业数和已更新股票数

#### Scenario: 同步完成后查询结果
- **Given** 同步任务已完成
- **When** 查询同步状态
- **Then** 返回 `running: false`，包含最终更新数量或错误信息

### Requirement: 同步质量保障
同步执行 MUST 确保行业补全率达到 90% 以上视为成功。

#### Scenario: 同步后验证补全率
- **Given** 同步任务已完成且无错误
- **When** 查询行业补全状态
- **Then** industry 字段非空率 SHALL 大于 90%
- **And** 如果补全率低于 90%，同步状态中 SHOULD 包含告警信息

### Requirement: 同步 API 鉴权
行业数据同步的写入端点 MUST 限制为管理员用户才能调用。

#### Scenario: 管理员触发同步
- **Given** 已登录用户具有管理员权限（is_admin=1）
- **When** POST /api/admin/industry/sync
- **Then** 请求被接受，返回 202

#### Scenario: 非管理员触发同步
- **Given** 已登录用户不是管理员
- **When** POST /api/admin/industry/sync
- **Then** 返回 403 Forbidden

#### Scenario: 未登录用户触发同步
- **Given** 用户未登录（session 中无 uid）
- **When** POST /api/admin/industry/sync
- **Then** 返回 403 Forbidden

## MODIFIED Requirements

### Requirement: 聚合器行业维度可用
策略组引擎的聚合器按行业维度对信号进行分组聚合时，SHALL 能正确读取已填充的 industry 字段。

#### Scenario: 聚合器按行业分组
- **Given** stock_basic.industry 字段已填充（补全率 > 90%）
- **And** signal_snapshot 中存在多条不同行业股票的信号
- **When** 聚合器执行 aggregate() 方法
- **Then** 信号按 industry 字段值分组
- **And** 同一行业内信号数量 >= min_stocks 时生成群体事件
