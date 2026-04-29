#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import sys
import akshare as ak
from talib import func

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
path = os.path.split(rootPath)[0]
# print(curPath,rootPath,path)
sys.path.append(path) # 这句是为了导入_config
sys.path.append(rootPath)

from stockfetch.db_kdj import *
from stockfetch.db_asi import *
from stockfetch.db_bias import *
from stockfetch.db_boll import *
from stockfetch.db_macd import *
from stockfetch.db_rsi import *
from stockfetch.db_vr import *
from stockfetch.db_wr import *
from stockfetch.db_ma import *


import logging
# from buy.cache import DicStockFactory

# logging.basicConfig(
#     filename=os.path.join(rootPath, 'stock.log'),
#     level=logging.DEBUG,
#     format='%(asctime)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s',
#     datefmt='%Y-%m-%d %H:%M:%S'
# )

# from DailyStockCheckTaskV2 import DailyStockCheckTaskV2


def test():

    # dicStock = DicStockFactory()
    # print(dicStock.isExist("600036"))

    #更新个股数据
    print("==========")
    # t = DailyStockCheckTaskV2()
    # t.action()
    print("====2======")
    # ask 是东方财富 股票编码不加头比如sh，sz
    # 东方财富-行情报价 -- 实时报价
    # stock_bid_ask_em_df = ak.stock_bid_ask_em(symbol="600036")
    # print(stock_bid_ask_em_df)
   
    # test1()
    pass


def test1():

    print("==========")
    code = '600036'

    # stock_zh_a_hist

    # ask 是东方财富 股票编码不加头比如sh，sz
    # 东方财富-行情报价 -- 实时报价
    stock_bid_ask_em_df = ak.stock_bid_ask_em(symbol=code)
    print(stock_bid_ask_em_df)

    #实时行情数据-东财
    # 序号	int64	-
    # 代码	object	-
    # 名称	object	-
    # 最新价	float64	-
    # 涨跌幅	float64	注意单位: %
    # 涨跌额	float64	-
    # 成交量	float64	注意单位: 手
    # 成交额	float64	注意单位: 元
    # 振幅	float64	注意单位: %
    # 最高	float64	-
    # 最低	float64	-
    # 今开	float64	-
    # 昨收	float64	-
    # 量比	float64	-
    # 换手率	float64	注意单位: %
    # 市盈率-动态	float64	-
    # 市净率	float64	-
    # 总市值	float64	注意单位: 元
    # 流通市值	float64	注意单位: 元
    # 涨速	float64	-
    # 5分钟涨跌	float64	注意单位: %
    # 60日涨跌幅	float64	注意单位: %
    # 年初至今涨跌幅	float64	注意单位: %
    stock_zh_a_spot_em_df = ak.stock_zh_a_spot_em() #全国的接口zh，除了能用这个获取实时数据，还可以根据这个数据获取股票的代码
    print(stock_zh_a_spot_em_df[stock_zh_a_spot_em_df['代码'] == code].to_string())


    #东方财富的历史数据
    stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20250301", end_date='20250701', adjust="qfq")
    print(stock_zh_a_hist_df)

    # date	object	交易日
    # open	float64	开盘价
    # high	float64	最高价
    # low	float64	最低价
    # close	float64	收盘价
    # volume	float64	成交量; 注意单位: 股
    # amount	float64	成交额; 注意单位: 元
    # outstanding_share	float64	流动股本; 注意单位: 股
    # turnover	float64	换手率=成交量/流动股本
    # qfq 前复权的数据是和看软件一样的
    stock_zh_a_daily_qfq_df = ak.stock_zh_a_daily(symbol="sh600036", start_date="20250301", end_date="20250701", adjust="qfq")
    print(stock_zh_a_daily_qfq_df)

pass


def test2():
    code = '600036'
    #东方财富的历史数据
    #"日期",
    #"股票代码",
    #"开盘",
    #"收盘",
    #"最高",
    #"最低",
    #"成交量", 单位手
    #"成交额",
    #"振幅",
    #"涨跌幅",
    #"涨跌额",
    #"换手率", 按照百分比为单位
    #目前在用的算法
    stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20250301", end_date='20250701', adjust="qfq")
    print(stock_zh_a_hist_df)

    # date	object	交易日
    # open	float64	开盘价
    # high	float64	最高价
    # low	float64	最低价
    # close	float64	收盘价
    # volume	float64	成交量; 注意单位: 股
    # amount	float64	成交额; 注意单位: 元
    # outstanding_share	float64	流动股本; 注意单位: 股
    # turnover	float64	换手率=成交量/流动股本
    # qfq 前复权的数据是和看软件一样的
    stock_zh_a_daily_qfq_df = ak.stock_zh_a_daily(symbol="sh600036", start_date="20250301", end_date="20250701", adjust="qfq")
    print(stock_zh_a_daily_qfq_df)

    # Compare the two dataframes
    print("\nComparing the two data sources:")
    
    # Rename columns in stock_zh_a_hist_df to match stock_zh_a_daily_qfq_df
    hist_df_renamed = stock_zh_a_hist_df.rename(columns={
        '日期': 'date',
        '开盘': 'open',
        '收盘': 'close', 
        '最高': 'high',
        '最低': 'low',
        '成交量': 'volume',
        '成交额': 'amount',
        '换手率': 'turnover'
    })

    # Select common columns for comparison
    common_columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount','turnover']
    df1 = hist_df_renamed[common_columns]
    df2 = stock_zh_a_daily_qfq_df[common_columns]

    # Adjust volume and turnover in df2
    df2['volume'] = (df2['volume'] / 100).round()  # Convert volume to match df1 and round to integer
    df2['turnover'] = round(df2['turnover'] * 100, 2)  # Convert turnover to percentage and round to 2 decimal places

    # Convert date columns to same format for comparison
    df1['date'] = pd.to_datetime(df1['date'])
    df2['date'] = pd.to_datetime(df2['date'])

    # Sort both dataframes by date
    df1 = df1.sort_values('date')
    df2 = df2.sort_values('date')

    # Calculate differences
    print("\nChecking for value differences:")
    for column in common_columns[1:]:  # Skip date column
        diff = np.abs(df1[column] - df2[column])
        max_diff = diff.max()
        print(f"{column}: Maximum difference = {max_diff}")
        
        # Check if values are significantly different (>1% difference)
        significant_diff = diff[diff > df1[column].mean() * 0.01]
        if not significant_diff.empty:
            print(f"Found {len(significant_diff)} significant differences in {column}")

    # Check for missing dates
    dates1 = set(df1['date'])
    dates2 = set(df2['date'])
    
    missing_in_df1 = dates2 - dates1
    missing_in_df2 = dates1 - dates2
    
    if missing_in_df1:
        print("\nDates missing in first dataset:", missing_in_df1)
    if missing_in_df2:
        print("\nDates missing in second dataset:", missing_in_df2)



def get_kline_daily(symbol, start_date, end_date,api=1, adjust="qfq"):
    #东方财富的历史数据
    #"日期",
    #东方财富的历史数据
    #"日期",
    #"股票代码",
    #"开盘",
    #"收盘",
    #"最高",
    #"最低",
    #"成交量", 单位手
    #"成交额",
    #"振幅",
    #"涨跌幅",
    #"涨跌额",
    #"换手率", 按照百分比为单位
    # stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20250301", end_date='20250701', adjust="qfq")
    # print(stock_zh_a_hist_df)

    # date	object	交易日
    # open	float64	开盘价
    # high	float64	最高价
    # low	float64	最低价
    # close	float64	收盘价
    # volume	float64	成交量; 注意单位: 股
    # amount	float64	成交额; 注意单位: 元
    # outstanding_share	float64	流动股本; 注意单位: 股
    # turnover	float64	换手率=成交量/流动股本
    # qfq 前复权的数据是和看软件一样的
    # stock_zh_a_daily_qfq_df = ak.stock_zh_a_daily(symbol="sh600036", start_date="20250301", end_date="20250701", adjust="qfq")
    # print(stock_zh_a_daily_qfq_df)

    if api == 1:
        # Use stock_zh_a_hist
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust=adjust)
        # Already in the desired format
        return df
    else:
        # Use stock_zh_a_daily
        # Need to add "sh" or "sz" prefix based on symbol
        #0 3 sz
        #4 8 9 bj
        #6  sh
        if symbol.startswith('6'):
            prefix = 'sh'
        elif symbol.startswith(('0', '3')):
            prefix = 'sz' 
        elif symbol.startswith(('4', '8', '9')):
            prefix = 'bj'
        else:
            raise ValueError(f"Invalid stock code prefix: {symbol}")

        df = ak.stock_zh_a_daily(symbol=f"{prefix}{symbol}", start_date=start_date, end_date=end_date, adjust=adjust)
        
        # Create a new dataframe with the desired format
        result_df = pd.DataFrame()
        result_df['日期'] = df['date']
        result_df['股票代码'] = symbol
        result_df['开盘'] = df['open']
        result_df['收盘'] = df['close']
        result_df['最高'] = df['high']
        result_df['最低'] = df['low']
        result_df['成交量'] = (df['volume'] / 100).round()  # Convert from shares to lots
        result_df['成交额'] = df['amount']
        result_df['振幅'] = 0  # Not available in stock_zh_a_daily
        result_df['涨跌幅'] = 0  # Not available in stock_zh_a_daily
        result_df['涨跌额'] = 0  # Not available in stock_zh_a_daily
        result_df['换手率'] = round(df['turnover'] * 100, 2)  # Convert to percentage
        return result_df

    pass
# test()


rt = get_kline_daily(symbol='000001', start_date="20250615", end_date='20250618', api=0)
print(rt)