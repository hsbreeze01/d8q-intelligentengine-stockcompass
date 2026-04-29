import os
import sys
curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
path = os.path.split(rootPath)[0]
# print(curPath,rootPath,path)
sys.path.append(path) # 这句是为了导入_config
sys.path.append(rootPath)

import time
from datetime import datetime
from buy.DBClient import DBClient
import logging
from buy.cache import *
import json
from datetime import date

logger = logging.getLogger("my_logger")

class RecommendedCache:
    def __init__(self, cache_duration=3600):
        self.cache_duration = cache_duration
        self.stock_cache = {}  # Dictionary to store data for each date
        self.last_updated = 0

    def _fetch_daily_details(self, date):
        """查询当日的推荐股票明细"""
        try:
            mc = DBClient()
            sql = f"select a.stock_code, b.stock_name, b.industry, a.buy, a.record_time,c.open,c.close,c.high,c.low ,c.volume ,c.turnover ,c.amplitude ,c.change_percentage ,c.change_amount ,c.turnover_rate from stock_analysis a, dic_stock b,stock_data_daily c  where a.buy > 0 and a.stock_code = b.code and a.stock_code  = c.stock_code  and a.record_time = '{date}' and a.record_time  = c.`date`  order by b.industry,b.stock_name"
            count, recommended_stocks = mc.select_many(sql)
            mc.commit()
            
            # 拼接股票概念数据
            for stock in recommended_stocks:
                stock_code = stock['stock_code']
                try:
                    concepts = dicStock.data[dicStock.data['code'] == stock_code]['concepts'].values[0]
                    stock['concepts'] = concepts
                except Exception as ex:
                    logger.error(f"Error processing stock_code: {stock_code}, Exception: {ex}")
            
            return recommended_stocks
        except Exception as ex:
            logger.error(f"Error fetching daily details: {ex}")
            raise
        finally:
            mc.close()

    # def _fetch_industry_concept_stats(self, date):
    #     """查询行业和概念的统计数据"""
    #     industry_count = []
    #     concept_count = []
        
    #     try:
    #         mc = DBClient()
            
    #         # 查询行业统计数据
    #         sql = f"select category_name, count(*) as total from stock_analysis_stat where date = '{date}' and type = 0 group by category_name order by total desc"
    #         count, industry_count = mc.select_many(sql)
            
    #         # 查询概念统计数据
    #         sql = f"select category_name, count(*) as total from stock_analysis_stat where date = '{date}' and type = 1 group by category_name order by total desc"
    #         count, concept_count = mc.select_many(sql)
            
    #         mc.commit()
    #     except Exception as ex:
    #         logger.error(f"Error fetching industry/concept stats: {ex}")
    #         raise
    #     finally:
    #         mc.close()
            
    #     return industry_count, concept_count

    def _fetch_recent_dates(self, date, limit=5):
        """查询最近的几个日期"""
        try:
            mc = DBClient()
            sql = "SELECT DISTINCT date FROM stock_analysis_stat WHERE date <= %s ORDER BY date DESC LIMIT %s"
            count, dates = mc.select_many(sql, (date, limit))
            mc.commit()
            return [d['date'].strftime('%Y-%m-%d') for d in dates]
        except Exception as ex:
            logger.error(f"Error fetching recent dates: {ex}")
            raise
        finally:
            mc.close()

    def _fetch_date_stats(self, dates):
        """查询多个日期的统计数据"""
        date_stats = []
        
        try:
            mc = DBClient()
            
            for d in dates:
                # 查询推荐股票数量
                sql = "SELECT COUNT(distinct stock_code) as total FROM stock_analysis_stat WHERE date = %s"
                count, recommended_count = mc.select_many(sql, (d,))
                
                # 查询行业股票数量
                sql = "SELECT category_name, COUNT(*) as total FROM stock_analysis_stat WHERE date = %s AND type = 0 group by category_name order by total desc"
                count, industry_stock_count = mc.select_many(sql, (d,))
                
                # 查询概念股票数量
                sql = "SELECT category_name, COUNT(*) as total FROM stock_analysis_stat WHERE date = %s AND type = 1 group by category_name order by total desc"
                count, concept_stock_count = mc.select_many(sql, (d,))
                
                date_stats.append({
                    'date': d,
                    'recommended_count': recommended_count[0]['total'] if recommended_count else 0,
                    'industry_stock_count': industry_stock_count,
                    'concept_stock_count': concept_stock_count
                })
            
            mc.commit()
        except Exception as ex:
            logger.error(f"Error fetching date stats: {ex}")
            raise
        finally:
            mc.close()
            
        return date_stats

    def _fetch_recommended_stocks(self, date):
        """获取推荐股票的完整数据"""
        try:
            # 1. 查询当日的明细
            daily_details = self._fetch_daily_details(date)
            
            # 2. 查询近5日行业统计数据和概念统计数据
            # industry_count, concept_count = self._fetch_industry_concept_stats(date)
            
            # 3. 查询近5日的推荐股票数量
            recent_dates = self._fetch_recent_dates(date)
            date_stats = self._fetch_date_stats(recent_dates)
            
            # 4. 合并上述数据作为data，按照日期为key存储在stock_cache中
            data = {
                'recommended_stocks': daily_details,
                # 'industry_count': industry_count,
                # 'concept_count': concept_count,
                'date_stats': date_stats,
                'date': date
            }
            
            return data
        except Exception as ex:
            logger.error(f"Error fetching recommended stocks: {ex}")
            raise

    def get_recommended_stocks(self, date_str):
        """获取推荐股票数据"""
        if date_str in self.stock_cache:
            return self.stock_cache[date_str]
        else:
            #所有数据必须自动生成，不再依赖用户点击触发加载动作
            logger.debug(f"cache miss on date: {date_str}")
            return

        
        # logger.info(f"Cache miss for date: {date_str}")
        # data = self._fetch_recommended_stocks(date_str)
        # # 将date_str转换为date对象（如果是字符串则解析，若是datetime对象则提取date部分）
        # if isinstance(date_str, str):
        #     date_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        # elif isinstance(date_str, datetime):
        #     date_date = date_str.date()
        # else:
        #     raise TypeError("date_str must be a string (format 'YYYY-MM-DD') or a datetime.datetime object")

        # if date_date < date.today():
        #     self.stock_cache[date_str] = data
        #     self.last_updated = time.time()
        #     logger.info(f"Cache updated for date: {date_str}")

        # return data


    def reload(self):
        """初始化 最近10天的数据，只要不重启之前的数据会一直缓存"""
        today = date.today().strftime('%Y-%m-%d')
        dates= self._fetch_recent_dates(today,10)

        #不论当天是否加载过，都清理掉当天的数据重新生成
        if today in self.stock_cache:
            del self.stock_cache[today]

        for d in dates:
            # 跳过今天的数据，因为今天的数据可能还没有生成，需要重新加载
            # if d != today and d in self.stock_cache:
            if d in self.stock_cache:
                continue
            
            logger.info(f"Load cache for date: {d}")
            try:
                data = self._fetch_recommended_stocks(d)
                self.stock_cache[d] = data
            except Exception as ex:
                logger.error(f"Error fetching recommended stocks for date {d}: {ex}")
                continue
        
        self.last_updated = time.time()
        logger.info("Cache initialized")


recommend_cache = RecommendedCache()

if __name__ == '__main__':
    c = RecommendedCache()
    start_time = time.time()
    c.reload()
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Total execution time: {execution_time:.2f} seconds")

    start_time = time.time()

    result = c.get_recommended_stocks('2025-06-04')
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Total2 execution time: {execution_time:.2f} seconds")

    # Convert result to JSON format with pretty printing
    # json_result = json.dumps(result, indent=4, ensure_ascii=False)
    print(result)
    
