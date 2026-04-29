--股票市场所有股票数据
CREATE TABLE dic_stock (
    code VARCHAR(10) PRIMARY KEY COMMENT '代码',
    stock_name VARCHAR(100) NOT NULL COMMENT '名称',
    stock_prefix VARCHAR(10) NOT NULL COMMENT '前后缀',
    latest_price DECIMAL(10, 2) NOT NULL COMMENT '最新价',
    change_percentage DECIMAL(5, 2) NOT NULL COMMENT '涨跌幅',
    change_amount DECIMAL(10, 2) NOT NULL COMMENT '涨跌额',
    volume BIGINT NOT NULL COMMENT '成交量',
    turnover DECIMAL(20, 2) NOT NULL COMMENT '成交额',
    amplitude DECIMAL(5, 2) NOT NULL COMMENT '振幅',
    highest DECIMAL(10, 2) NOT NULL COMMENT '最高',
    lowest DECIMAL(10, 2) NOT NULL COMMENT '最低',
    open_today DECIMAL(10, 2) NOT NULL COMMENT '今开',
    close_yesterday DECIMAL(10, 2) NOT NULL COMMENT '昨收',
    volume_ratio DECIMAL(5, 2) NOT NULL COMMENT '量比',
    turnover_rate DECIMAL(5, 2) NOT NULL COMMENT '换手率',
    pe_ratio_dynamic DECIMAL(10, 2) NOT NULL COMMENT '市盈率-动态',
    pb_ratio DECIMAL(10, 2) NOT NULL COMMENT '市净率',
    total_market_value DECIMAL(20, 2) NOT NULL COMMENT '总市值',
    circulating_market_value DECIMAL(20, 2) NOT NULL COMMENT '流通市值',
    speed_of_increase DECIMAL(5, 2) NOT NULL COMMENT '涨速',
    change_5min DECIMAL(10, 2) NOT NULL COMMENT '5分钟涨跌',
    change_60days DECIMAL(10, 2) NOT NULL COMMENT '60日涨跌幅',
    change_ytd DECIMAL(10, 2) NOT NULL COMMENT '年初至今涨跌幅',
    last_update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    stock_data_daily_update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '每日数据更新时间'
) COMMENT='dic_stock table';

ALTER TABLE dic_stock
ADD COLUMN industry VARCHAR(20) NOT NULL DEFAULT 'none' COMMENT '行业';

ALTER TABLE dic_stock
ADD COLUMN status TINYINT NOT NULL DEFAULT 0 COMMENT '状态 0正常 1废弃';

--股票的每日数据
CREATE TABLE stock_data_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    date DATE NOT NULL COMMENT '日期',
    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    open DECIMAL(10, 2) NOT NULL COMMENT '开盘价',
    close DECIMAL(10, 2) NOT NULL COMMENT '收盘价',
    high DECIMAL(10, 2) NOT NULL COMMENT '最高价',
    low DECIMAL(10, 2) NOT NULL COMMENT '最低价',
    volume BIGINT NOT NULL COMMENT '成交量',
    turnover DECIMAL(20, 2) NOT NULL COMMENT '成交额',
    amplitude DECIMAL(5, 2) COMMENT '振幅',
    change_percentage DECIMAL(5, 2) COMMENT '涨跌幅',
    change_amount DECIMAL(10, 2) COMMENT '涨跌额',
    turnover_rate DECIMAL(10, 2) COMMENT '换手率'
) COMMENT='stock_data_daily table';



--任务的记录，根据这个可以知道最后执行的任务时间
--1	市场数据更新
--2	个股数据更新
--3	个股指标计算
CREATE TABLE task_record (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    name VARCHAR(255) NOT NULL COMMENT '任务名称',
    last_action_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后操作时间'
) COMMENT='task_record table';


#表名 
#id 自增ID
#stock_code char 10
#analysis_data json
#buy_advice json
#record_time date
#buy int
#sell int
#索引 stock_code 和 record_time 唯一索引

CREATE TABLE stock_analysis (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    stock_code CHAR(10) NOT NULL COMMENT '股票代码',
    analysis_data JSON NOT NULL COMMENT '分析数据',
    buy_advice JSON NOT NULL COMMENT '买入建议',
    record_time DATE NOT NULL COMMENT '记录时间',
    buy INT NOT NULL COMMENT '买入',
    sell INT NOT NULL COMMENT '卖出',
    UNIQUE INDEX unique_stock_record (stock_code, record_time)
) COMMENT='stock_analysis table';

CREATE INDEX idx_stock_analysis_code ON stock_analysis(stock_code);

#user 表
#id 自增ID
#username varchar 255
#password varchar 255
#login_time timestamp
#索引 username 唯一索引

CREATE TABLE user (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    username VARCHAR(255) NOT NULL COMMENT '用户名',
    password VARCHAR(255) NOT NULL COMMENT '密码',
    login_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '登录时间',
    UNIQUE INDEX unique_username (username)
) COMMENT='user table';

#用户股票关注列表
#id 自增ID
#user_id int
#stock_code char 10
#索引 user_id 和 stock_code 唯一索引

CREATE TABLE user_stock (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    user_id INT NOT NULL COMMENT '用户ID',
    stock_code CHAR(10) NOT NULL COMMENT '股票代码',
    UNIQUE INDEX unique_user_stock (user_id, stock_code)
) COMMENT='user_stock table';



#用户交易模拟记录
#id 自增ID
#user_id int
#stock_code char 10
#buy_price decimal 10,2
#buy_date date
#buy_type char 20
#check_date date
#check_price decimal 10,2
#sell_boll_date date
#sell_boll_price decimal 10,2
#sell_ma5_date date
#sell_ma5_price decimal 10,2
#sell_ma10_date date
#sell_ma10_price decimal 10,2
#sell_ma20_date date
#sell_ma20_price decimal 10,2
#stop_date date
#stop_price decimal 10,2
#索引 user_id 和 stock_code 和 buy_date 唯一索引

#用户交易模拟记录
--股票市场所有股票数据
CREATE TABLE user_trade_simulation (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    user_id INT NOT NULL COMMENT '用户ID',
    stock_code CHAR(10) NOT NULL COMMENT '股票代码',
    decide_date DATE NOT NULL COMMENT '策略决定的日期',
    decide_price DECIMAL(10, 2) NOT NULL COMMENT '策略定义的买入价格',
    decide_type CHAR(20) NOT NULL COMMENT '决策类型',
    execute_status tinyint NOT NULL COMMENT '执行状态 0 未执行 1 已执行 2 失败',
    buy_date DATE COMMENT '买入日期',
    buy_price DECIMAL(10, 2) NOT NULL COMMENT '买入价格',
    check_date DATE COMMENT '检查日期',
    check_price DECIMAL(10, 2) COMMENT '检查价格',
    sell_boll_date DATE COMMENT '布林卖出日期',
    sell_boll_price DECIMAL(10, 2) COMMENT '布林卖出价格',
    sell_ma5_date DATE COMMENT 'MA5卖出日期',
    sell_ma5_price DECIMAL(10, 2) COMMENT 'MA5卖出价格',
    sell_ma10_date DATE COMMENT 'MA10卖出日期',
    sell_ma10_price DECIMAL(10, 2) COMMENT 'MA10卖出价格',
    sell_ma20_date DATE COMMENT 'MA20卖出日期',
    sell_ma20_price DECIMAL(10, 2) COMMENT 'MA20卖出价格',
    stop_date DATE COMMENT '止损日期',
    stop_price DECIMAL(10, 2) COMMENT '止损价格',
    UNIQUE INDEX unique_user_stock_buy (user_id, stock_code, decide_date)
) COMMENT='user_trade_simulation table';


#表名称 stock_llm
#id 自增ID
#stock_code char 10
#record_time date
#content text
#索引 stock_code 和 record_time 唯一索引

CREATE TABLE stock_llm (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    stock_code CHAR(10) NOT NULL COMMENT '股票代码',
    record_time DATE NOT NULL COMMENT '记录时间',
    content text NOT NULL COMMENT '内容',
    UNIQUE INDEX unique_stock_record (stock_code, record_time)
) COMMENT='stock_llm table';


#表名称 login_log
#id 自增ID
#user_id int
#login_time timestamp
#ip varchar 255

CREATE TABLE login_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    user_id INT NOT NULL COMMENT '用户ID',
    login_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '登录时间',
    ip VARCHAR(255) NOT NULL COMMENT 'IP地址'
) COMMENT='login_log table';




#表名称 indicators_daily


id，自增，主键
stock_code 字符 10个，
date 类型是date，
macd_dif	macd_dea	macd_macd	kdj_k	kdj_d	kdj_j	boll_up	boll_mid boll_low	rsi_6	rsi_12	rsi_24	ma5	ma10	ma20	ma30	ma60 ，根据这些字段创建一个数据库的表结构，这些字段的值都是浮点型的，小数点最多3位
stock_code和date是唯一索引
按照上面的要求生产mysql的创建表的语句

CREATE TABLE indicators_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    stock_code CHAR(10) NOT NULL COMMENT '股票代码',
    date DATE NOT NULL COMMENT '日期',
    macd_dif FLOAT COMMENT 'MACD DIF',
    macd_dea FLOAT COMMENT 'MACD DEA',
    macd_macd FLOAT COMMENT 'MACD MACD',
    kdj_k FLOAT COMMENT 'KDJ K',
    kdj_d FLOAT COMMENT 'KDJ D',
    kdj_j FLOAT COMMENT 'KDJ J',
    boll_up FLOAT COMMENT 'BOLL UP',
    boll_mid FLOAT COMMENT 'BOLL MID',
    boll_low FLOAT COMMENT 'BOLL LOW',
    rsi_6 FLOAT COMMENT 'RSI 6',
    rsi_12 FLOAT COMMENT 'RSI 12',
    rsi_24 FLOAT COMMENT 'RSI 24',
    ma5 FLOAT COMMENT 'MA5',
    ma10 FLOAT COMMENT 'MA10',
    ma20 FLOAT COMMENT 'MA20',
    ma30 FLOAT COMMENT 'MA30',
    ma60 FLOAT COMMENT 'MA60',
    UNIQUE INDEX unique_stock_date (stock_code, date)
) COMMENT='indicators_daily table';



#表名称 概念股 stock_concept
#id 自增ID
#股票代码 stock_code char 10
#股票代码 full_stock_code char 10
#概念名称 concept_name varchar 100
# 唯一键 stock_code 和 concept_name
CREATE TABLE stock_concept (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    stock_code CHAR(10) NOT NULL COMMENT '股票代码',
    full_stock_code CHAR(10) NOT NULL COMMENT '完整股票代码',
    concept_name VARCHAR(100) NOT NULL COMMENT '概念名称',
    UNIQUE INDEX unique_stock_concept (stock_code, concept_name)
) COMMENT='stock_concept table';


#     代码    简称  事件类型                                               具体事项         交易日
#  000526  学大教育  资产重组  紫光集团有限公司管理人(以下简称“管理人”)履行紫光集团等七家企业实质合并重整案重整计划相关...  2025-02-20
#  000591   太阳能  资产重组  五常分布式项目预计总投资约为6,170.69万元,其中资本金不低于1,234.14万元(不超...  2025-02-20

CREATE TABLE stock_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    stock_code CHAR(10) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(100) NOT NULL COMMENT '股票简称',
    event_type VARCHAR(100) NOT NULL COMMENT '事件类型',
    event_detail TEXT NOT NULL COMMENT '具体事项',
    date DATE NOT NULL COMMENT '交易日'
) COMMENT='stock_events table';

# 表名称 根据产业和概念统计命中策略的统计 stock_analysis_stat
# id 自增ID
# 代码
# 类型 0 产业 1 概念
# 分类名称
# 日期
CREATE TABLE stock_analysis_stat (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    stock_code CHAR(10) NOT NULL COMMENT '股票代码',
    type TINYINT NOT NULL COMMENT '类型 0 产业 1 概念',
    category_name VARCHAR(100) NOT NULL COMMENT '分类名称',
    date DATE NOT NULL COMMENT '日期'
) COMMENT='stock_analysis_stat table';



#我要增加一张表，来存储用户购买的股票以及购买时的股票价格。然后每天都会更新股票的最新价格，并且根据最新价格来计算新的止损价格
CREATE TABLE user_stock_tracking (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    stock_code CHAR(10) NOT NULL COMMENT '股票代码',
    buy_price DECIMAL(10, 2) NOT NULL COMMENT '买入价格',
    buy_amount INT NOT NULL COMMENT '购买数量',
    buy_date DATE NOT NULL COMMENT '买入日期',
    stop_loss_pct DECIMAL(5, 2) NOT NULL COMMENT '止损百分比',
    current_price DECIMAL(10, 2) NOT NULL COMMENT '当前价格',
    stop_loss_price DECIMAL(10, 2) NOT NULL COMMENT '止损价格',
    last_update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间'
) COMMENT='User stock tracking and stop loss management';

