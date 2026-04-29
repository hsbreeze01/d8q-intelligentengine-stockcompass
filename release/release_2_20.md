


# 变更
1. 根据日期增加股票事件的记录stock_events
2. 策略成功的统计在计算策略的时候添加
3. 重构之前推荐中和概念，产业相关的代码



# 待执行
1. 增加表结构

CREATE TABLE stock_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    stock_code CHAR(10) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(100) NOT NULL COMMENT '股票简称',
    event_type VARCHAR(100) NOT NULL COMMENT '事件类型',
    event_detail TEXT NOT NULL COMMENT '具体事项',
    date DATE NOT NULL COMMENT '交易日'
) COMMENT='stock_events table';

2. 增加

CREATE TABLE stock_analysis_stat (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    stock_code CHAR(10) NOT NULL COMMENT '股票代码',
    type TINYINT NOT NULL COMMENT '类型 0 产业 1 概念',
    category_name VARCHAR(100) NOT NULL COMMENT '分类名称',
    date DATE NOT NULL COMMENT '日期'
) COMMENT='stock_analysis_stat table';