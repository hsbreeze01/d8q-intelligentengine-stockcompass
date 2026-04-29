import os
import sys
from buy.DBClient import DBClient
from buy.utils import *
from datetime import timedelta
import numpy
import akshare as ak
from buy.cache import *
import requests
import json
import pandas
import time
import talib as tl
import numpy as np
import traceback

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
path = os.path.split(rootPath)[0]
# print(curPath,rootPath,path)
sys.path.append(path) # 这句是为了导入_config
sys.path.append(rootPath)

# from stockfetch.db_kdj import *
# from stockfetch.db_asi import *
# from stockfetch.db_bias import *
# from stockfetch.db_boll import *
# from stockfetch.db_macd import *
# from stockfetch.db_rsi import *
# from stockfetch.db_vr import *
# from stockfetch.db_wr import *
# from stockfetch.db_ma import *

# from calc_indicator import calcIndicatorAndSaveToDB
from main_analysis import summery_trade_json
from main_analysis import buy_advice_v2

from main_simulation import *
import threading
from llm import DoubaoLLM
import markdown


class StockTask:
    logger = logging.getLogger("my_logger")
    # global_lock = threading.Lock()

    def __init__(self, stock_code, last_update_time):
        self.stock_code = stock_code
        self.last_update_time = last_update_time

    def action(self):
        #更新股票数据
        
        # try:
        #     self.updateData()
        # except Exception as e:
        #     self.logger.error(f"Error updating data for stock {self.stock_code}: {e}")
        #     #如果遇到异常则不再继续
        #     return

        # #指标类型的东西现在是全局类，需要加锁
        # # self.logger.debug(self.stock_code+"wait for update indicator")
        # # with self.global_lock:
        # #     # self.logger.debug(self.stock_code+"doing update indicator")
        # #     self.updateIndicator()

        # #更新指标数据
        # self.updateIndicatorV2()
        # #分析股票
        # self.updateTradeAnalysis()

        # #模拟交易
        # simulation_gen(self.stock_code,1)
        # simulation_buy(self.stock_code,1)
        # simulation_sell(self.stock_code,1)

        try:
            self.updateData()
        except Exception as e:
            self.logger.error(f"An error occurred while updating stock {self.stock_code}: {e}\n"
                     f"Traceback: {traceback.format_exc()}")
            return

        try:
            self.updateIndicatorV2()
        except Exception as e:
            self.logger.error(f"An error occurred while updating stock {self.stock_code}: {e}\n"
                     f"Traceback: {traceback.format_exc()}")
            return

        try:
            self.updateTradeAnalysis()
        except Exception as e:
            self.logger.error(f"An error occurred while updating stock {self.stock_code}: {e}\n"
                     f"Traceback: {traceback.format_exc()}")
            return

        try:
            simulation_gen(self.stock_code, 1)
            simulation_buy(self.stock_code, 1)
            simulation_sell(self.stock_code, 1)
        except Exception as e:
            self.logger.error(f"An error occurred while simulation stock {self.stock_code}: {e}\n"
                     f"Traceback: {traceback.format_exc()}")
            return
        
        # 先不打开，花钱太快
        # try:
        #     self.updateFavoriteLLM()
        # except Exception as e:
        #     self.logger.error(f"An error occurred while updateFavoriteLLM stock {self.stock_code}: {e}\n"
        #              f"Traceback: {traceback.format_exc()}")
        #     return
       

        pass

    #更新股票数据
    def updateData(self):
       
        #当天16点之后更新过则不再更新，如果是16点之前每次都可以更新，因为盘中数据会有变化
        if dayDif(datetime.datetime.now(), self.last_update_time) <= 0 and self.last_update_time.hour > 16:
            self.logger.debug(self.stock_code+" update in "+ str(self.last_update_time))
            return False

        mc = DBClient()
        
        try:
            # 根据股票id补全每日股票数据
            # self.logger.debug("-----1-------"+self.stock_code)
            max_record_time = mc.select_one('select max(date) from stock_data_daily where stock_code=%s', (self.stock_code,))
            # self.logger.debug("-----2-------"+self.stock_code)
            
            start = '20240101'
            if max_record_time[1]['max(date)'] is not None:
                #默认从最大的时间-1天，因为更新的时候有可能是当天的盘中时间
                start = (max_record_time[1]['max(date)'] - timedelta(days=1)).strftime('%Y%m%d')
                self.logger.debug(self.stock_code + " max record time: " + start)

            end = datetime.datetime.now().strftime('%Y%m%d')
            self.logger.debug(self.stock_code + " start: " + start + " end: " + end)

            #获取股票市场最新的每日数据
            # stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol=self.stock_code, period="daily", start_date=start, end_date=end, adjust="qfq",timeout=60)
            # self.logger.debug(stock_zh_a_hist_df)
            stock_zh_a_hist_df = self.get_kline_daily( start_date=start, end_date=end, adjust="qfq",api=0,timeout=60)
            
            #更新所有数据
            for index2, row in stock_zh_a_hist_df.iterrows():
                sql = f"""
                REPLACE INTO stock_data_daily (
                    date,
                    stock_code,
                    open,
                    close,
                    high,
                    low,
                    volume,
                    turnover,
                    amplitude,
                    change_percentage,
                    change_amount,
                    turnover_rate
                ) VALUES (
                    '{row['日期']}',
                    '{row['股票代码']}',
                    {row['开盘']},
                    {row['收盘']},
                    {row['最高']},
                    {row['最低']},
                    {row['成交量']},
                    {row['成交额']},
                    {row['振幅']},
                    {row['涨跌幅']},
                    {row['涨跌额']},
                    {row['换手率']}
                );
                """
                
                # print(sql)
                # self.logger.debug("-----3-------"+self.stock_code)

                mc.execute(sql)
                # self.logger.debug("-----4-------"+self.stock_code)

                pass
            
            # 更新最新数据，同时更新股票的最后刷新时间
            sql = "update dic_stock set stock_data_daily_update_time= '"+ datetime.datetime.strftime(datetime.datetime.now(),'%Y-%m-%d %H:%M:%S') +"' where code='"+self.stock_code+"';"
            # self.logger.debug("-----5-------"+self.stock_code)
            
            mc.execute(sql)
            # self.logger.debug("-----6-------"+self.stock_code)
            
            mc.commit()
        except Exception as ex:
            self.logger.error(f"An error occurred while updating stock {self.stock_code}: {ex}\n"
                     f"Traceback: {traceback.format_exc()}")
            mc.rollback()
            return False
        finally:
            mc.close()
            pass
        
        return True

    #更新股票类似KDJ等相关的数据
    # def updateIndicator(self):
    #     #根据股票id补全每日股票数据
    #     mc = DBClient()
    #     max_record_time = mc.select_one('select max(date) from stock_data_daily where stock_code=%s', (self.stock_code,))
    #     mc.close()

    #     #默认从最大的时间-1天，因为更新的时候有可能是当天的盘中时间
    #     endDate = (max_record_time[1]['max(date)']).strftime('%Y%m%d')

    #     # self.logger.debug('update indicator:',self.stock_code,endDate)
    #     # calcIndicatorAndSaveToDB(self.stock_code,endDate)
    #     #设置数据来源
    #     set_data_backend(DBDataBackend())

    #     #获取数据
    #     T(endDate)#日期必须是开盘日（有数据的那一天）
    #     S(self.stock_code)
    #     set_start_date('20240101') #设置开始日期

    #     #kdj
    #     kdj_daily = kdj_daily(self.stock_code)
    #     kdj_daily.insert(KDJ(),DATETIME)

    #     kdj_daily = kdj_daily(self.stock_code,"522")
    #     kdj_daily.insert(KDJ(5,2,2),DATETIME)

    #     #asi
    #     asidaily = ASIDaily(self.stock_code)
    #     asidaily.insert(ASI(),DATETIME)

    #     #bias
    #     biasdaily = BIASDaily(self.stock_code)
    #     biasdaily.insert(BIAS(),DATETIME)

    #     # boll
    #     daily = BOLLDaily(self.stock_code)
    #     daily.insert(BOLL(),DATETIME)

    #     # macd 数据貌似几个网站都不同
    #     daily = MACDDaily(self.stock_code)
    #     daily.insert(MACD(),DATETIME)

    #     daily = RSIDaily(self.stock_code)
    #     daily.insert(RSI(),DATETIME)

    #     daily = MADaily(self.stock_code)
    #     daily.insert(MA(CLOSE,5),MA(CLOSE,10),MA(CLOSE,20),MA(CLOSE,30),MA(CLOSE,60),DATETIME)

        
    #     pass
    
    #更新指标相关数据
    def updateIndicatorV2(self):
        #根据股票id补全每日股票数据
        mc = DBClient()
        max_record_time = mc.select_one('select max(date) from stock_data_daily where stock_code=%s', (self.stock_code,))
        
        #如果没有股票记录
        if max_record_time[1]['max(date)'] is None:
            self.logger.debug(self.stock_code + "has not max record time")
            mc.close()
            return

        endDate = (max_record_time[1]['max(date)']).strftime('%Y%m%d')
        startDate = '20240101'
        count,rows,cols = mc.select_many_cols('select * from stock_data_daily where stock_code=%s and date >=%s and date <= %s  order by date', (self.stock_code,startDate,endDate))

        max_indicators_record_time = mc.select_one('select max(date) from indicators_daily where stock_code=%s', (self.stock_code,))
        mc.close()

        start = '20240101'
        start = datetime.datetime.strptime(start, '%Y%m%d').date()
        if max_indicators_record_time[1]['max(date)'] is not None:
            start = max_indicators_record_time[1]['max(date)']
            # self.logger.debug(self.stock_code + " max record_time time: " + start)

        df = pd.DataFrame(rows, columns=cols)
        # df.rename(columns={'record_time':'date'},inplace=True) 
        del df["id"]
        del df["stock_code"]
        del df["turnover"]
        del df["amplitude"]
        del df["change_percentage"]
        del df["change_amount"]
        del df["turnover_rate"]
        # df["datetime"] = df["date"].apply(lambda x: int(x.strftime("%Y-%m-%d").replace("-", "")) * 1000000)

        result = self.calc_indicators(df)
        if result is not None:
            mc = DBClient()
            for index, row in result.iterrows():
                #比最大日期还小的数据不需要更新，每次更新都会把最后一条记录更新，防止在盘中更新数据
                if row['date'] < start:
                    continue

                sql = f"""
                REPLACE INTO indicators_daily (
                    date,
                    stock_code,
                    macd_dif,
                    macd_dea,
                    macd_macd,
                    kdj_k,
                    kdj_d,
                    kdj_j,
                    boll_up,
                    boll_mid,
                    boll_low,
                    rsi_6,
                    rsi_12,
                    rsi_24,
                    ma5,
                    ma10,
                    ma20,
                    ma30,
                    ma60
                ) VALUES (
                    '{row['date']}',
                    '{self.stock_code}',
                    {row['macd_dif']},
                    {row['macd_dea']},
                    {row['macd_macd']},
                    {row['kdj_k']},
                    {row['kdj_d']},
                    {row['kdj_j']},
                    {row['boll_up']},
                    {row['boll_mid']},
                    {row['boll_low']},
                    {row['rsi_6']},
                    {row['rsi_12']},
                    {row['rsi_24']},
                    {row['ma5']},
                    {row['ma10']},
                    {row['ma20']},
                    {row['ma30']},
                    {row['ma60']}
                );
                """
                mc.execute(sql)
                pass
            mc.commit()
            mc.close()

        pass



    def calc_indicators(self,data, end_date=None, threshold=1000, calc_threshold=None):
        """
        计算kdj等指标
        Parameters:
        data (pd.DataFrame): DataFrame containing stock data with columns 'date', 'close', 'high', 'low', 'open'.
        end_date (datetime, optional): 截取结束日期之前的记录
        threshold (int, optional): 最后返回多少条记录
        calc_threshold (int, optional): 截取数据最后几行进行计算. Defaults to None.
        Returns:
        pd.DataFrame: DataFrame with calculated indicators added as columns.
        None: If an exception occurs during calculation.

        Indicators calculated:
        - MACD: Moving Average Convergence Divergence
        - kdj_k: Stochastic Oscillator
        - Bollinger Bands
        - RSI: Relative Strength Index
        - MA: Moving Averages (5, 10, 20, 30, 60 periods)

        Note:
        - The function uses the TA-Lib library for indicator calculations.
        - Some indicators are commented out and not calculated.
        - Handles NaN values by replacing them with 0.0.
        """

        try:
            isCopy = False
            if end_date is not None:
                mask = (data['date'] <= end_date)
                data = data.loc[mask]
                isCopy = True

            if calc_threshold is not None:
                data = data.tail(n=calc_threshold)
                isCopy = True

            if isCopy:
                data = data.copy()

            data['close'] = data['close'].astype(float)
            data['high'] = data['high'].astype(float)
            data['low'] = data['low'].astype(float)
            data['open'] = data['open'].astype(float)

            with np.errstate(divide='ignore', invalid='ignore'):
                # macd
                data.loc[:, 'macd'], data.loc[:, 'macds'], data.loc[:, 'macdh'] = tl.MACD(
                    data['close'].values, fastperiod=12, slowperiod=26, signalperiod=9)
                
                data['macd'].values[np.isnan(data['macd'].values)] = 0.0
                data['macds'].values[np.isnan(data['macds'].values)] = 0.0
                data['macdh'].values[np.isnan(data['macdh'].values)] = 0.0
                data.rename(columns={'macd': 'macd_dif'}, inplace=True)
                data.rename(columns={'macds': 'macd_dea'}, inplace=True)
                data.rename(columns={'macdh': 'macd_macd'}, inplace=True)

                data['macd_macd'] = data['macd_macd'] * 2#根据股票软件的算法需要*2 macd_macd = (DIFF - DEA) * 2


                # kdj_k
                data.loc[:, 'kdj_k'], data.loc[:, 'kdj_d'] = tl.STOCH(
                    data['high'].values, data['low'].values, data['close'].values, fastk_period=9,
                    slowk_period=5, slowk_matype=1, slowd_period=5, slowd_matype=1)
                data['kdj_k'].values[np.isnan(data['kdj_k'].values)] = 0.0
                data['kdj_d'].values[np.isnan(data['kdj_d'].values)] = 0.0
                data.loc[:, 'kdj_j'] = 3 * data['kdj_k'].values - 2 * data['kdj_d'].values

                # boll 计算结果和stockstats不同boll_up,boll_low
                data.loc[:, 'boll_up'], data.loc[:, 'boll_mid'], data.loc[:, 'boll_low'] = tl.BBANDS \
                    (data['close'].values, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
                data['boll_up'].values[np.isnan(data['boll_up'].values)] = 0.0
                data['boll_mid'].values[np.isnan(data['boll_mid'].values)] = 0.0
                data['boll_low'].values[np.isnan(data['boll_low'].values)] = 0.0

                # rsi
                data.loc[:, 'rsi_6'] = tl.RSI(data['close'].values, timeperiod=6)
                data['rsi_6'].values[np.isnan(data['rsi_6'].values)] = 0.0
                data.loc[:, 'rsi_12'] = tl.RSI(data['close'].values, timeperiod=12)
                data['rsi_12'].values[np.isnan(data['rsi_12'].values)] = 0.0
                data.loc[:, 'rsi_24'] = tl.RSI(data['close'].values, timeperiod=24)
                data['rsi_24'].values[np.isnan(data['rsi_24'].values)] = 0.0

                # MA
                data.loc[:, 'ma5'] = tl.MA(data['close'].values, timeperiod=5)
                data['ma5'].values[np.isnan(data['ma5'].values)] = 0.0
                data.loc[:, 'ma10'] = tl.MA(data['close'].values, timeperiod=10)
                data['ma10'].values[np.isnan(data['ma10'].values)] = 0.0

                data.loc[:, 'ma20'] = tl.MA(data['close'].values, timeperiod=20)
                data['ma20'].values[np.isnan(data['ma20'].values)] = 0.0

                data.loc[:, 'ma30'] = tl.MA(data['close'].values, timeperiod=30)
                data['ma30'].values[np.isnan(data['ma30'].values)] = 0.0

                data.loc[:, 'ma60'] = tl.MA(data['close'].values, timeperiod=60)
                data['ma60'].values[np.isnan(data['ma60'].values)] = 0.0

            if threshold is not None:
                data = data.tail(n=threshold).copy()
            return data
        except Exception as e:
            self.logger.error(f"An error occurred while updating stock {self.stock_code}: {e}\n"
                     f"Traceback: {traceback.format_exc()}")
        return None


    #根据指标，进行买卖分析的判断
    def updateTradeAnalysis(self):
        
        mc = DBClient()
        try:
            #查找最大的分析时间
            count,max_record_time = mc.select_one('select max(record_time) from stock_analysis where stock_code=%s', (self.stock_code,))
            #从8月份开始，之前的数据需要构建指标，数据不足时指标不准确
            start = '20240801'

            if max_record_time['max(record_time)'] is not None:
                #默认从最大的时间-1天，因为更新的时候有可能是当天的盘中时间
                start = (max_record_time['max(record_time)'] - timedelta(days=1)).strftime('%Y%m%d')
                pass
            
            stock = dicStock.data.loc[dicStock.data['code'] == self.stock_code]

            if stock.empty:
                self.logger.error(f"Stock {self.stock_code} not found in dic_stock.")
                return False

            sql = f"SELECT * FROM stock_data_daily WHERE stock_code='{self.stock_code}' AND date > '{start}'"
            count,result = mc.select_many(sql)

            #需要先删除当天所有已经跑过的，否则如果盘中触发过，但是盘后并不触发就会报错

            #删除已存在的今天的统计记录
            sql_delete = f"DELETE FROM stock_analysis WHERE stock_code='{self.stock_code}' AND record_time > '{start}'"
            mc.execute(sql_delete)

            sql_delete = f"DELETE FROM stock_analysis_stat WHERE stock_code='{self.stock_code}' AND date > '{start}'"
            mc.execute(sql_delete)
            
            
            #统计买入和卖出的次数
            for row in result:
                #如果指标数量不够，不足以计算
                count_indicators = mc.select_one('SELECT COUNT(*) FROM indicators_daily WHERE stock_code=%s AND date<=%s', (self.stock_code, row['date']))
                if count_indicators[1]['COUNT(*)'] < 30:
                    continue

                data = summery_trade_json(self.stock_code,row['date'].strftime('%Y%m%d'))
                # self.logger.debug(data)
                buy,sell,advice = buy_advice_v2(data)
                
                sql_insert = """
                INSERT INTO stock_analysis (
                    stock_code,
                    analysis_data,
                    buy_advice,
                    record_time,
                    buy,
                    sell
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                ) ON DUPLICATE KEY UPDATE
                    analysis_data = VALUES(analysis_data),
                    buy_advice = VALUES(buy_advice),
                    buy = VALUES(buy),
                    sell = VALUES(sell)
                """
                mc.execute(sql_insert, (self.stock_code, json.dumps(data), json.dumps(advice), row['date'], buy, sell))

                if buy > 0:
                    #插入行业统计
                    industry = stock['industry'].values[0]
                    sql_insert_stat = f"""
                    INSERT INTO stock_analysis_stat (
                        stock_code,
                        type,
                        category_name,
                        date
                    ) VALUES (
                        '{self.stock_code}',
                        0,
                        '{industry}',
                        '{row['date']}'
                    )
                    """
                    #插入概念统计
                    mc.execute(sql_insert_stat)
                    concepts = stock['concepts'].values[0]
                    for concept in concepts:
                        sql_insert_stat_concept = f"""
                        INSERT INTO stock_analysis_stat (
                            stock_code,
                            type,
                            category_name,
                            date
                        ) VALUES (
                            '{self.stock_code}',
                            1,
                            '{concept}',
                            '{row['date']}'
                        )
                        """
                        mc.execute(sql_insert_stat_concept)
                
            mc.commit()
            pass
        except Exception as e:
            self.logger.error(f"An error occurred while updating stock {self.stock_code}: {e}\n"
                     f"Traceback: {traceback.format_exc()}")
            mc.rollback()
            return False
        finally:
            mc.close()
            pass
    
    #更新被加入收藏的股票的LLM建议
    def updateFavoriteLLM(self):
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        # today = '2025-02-14'

        mc = DBClient()
        
        #检查是否已有数据，如果有则不处理
        sql_check = f"SELECT COUNT(*) FROM stock_llm WHERE stock_code='{self.stock_code}' AND record_time='{today}'"
        count, result_check = mc.select_one(sql_check)
        if result_check['COUNT(*)'] > 0:
            mc.close()
            self.logger.debug(f"Stock {self.stock_code} has already been checked.")
            return

        try:
            sql = f"SELECT a.*,c.stock_name FROM stock_analysis a, user_stock b,dic_stock c WHERE a.stock_code = '{self.stock_code}' and a.record_time = '{today}' AND a.stock_code = b.stock_code and a.stock_code = c.code"
            count, row = mc.select_one(sql)
        except Exception as e:
            self.logger.error(f"An error occurred while fetching favorite stocks: {e}\n"
             f"Traceback: {traceback.format_exc()}")
        finally:
            mc.close()
        
        #如果没有人收藏，也不处理
        if count == 0:
            self.logger.debug(f"No one has favorited stock {self.stock_code}")
            return

        stock_code = row['stock_code']
        record_time = row['record_time']
        analysis_data = json.loads(row['analysis_data'])
        buy_advice = json.loads(row['buy_advice'])
        analysis_data = json.loads(analysis_data)
        buy_advice = json.loads(buy_advice)
        

        buy = row['buy']
        sell = row['sell']
        stock_name = row['stock_name']

        message = generate_plain_text(stock_code, stock_name, record_time, buy, sell, buy_advice, analysis_data)
        llm = DoubaoLLM()
        
        try:
            message = llm.stock_message(message)
        except Exception as ex:
            self.logger.error(ex)
            return

        if message == None or len(message) < 100:
            self.logger.error("The generated message is too short.")
            return
        
        try:
            mc = DBClient()
            sql = f"INSERT INTO stock_llm (stock_code, record_time, content) VALUES ('{stock_code}', '{record_time}', '{message}')"
            mc.execute(sql)
            mc.commit()
        except Exception as ex:
            self.logger.error(ex)
            mc.rollback()
        finally:
            mc.close()

        pass

    
    def get_kline_daily(self, start_date, end_date,api=1, adjust="qfq",timeout=60):
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
        symbol = self.stock_code

        if api == 1:
            # Use stock_zh_a_hist
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust=adjust,timeout=timeout)
            # Already in the desired format
            self.logger.debug(f"Stock {symbol} - API: {api} - DataFrame length: {len(df)}")
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
            self.logger.debug(f"Stock {symbol} - API: {api} - DataFrame length: {len(df)}")
            
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



def generate_plain_text(stock_code,stock_name ,record_time, buy, sell, buy_advice, analysis_data):
    text = []

    # 标题
    text.append(f"{stock_code} {stock_name} {record_time} 的分析记录\n")

    # 建议
    text.append("1.建议\n")
    text.append(f"策略命中情况 买入策略编号 {buy} 次 卖出提示 {sell} 次\n")
    text.append(f"趋势:{buy_advice.get('trend_advice_comments', '')}\n")
    text.append(f"强弱:{buy_advice.get('strength_advice_comments', '')}\n")
    text.append(f"交叉:{buy_advice.get('cross_advice_comments', '')}\n")

    if 'kdj_head_comments' in buy_advice and len(buy_advice['kdj_head_comments']) > 0:
        text.append(f"{buy_advice['kdj_head_comments']}\n")
    if 'kdj_bottom_comments' in buy_advice and len(buy_advice['kdj_bottom_comments']) > 0:
        text.append(f"{buy_advice['kdj_bottom_comments']}\n")
    if 'high_change' in buy_advice and len(buy_advice['high_change']) > 0:
        text.append(f"{buy_advice['high_change']}\n")
    if 'low_change' in buy_advice and len(buy_advice['low_change']) > 0:
        text.append(f"{buy_advice['low_change']}\n")
    if 'cross_change' in buy_advice and len(buy_advice['cross_change']) > 0:
        text.append(f"{buy_advice['cross_change']}\n")

    text.append("买入建议\n")
    for i in range(1, 11):
        key = f'summary_advice_{i}'
        if key in buy_advice and len(buy_advice[key]) > 0:
            text.append(f"{buy_advice[key]}\n")

    # 指数分析明细
    text.append("2.指数分析明细\n")
    text.append("RSI\n")
    text.append(f"强弱 {analysis_data.get('rsi_strength', '')}\n")
    text.append(f"趋势 {analysis_data.get('rsi1_slope', '')} \n")
    text.append(f"交叉 {analysis_data.get('rsi_cross', '')}\n")

    text.append("KDJ\n")
    text.append(f"强弱 {analysis_data.get('kdj_strength', '')}\n")
    text.append(f"趋势 kdj {analysis_data.get('kdj_slope', '')}\n")
    text.append(f"交叉 {analysis_data.get('kdj_cross', '')}\n")
    text.append(f"头部形成:{analysis_data.get('kdj_head_bottom_head', '')} 底部形成:{analysis_data.get('kdj_head_bottom_bottom', '')}\n")

    text.append("MACD\n")
    text.append(f"强弱 {analysis_data.get('macd_strength', '')}\n")
    text.append(f"趋势 macd {analysis_data.get('macd_slope', '')}\n")

    text.append("MA\n")
    text.append(f"趋势 ma5 {analysis_data.get('ma5_slope', '')} ma10 {analysis_data.get('ma10_slope', '')} ma20 {analysis_data.get('ma20_slope', '')}\n")

    text.append("VOLUME\n")
    text.append(f"趋势 {analysis_data.get('volume_slope', '')}\n")

    text.append("3.交易记录\n")
    for key in reversed(analysis_data['trade']):
        trade = analysis_data['trade'][key]
        text.append(f"{key} 开盘:{trade.get('judge_open', '')} 收盘:{trade.get('judge', '')}\n")
        if len(trade.get('judge_high', '')) > 0:
            text.append(f"❗️股价 {trade['judge_high']}\n")
        if len(trade.get('judge_low', '')) > 0:
            text.append(f"❗️股价 {trade['judge_low']}\n")
        if len(trade.get('judge_cross', '')) > 0:
            text.append(f"❗️ {trade['judge_cross']}\n")
        text.append(f"{trade.get('today', '')}\n")
        text.append(f"MA指标 5日 [{trade.get('ma5', '')} {trade.get('judge_ma5', '')}")
        if len(trade.get('buy_signal_ma5', '')) > 0:
            text.append(f" |👆{trade['buy_signal_ma5']}")
        if len(trade.get('sell_signal_ma5', '')) > 0:
            text.append(f" |👇{trade['sell_signal_ma5']}")
        text.append("]\n")

        text.append(f"10日 [{trade.get('ma10', '')} {trade.get('judge_ma10', '')}")
        if len(trade.get('buy_signal_ma10', '')) > 0:
            text.append(f" |👆{trade['buy_signal_ma10']}")
        if len(trade.get('sell_signal_ma10', '')) > 0:
            text.append(f" |👇{trade['sell_signal_ma10']}")
        text.append("]\n")

        text.append(f"20日 [{trade.get('ma20', '')} {trade.get('judge_ma20', '')}")
        if len(trade.get('buy_signal_ma20', '')) > 0:
            text.append(f" |👆{trade['buy_signal_ma20']}")
        if len(trade.get('sell_signal_ma20', '')) > 0:
            text.append(f" |👇{trade['sell_signal_ma20']}")
        text.append("]\n")

        text.append(f"BOLL指标 上轨 [{trade.get('upper_v', '')}")
        if len(trade.get('judge_boll_upper', '')) > 0:
            text.append(f" | {trade['judge_boll_upper']}位")
        text.append("]\n")

        text.append(f"中轨 [{trade.get('mid_v', '')}]\n")
        text.append(f"下轨 [{trade.get('lower_v', '')}")
        if len(trade.get('judge_boll_lower', '')) > 0:
            text.append(f" | {trade['judge_boll_lower']} 位")
        text.append("]\n")

        if len(trade.get('buy_signal_boll', '')) > 0:
            text.append(f"👆{trade['buy_signal_boll']}\n")
        if len(trade.get('sell_signal_boll', '')) > 0:
            text.append(f"👇{trade['sell_signal_boll']}\n")

        text.append(f"成交量 {trade.get('volume', '')} 比昨日 {trade.get('volume_rate', '')}\n")
        if len(trade.get('buy_signal_volume', '')) > 0:
            text.append(f"👆{trade['buy_signal_volume']}\n")
        if len(trade.get('sell_signal_volume', '')) > 0:
            text.append(f"👇{trade['sell_signal_volume']}\n")

        text.append(f"换手率 {trade.get('turnover_rate', '')} 比昨日 {trade.get('turnover_rate_rate', '')}\n")

    return "\n".join(text)