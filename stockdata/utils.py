#!/usr/bin/python
# -*- coding: UTF-8 -*-

import datetime
from datetime import timedelta

def get_adjacent_trading_days(date_str):
    """
    根据输入日期返回前一个和后一个中国股票交易日
    :param date_str: 日期字符串，格式为'yyyy-mm-dd'
    :return: (previous_trading_day, next_trading_day)
    """
    
    try:
        mc = DBClient()
        # 查询指定日期及其前后一天的交易数据
        sql = f"""
            SELECT DISTINCT date 
            FROM stock_data_daily 
            WHERE date BETWEEN 
                DATE_SUB('{date_str}', INTERVAL 1 DAY) AND 
                DATE_ADD('{date_str}', INTERVAL 1 DAY)
            ORDER BY date
        """
        count, trading_days = mc.select_many(sql)
        mc.commit()
        
        # 提取查询结果中的日期
        dates = [day[0] for day in trading_days]
        
        # 确保返回三个日期（前一天、当天、后一天）
        if len(dates) < 3:
            # 如果不足三个日期，使用默认方法计算前后交易日
            input_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # 查找前一个交易日
            previous_day = input_date - timedelta(days=1)
            while previous_day.weekday() >= 5 or is_holiday(previous_day):
                previous_day -= timedelta(days=1)
            
            # 查找后一个交易日
            next_day = input_date + timedelta(days=1)
            while next_day.weekday() >= 5 or is_holiday(next_day):
                next_day += timedelta(days=1)
            
            return previous_day.strftime('%Y-%m-%d'), date_str, next_day.strftime('%Y-%m-%d')
        
        return dates[0], date_str, dates[-1]
        
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        raise ex
    finally:
        mc.close()



