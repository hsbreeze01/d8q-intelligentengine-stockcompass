## ADDED Requirements

### Requirement: 实体标识统一
所有入库的资讯/公告必须携带 `stock_codes`（列表）和 `entity_names`（列表），以 stock_code 为跨源关联主键。

#### Scenario: DataAgent 资讯入库
- **WHEN** DataAgent 保存一条资讯到数据库
- **THEN** 自动提取正文中的6位股票代码，并通过 StockShark 映射表补全 entity_names

#### Scenario: 跨源关联查询
- **WHEN** Compass 用 stock_code 查询资讯
- **THEN** 可直接通过 stock_codes 字段匹配，无需额外实体对齐

#### Scenario: 代码映射缺失
- **WHEN** 提取的 stock_code 在 StockShark dic_stock 中不存在
- **THEN** stock_codes 保留该代码，entity_names 对应位置填 null
