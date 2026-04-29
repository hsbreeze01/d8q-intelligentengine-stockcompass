# 变更
1. 加入概念股，程序启动时更新
2. 更新收藏和推荐，添加概念股相关查询能力
3. 优化dicstock字典表的更新逻辑

# 执行
1. 增加表
CREATE TABLE stock_concept (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    stock_code CHAR(10) NOT NULL COMMENT '股票代码',
    full_stock_code CHAR(10) NOT NULL COMMENT '完整股票代码',
    concept_name VARCHAR(100) NOT NULL COMMENT '概念名称',
    UNIQUE INDEX unique_stock_concept (stock_code, concept_name)
) COMMENT='stock_concept table';