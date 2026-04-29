
truncate table indicators_daily;

truncate table indicators_asi_daily;

truncate table indicators_bias_daily;  

truncate table indicators_boll_daily;

truncate table indicators_kdj_daily;


truncate table indicators_kdj_daily_522;

truncate table indicators_ma_daily;

truncate table indicators_macd_daily;  

truncate table indicators_rsi_daily; 

truncate table indicators_vr_daily;  

truncate table indicators_wr_daily;  

truncate table stock_analysis;

TRUNCATE TABLE user_trade_simulation;

truncate table  stock_data_daily;
truncate table  stock_llm;

update dic_stock set  stock_data_daily_update_time = DATE_SUB(stock_data_daily_update_time, INTERVAL 1 DAY);
