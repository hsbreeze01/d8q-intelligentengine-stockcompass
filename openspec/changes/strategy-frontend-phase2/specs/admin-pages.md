# Delta Spec: 管理员页面样式完善

## MODIFIED Requirements

### Requirement: 策略组管理列表页样式

admin_list.html SHALL 以表格形式展示所有策略组，包含：
- 策略名称、维度、指标名、状态
- 订阅人数
- 操作按钮（编辑、暂停/恢复、删除）
- Compass 风格表格样式（斑马纹、悬停高亮、操作按钮蓝/红配色）

#### Scenario: 管理员查看策略列表

```
Given 管理员访问 /strategy/admin
When 页面加载完成
Then 页面调用 GET /api/strategy/groups 获取策略组列表
And 以表格展示所有策略组
And 每行显示操作按钮：编辑（蓝色）、暂停/恢复（黄色/绿色）、删除（红色）
```

### Requirement: 策略组编辑表单样式

admin_edit.html SHALL 提供策略组创建/编辑表单，使用 Compass 风格表单样式：
- 输入框统一圆角 + 边框样式
- 提交按钮 #1890FF 蓝色
- 表单验证提示

#### Scenario: 管理员编辑策略组

```
Given 管理员点击某策略组的"编辑"按钮
When 页面跳转到 /strategy/admin/{id}/edit
Then 表单预填当前策略组的名称、描述、维度、指标、阈值
And 管理员修改后点击"保存"，调用 PUT /api/strategy/groups/{id}
And 成功后跳回列表页
```

#### Scenario: 管理员创建新策略组

```
Given 管理员点击"新建策略组"按钮
When 页面跳转到 /strategy/admin/new
Then 展示空表单
And 管理员填写后点击"创建"，调用 POST /api/strategy/groups
And 成功后跳回列表页
```
