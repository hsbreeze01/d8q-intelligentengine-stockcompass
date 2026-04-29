#!/usr/bin/python
# -*- encoding: utf-8 -*-

"""
Description: 每日检测股票交易信息
Version: 1.0
Autor: Sam Zhu
Date: 2020-12-19 23:07:10
LastEditTime: 2020-12-27 21:20:53
"""
import concurrent.futures
import os
import sys
curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
path = os.path.split(rootPath)[0]
# print(curPath,rootPath,path)
sys.path.append(path) # 这句是为了导入_config
sys.path.append(rootPath)

import logging
# from buy.task import Task

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

from calc_indicator import calcIndicatorAndSaveToDB
from main_analysis import summery_trade_json
# from main_analysis import buy_advice
from main_analysis import buy_advice_v2
from stock_task import StockTask
import time
from bs4 import BeautifulSoup
import traceback
from RecommendedStockCache import recommend_cache as cache

class DailyStockCheckTaskV2():
    logger = logging.getLogger("my_logger")

    def __init__(self, name="DailyStockCheckTaskV2"):
        self.running = False
        # 继承父类的构造方法，也可以写成：super(Chinese,self).__init__(name,age)
        pass
    
  
    #启动股票任务
    def action(self):
        #防止重入
        if self.running == True:
            self.logger.debug("任务未完成，不重复执行")
            return
        
        self.running = True
        
        self.logger.info('===========action start========== ')
        #更新基础数据
        #如果捕获了异常则重试10次
        max_retries = 10
        for attempt in range(max_retries):
            try:
                self.logger.info('update stock list')
                self.updateStock()
                self.logger.info('update stock list end')
                break
            except Exception as e:
                self.logger.error(f"An error occurred while updateStock {e}\n"
                     f"Traceback: {traceback.format_exc()}")
                
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying... ({attempt + 1}/{max_retries})")
                else:
                    self.logger.error("Max retries reached. Exiting.")
            time.sleep(30)

        #更新股票数据和分析数据
        try:
            self.logger.info('update stock v2')
            self.updateStockV2()
            self.logger.info('update stock v2 end')
        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
        
        #股票数据更新后，dic的单只股票的最后更新时间也有变化
        dicStock.setNeedReload()

        #更新用户已购买的数据的止损价格
        try:
            self.logger.info('update user buy')
            self.updateUserStockTracking()
            self.logger.info('update user buy end')
        except Exception as e:
            self.logger.error(f"An error occurred: {e}")

        
        #更新缓存数据
        try:
            self.logger.info('update cache')
            cache.reload()
            self.logger.info('update cache end')
        except Exception as e:
            self.logger.error(f"An error occurred: {e}")

         #更新dic数据
        try:
            self.logger.info('update dic')
            dicStock.setNeedReload()
            dicStock.reload()
            self.logger.info('update dic end')
        except Exception as e:
            self.logger.error(f"An error occurred: {e}")

        self.logger.info('===========action over========== ')
        self.running = False
        pass

    #股票基础数据更新
    def updateStock(self):
        #更新股票信息
        self.updateAllStockData()
        #更新股票的行业信息
        self.updateAllStockIndustry()
        #更新概念信息
        self.updateAllStockConcept()
        #更新最近2天的股票事件，因为有可能当天的事件还没有更新全，所以每次更新要把前一天的重新更新
        date = datetime.datetime.now().strftime('%Y%m%d')
        self.updateAllStockEvents(date)
        date = (datetime.datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        self.updateAllStockEvents(date)
        pass
    
    #股票指标数据更新
    def updateStockIndicator(self):
        dicStock.reload()

        mc = DBClient()

        pd = dicStock.data
        count = 0
        for index in pd.index:
            count += 1
            # 根据股票id补全每日股票数据
            stockcode = pd.loc[index]["code"]
            max_record_time = mc.select_one('select max(date) from stock_data_daily where stock_code=%s', (stockcode,))
            #默认从最大的时间-1天，因为更新的时候有可能是当天的盘中时间
            endDate = (max_record_time[1]['max(date)']).strftime('%Y%m%d')
            print('update indicator:',stockcode,endDate)
            calcIndicatorAndSaveToDB(stockcode,endDate)
            pass

        print('stocks indicator check finish:',len(pd),' count:',count)
        mc.close()
    
    #根据股票的指标，进行内容分析
    def tradeAnalysis(self):
        dicStock.reload()

        mc = DBClient()

        pd = dicStock.data
        count = 0
        for index in pd.index:
            count += 1
            # 根据股票id补全每日股票数据
            stockcode = pd.loc[index]["code"]
            
            #查找最大的分析时间
            count,max_record_time = mc.select_one('select max(record_time) from stock_analysis where stock_code=%s', (stockcode,))
            start = '20240801' #从8月份开始，之前的数据需要构建指标，数据不足时指标不准确
            print('count:',count)
            if max_record_time['max(record_time)'] is not None:
                #默认从最大的时间-1天，因为更新的时候有可能是当天的盘中时间
                start = (max_record_time['max(record_time)'] - timedelta(days=1)).strftime('%Y%m%d')
                pass
            
            print('tradeAnalysis() start:',start)
            sql = f"SELECT * FROM stock_data_daily WHERE stock_code='{stockcode}' AND date > '{start}'"
            # sql3 = 'replace into param (id,name) values(%s,%s)'
            # param = (index,'12'+str(index))
            count,result = mc.select_many(sql)

            for row in result:
                print(row)
                data = summery_trade_json(stockcode,row['date'].strftime('%Y%m%d'))
                # print(data)
                buy,sell,advice = buy_advice_v2(data)

                #更新所有数据
# id           |bigint(20)|NO  |PRI|       |auto_increment|
# stock_code   |char(10)  |NO  |MUL|       |              |
# analysis_data|json      |NO  |   |       |              |
# buy_advice   |json      |NO  |   |       |              |
# record_time  |date      |NO  |   |       |              |
# buy          |int(11)   |NO  |   |       |              |
# sell         |int(11)   |NO  |   |       |              |
                
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
                mc.execute(sql_insert, (stockcode, json.dumps(data), json.dumps(advice), row['date'], buy, sell))
                mc.commit()
            pass

        print('stocks indicator check finish:',len(pd),' count:',count)
        mc.close()

    def check(self):
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"======= check Current time: {current_time}")

    def updateStockDaily(self):
        """[summary]
        执行基础数据补全的任务，每天执行一次或启动时执行
        如果抓取数据期间被安全策略封禁，则过5分钟再尝试一次
        Returns:
            [type]: [description]
        """
        
        # 当日执行过
        # if dayDif(datetime.date.today(), self.lastTime) <= 0:
        #     self.logger.info(f"exec failed! last action time: {self.lastTime} now: {datetime.date.today()}")
        #     print(f"exec failed! last action time: {self.lastTime} now: {datetime.date.today()}")
        #     return
        
        print("---------start----------")
        # 每次更新重新读库保证数据一致
        dicStock.reload()
        
        try:
            mc = DBClient()
            

            pd = dicStock.data
            
            count = 0
            for index in pd.index:
                count += 1
                
                # 不做当日校验，每次执行时都执行一次（只要是连贯的多刷新数据至少数据准确）
                # #比较数据是否今天更新过 
                #如果今天更新过，且更新时间是16:00 以后，则跳过，否则更新
                if dayDif(datetime.datetime.now(), pd.at[index,"stock_data_daily_update_time"]) <= 0 and pd.at[index,"stock_data_daily_update_time"].hour > 16:
                    self.logger.debug(pd.at[index,"code"]+" update in "+ str(pd.at[index,"stock_data_daily_update_time"]))
                    print((pd.at[index,"code"]+" update in "+ str(pd.at[index,"stock_data_daily_update_time"]),' skip'))
                    continue
                
                # 根据股票id补全每日股票数据
                stockcode = pd.loc[index]["code"]

                max_record_time = mc.select_one('select max(date) from stock_data_daily where stock_code=%s', (stockcode,))
                start = '20240101'
                if max_record_time[1]['max(date)'] is not None:
                    #默认从最大的时间-1天，因为更新的时候有可能是当天的盘中时间
                    start = (max_record_time[1]['max(date)'] - timedelta(days=1)).strftime('%Y%m%d')
                    self.logger.debug(pd.at[index, "code"] + " max record time: " + start)
                   
                end = datetime.datetime.now().strftime('%Y%m%d')

                print(stockcode,' update ( ',start,end,')')
                #已经是最新的了，不需要再更新
                if start == end:
                    continue

                stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol=stockcode, period="daily", start_date=start, end_date=end, adjust="qfq")
                print("-------------------")
                print(stock_zh_a_hist_df)
                print("-------------------")

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
                    mc.execute(sql)
                    pass
               
                # 更新最新数据，同时更新股票的最后刷新时间
                sql = "update dic_stock set stock_data_daily_update_time= '"+ datetime.datetime.strftime(datetime.datetime.now(),'%Y-%m-%d %H:%M:%S') +"' where code='"+stockcode+"';"
                mc.execute(sql)

                mc.commit()
                
                #追加执行n次之后停30秒
                print(index +1)
                # if (index+1) % 100 == 0:
                #     time.sleep(5)
                pass
        except Exception as ex:
            print(ex)
            mc.rollback()
            return False
        finally:
            mc.close()
            pass
        
        print('stocks:',len(pd),' count:',count)

        return True

    def updateStockJob(self,code,last_update_time):
        self.logger.debug('code:'+code+' last_update_time:'+str(last_update_time))

        max_retries = 5
        retry_delay = 3
        
        for attempt in range(max_retries):
            try:
                st = StockTask(code, last_update_time)
                st.action()
                break
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1}/{max_retries} failed while updating stock {code}: {e}")
                
                if attempt < max_retries - 1:
                    sleep_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.debug(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    self.logger.error(f"Max retries ({max_retries}) reached. Failed to update stock {code}")

        self.logger.debug('code:'+code+' last_update_time:'+str(last_update_time)+' done')
        pass

    #按照股票更新数据
    def updateStockV2(self):
        # 每次更新重新读库保证数据一致
        dicStock.reload()
        pd = dicStock.data

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            # 提交 更新异步任务 个任务
            future_to_task = {executor.submit(self.updateStockJob, pd.loc[index]["code"],pd.at[index,"stock_data_daily_update_time"]): index for index in pd.index}
            # 等待所有任务完成
            concurrent.futures.wait(future_to_task)

        return True
    

    #股票的全局数据
    def updateAllStockData(self):
        stock_zh_a_spot_em_df = ak.stock_zh_a_spot_em() #全国的接口zh，除了能用这个获取实时数据，还可以根据这个数据获取股票的代码
        mc = DBClient()
        try:
            # print(stock_zh_a_spot_em_df)
            for index, row in stock_zh_a_spot_em_df.iterrows():
                row = row.fillna(0)
                sql = f"""
                INSERT INTO dic_stock (
                    code,
                    stock_name,
                    stock_prefix,
                    latest_price,
                    change_percentage,
                    change_amount,
                    volume,
                    turnover,
                    amplitude,
                    highest,
                    lowest,
                    open_today,
                    close_yesterday,
                    volume_ratio,
                    turnover_rate,
                    pe_ratio_dynamic,
                    pb_ratio,
                    total_market_value,
                    circulating_market_value,
                    speed_of_increase,
                    change_5min,
                    change_60days,
                    change_ytd,
                    last_update_time
                ) VALUES (
                    '{row['代码']}',
                    '{row['名称']}',
                    '{row['代码'][:3]}',
                    {row['最新价']},
                    {row['涨跌幅']},
                    {row['涨跌额']},
                    {row['成交量']},
                    {row['成交额']},
                    {row['振幅']},
                    {row['最高']},
                    {row['最低']},
                    {row['今开']},
                    {row['昨收']},
                    {row['量比']},
                    {row['换手率']},
                    {row['市盈率-动态']},
                    {row['市净率']},
                    {row['总市值']},
                    {row['流通市值']},
                    {row['涨速']},
                    {row['5分钟涨跌']},
                    {row['60日涨跌幅']},
                    {row['年初至今涨跌幅']},
                    '{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}'
                ) ON DUPLICATE KEY UPDATE
                    stock_name=VALUES(stock_name),
                    stock_prefix=VALUES(stock_prefix),
                    latest_price=VALUES(latest_price),
                    change_percentage=VALUES(change_percentage),
                    change_amount=VALUES(change_amount),
                    volume=VALUES(volume),
                    turnover=VALUES(turnover),
                    amplitude=VALUES(amplitude),
                    highest=VALUES(highest),
                    lowest=VALUES(lowest),
                    open_today=VALUES(open_today),
                    close_yesterday=VALUES(close_yesterday),
                    volume_ratio=VALUES(volume_ratio),
                    turnover_rate=VALUES(turnover_rate),
                    pe_ratio_dynamic=VALUES(pe_ratio_dynamic),
                    pb_ratio=VALUES(pb_ratio),
                    total_market_value=VALUES(total_market_value),
                    circulating_market_value=VALUES(circulating_market_value),
                    speed_of_increase=VALUES(speed_of_increase),
                    change_5min=VALUES(change_5min),
                    change_60days=VALUES(change_60days),
                    change_ytd=VALUES(change_ytd),
                    last_update_time=VALUES(last_update_time);
                """


                # print(sql)
                # break
                # if row['代码'] == '600036':
                #     print(row)
                mc.execute(sql)
            pass  
            mc.commit()
        except Exception as ex:
            self.logger.error(ex)
            mc.rollback()
            return False
        finally:
            mc.close()
            pass
        
        #更新股票基础列表之后，缓存需要重新刷新
        dicStock.setNeedReload()

        self.logger.info("updateAllStockData success, length: %d", len(stock_zh_a_spot_em_df))
        return True

    #更新所有股票的行业信息(第一次进入股票池的行业信息是没有的)
    def updateAllStockIndustry(self):
        dicStock.reload()
        pd = dicStock.data
        self.logger.debug("updateAllStockIndustry start")

        for index in pd.index:
            industry = pd.loc[index]["industry"]
            if industry != 'none':
                continue

            self.logger.debug(f"Updating industry for stock {pd.loc[index]['code']}")

            stock_code = pd.loc[index]["code"]
            #如果抓取数据期间被安全策略封禁，则过10秒再尝试一次
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    # 查询股票所属行业
                    stock_info = ak.stock_individual_info_em(symbol=stock_code)
                    # 获取行业字段对应的value
                    industry = stock_info.loc[stock_info['item'] == '行业', 'value'].values[0] if not stock_info.empty else 'none'
                    break
                except Exception as ex:
                    self.logger.error(f"An error occurred while updating industry stock {stock_code}: {ex}\n"
                     f"Traceback: {traceback.format_exc()}")
                    if attempt < max_retries - 1:
                        self.logger.info(f"Retrying... ({attempt + 1}/{max_retries})")
                        time.sleep(10)
                    else:
                        self.logger.error("Max retries reached. Exiting.")
            
            if not industry:
                continue

            try:
                mc_single = DBClient()
                # 更新股票行业信息
                sql = f"UPDATE dic_stock SET industry = '{industry}' WHERE code = '{stock_code}'"
                mc_single.execute(sql)
                mc_single.commit()
            except Exception as ex:
                self.logger.error(f"An error occurred: {ex}")
                mc_single.rollback()
            finally:
                mc_single.close()

        
        return True
    
    #更新股票概念
    def updateStockConcept(self,stock_code,stock_name,full_stock_code):
        url = f'https://finance.sina.com.cn/realstock/company/{full_stock_code}/nc.shtml'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'accept-language':'zh-CN,zh;q=0.9,en;q=0.8'
        }

        #如果接口不可用考虑用这个代替 ak.stock_board_concept_name_em

        response = requests.get(url, headers=headers)
        # response.encoding = response.apparent_encoding  # 自动检测编码
        response.encoding = 'GB2312'

        soup = BeautifulSoup(response.text, 'lxml')
        
        # 获取股票名称
        stock_name2 = ""
        try:
            stock_name_tag = soup.find('h1', id='stockName').find('i', class_='c8_name')
            if stock_name_tag:
                stock_name2 = stock_name_tag.text.strip()
        except Exception as e:
            self.logger.debug(f"解析股票名称时出错: {e}")

        # if stock_name2 != stock_name:
        #     self.logger.error(f"Stock name mismatch: {stock_name} != {stock_name2}")
        #     return False
        
        # 获取所属板块信息
        self.logger.debug(f"Updating concepts for stock {stock_code}")
        print(f"Updating concepts for stock {stock_code}")
        concepts = []
        try:
            # 找到包含所属板块的 <p> 标签
            overview_div = soup.find('div', class_='com_overview blue_d')
            if overview_div:
                # 找到所有 <p> 标签
                p_tags = overview_div.find_all('p')
                for p in p_tags:
                    # 找到包含 "所属板块：" 的 <p> 标签
                    if '所属板块：' in p.text:
                        # 提取所有 <a> 标签中的文本
                        concept_tags = p.find_all('a')
                        for tag in concept_tags:
                            concepts.append(tag.text.strip())
                        break  # 找到后退出循环
        except Exception as e:
            self.logger.debug(f"解析网页时出错: {e}")
        
        try:
            mc = DBClient()

            for concept in concepts:
                sql = f"""
                INSERT INTO stock_concept (
                    stock_code,
                    full_stock_code,
                    concept_name
                ) VALUES (
                    '{stock_code}',
                    '{full_stock_code}',
                    '{concept}'
                ) ON DUPLICATE KEY UPDATE
                    concept_name=VALUES(concept_name);
                """
                mc.execute(sql)
            
            mc.commit()
        except Exception as ex:
            self.logger.error(f"An error occurred while inserting concepts for stock {stock_code}: {ex}")
            mc.rollback()
        finally:
            mc.close()


        return True
    
    
    #更新股票概念分类（首次加入股票池的没有概念信息）
    def updateAllStockConcept(self):
        dicStock.reload()
        pd = dicStock.data
        mc = DBClient()
        for index in pd.index:
            # 根据股票id补全每日股票数据
            stock_code = pd.loc[index]["code"]
            if len(pd.loc[index]["concepts"]) > 0:
                continue

            # 示例股票代码
            # stock_code = '301150'  # 浦发银行
            #43、83、87、88 是bj 6 开头是sh 其他是sz
            if stock_code.startswith('43') or stock_code.startswith('83') or stock_code.startswith('87') or stock_code.startswith('88') or stock_code.startswith('92'):
                full_stock_code = f'bj{stock_code}'
            elif stock_code.startswith('6'):
                full_stock_code = f'sh{stock_code}'
            else:
                full_stock_code = f'sz{stock_code}'


            self.updateStockConcept(stock_code,pd.loc[index]["stock_name"],full_stock_code)

    #更新股票事件
    def updateAllStockEvents(self,date):
        # 序号      代码    简称  事件类型                                               具体事项         交易日
        # 0    1  000526  学大教育  资产重组  紫光集团有限公司管理人(以下简称“管理人”)履行紫光集团等七家企业实质合并重整案重整计划相关...  2025-02-20
        # 1    2  000591   太阳能  资产重组  五常分布式项目预计总投资约为6,170.69万元,其中资本金不低于1,234.14万元(不超...  2025-02-20
        
        # date = datetime.datetime.now().strftime('%Y%m%d')
        
        try:
            #获取事件时如果当天没有数据会有异常
            events = ak.stock_gsrl_gsdt_em(date=date)
        except Exception as e:
            # self.logger.info(f"An error occurred while updateAllStockEvents {e}\n"
            #          f"Traceback: {traceback.format_exc()}")
            self.logger.warning("未获取到有效事件")   
            return

        mc = DBClient()
        date = datetime.datetime.now().strftime('%Y-%m-%d')

        try:
            # 删除当天的所有数据
            sql_delete = f"DELETE FROM stock_events WHERE date = '{date}'"
            mc.execute(sql_delete)

            for index, row in events.iterrows():
                sql = """
                INSERT INTO stock_events (
                    stock_code,
                    stock_name,
                    event_type,
                    event_detail,
                    date
                ) VALUES (%s, %s, %s, %s, %s)
                """
                param = (row['代码'], row['简称'], row['事件类型'], row['具体事项'], row['交易日'])
                mc.execute(sql,param=param)
                
            mc.commit()
        except Exception as ex:
            self.logger.error(f"An error occurred while updateAllStockEvents {row}: {ex}\n"
                     f"Traceback: {traceback.format_exc()}")
            mc.rollback()
        finally:
            mc.close()
        pass

    #更新用户的止损数据
    def updateUserStockTracking(self):
        #1.获取当天的日期
        #2.获取user_stock_tracking表中所有符合 last_update_time < date 的数据,只需要stock_code
        #3.遍历所有2获得的记录，调用updateStockTracking方法
        date = datetime.datetime.now().strftime('%Y-%m-%d')
        mc = DBClient()
        try:
            sql = "SELECT distinct stock_code FROM user_stock_tracking WHERE DATE(last_update_time) < %s"
            count, records = mc.select_many(sql, (date,))
            for record in records:
                self.updateStockTracking(record['stock_code'],date)
        except Exception as ex:
            self.logger.error(f"An error occurred while updateUserStockTracking {record}: {ex}\n"
                     f"Traceback: {traceback.format_exc()}")
            mc.rollback()
        finally:
            mc.close()

        pass

    def updateStockTracking(self,stock_code,date):
        #1.查看user_stock_tracking表中所有符合stock_code并且 last_update_time < date 的数据
        #2.查询stock_data_daily表中符合stock_code和date的数据，应该只有1条数据
        #3.根据2中的数据更新user_stock_tracking表中的数据，按照2中记录的收盘价格重新继续1记录里的止损价格并更新
        mc = DBClient()
        try:
            # 1. 查询需要更新的跟踪记录
            sql = "SELECT * FROM user_stock_tracking WHERE stock_code = %s AND DATE(last_update_time) < %s"
            count, records = mc.select_many(sql, (stock_code, date))
            
            if count == 0:
                self.logger.info(f"No records to update for stock_code: {stock_code} and date: {date}")
                return
            
            # 2. 获取最新的股票价格
            sql = "SELECT close FROM stock_data_daily WHERE stock_code = %s AND date = %s"
            count, daily_data = mc.select_one(sql, (stock_code, date))
            
            if count == 0:
                self.logger.info(f"No daily data found for stock_code: {stock_code} and date: {date}")
                return
                
            current_price = daily_data['close']
            
            # 3. 更新跟踪记录
            for record in records:
                # 计算新的止损价格
                # Only update stop loss price if current price is higher than previous
                if float(current_price) > float(record['current_price']):
                    stop_loss_price = float(current_price) * (1 - float(record['stop_loss_pct']) / 100)
                    # Update record with new current price and stop loss price
                    sql = "UPDATE user_stock_tracking SET current_price = %s, stop_loss_price = %s WHERE id = %s"
                    mc.execute(sql, (current_price, stop_loss_price, record['id']))

            mc.commit()
        except Exception as e:
            mc.rollback()
            print(f"Error updating stock tracking for {stock_code}: {str(e)}")
        finally:
            mc.close()

    
if __name__ == '__main__':
    # os.environ['DevENV'] = 'prod'

    start_time = time.time()
    t = DailyStockCheckTaskV2()
    date = (datetime.datetime.now() - timedelta(days=2)).strftime('%Y%m%d')
    # t.updateAllStockEvents(date)
    # t.action()
    # t.updateStockV2()
    # t.updateAllStockConcept()
    t.updateUserStockTracking()

    # t.updateAllStockIndustry()
    # st = StockTask('688393', datetime.datetime.strptime('2024-12-16 09:57:46', '%Y-%m-%d %H:%M:%S'))
    # st = StockTask('600036', datetime.datetime.strptime('2024-12-16 09:57:46', '%Y-%m-%d %H:%M:%S'))
    # st.action()
    # st.updateFavoriteLLM()
    # st.updateIndicatorV2()
    

    # updateAllStockIndustry()

    # stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol="000001", period="daily", start_date="20170301", end_date='20231022', adjust="")
    # print(stock_zh_a_hist_df)

    end_time = time.time()
    elapsed_time = end_time - start_time

    print(f"Update completed in {elapsed_time:.2f} seconds")
    
    print('股票策略version1.0 start')
