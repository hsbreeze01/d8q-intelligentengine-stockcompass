import os
import sys

from buy.DBClient import DBClient
import json
from decimal import Decimal

#策略执行列表
def simulation_list(code,uid):

    try:
        mc = DBClient()
        # 更新最新数据，同时更新股票的最后刷新时间
        sql = f"select * from user_trade_simulation where stock_code ='{code}' and user_id={uid}"
        count, result = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        print(ex)
        mc.rollback()
        return False
    finally:
        mc.close()
    
    return result


#将策略生成购买决策
def simulation_gen(code,uid):

    try:
        mc = DBClient()
        #清空表
        mc.execute("delete from user_trade_simulation where user_id =%s and stock_code = %s", (uid,code))
        mc.commit()
    except Exception as ex:
        print(ex)
        mc.rollback()
        return False
    finally:
        mc.close()
    
    print("clear user_trade_simulation")

    try:
        mc = DBClient()
        #读取买入策略
        
        sql = f"""
                select a.stock_code, a.record_time, a.buy, a.sell,b.`open` ,b.`close` ,b.low ,b.high,c.ma5 ,c.ma10,c.ma20 
                from stock_analysis a,stock_data_daily b,indicators_daily c
                where a.stock_code ='{code}' 
                and a.stock_code  = b.stock_code  and a.stock_code = c.stock_code 
                and a.record_time  = b.`date`  and a.record_time = c.`date`  order by a.record_time
        """
        count, result = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        print(ex)
        mc.rollback()
        return False
    finally:
        mc.close()

    #根据result的数据，生成购买记录
    #buy_type 'down_up_10'连续10个交易日都是不推荐买入 1，然后今天变0
    buy_records = []
    sell_count = 0

    for row in result:
        stock_code = row['stock_code']
        record_time = row['record_time']
        buy = row['buy']
        sell = row['sell']
        #记录累计连续的建议卖出次数
        if sell > 0:
            sell_count += 1

        #不管任何策略，次日开盘如果低于今日的开盘价格、5日线 则不买
        decide_price = max(row['open'], row['ma5'])


        #根据买入建议生成买入记录 (当日只有买入建议无卖出建议)
        if buy > 0 and sell == 0:
            buy_records.append({'user_id':uid, 'stock_code':stock_code, 'decide_date':record_time, 'decide_price':decide_price, 'decide_type':buy})

        #触发过购买事件的则不再触发该规则
        #超过10天连续卖出，变0的次日如果还是涨的话且站上ma5，买入
        if buy == 0 and sell_count >= 10 and sell == 0 and row['close'] > row['open'] and row['close'] > row['ma5']:
            buy_records.append({'user_id':uid, 'stock_code':stock_code, 'decide_date':record_time, 'decide_price':decide_price, 'decide_type':'sell_'+str(sell_count)})

        #打算sell的连续性
        if sell == 0:
            sell_count = 0
        # print(len(buy_records))
    pass

    # Insert buy records into user_trade_simulation table
    #id
# user_id
# stock_code
# decide_date
# decide_price
# decide_type
# execute_status
# buy_price
# check_date
# check_price
# sell_boll_date
# sell_boll_price
# sell_ma5_date
# sell_ma5_price
# sell_ma10_date
# sell_ma10_price
# sell_ma20_date
# sell_ma20_price
# stop_date
# stop_price
#execute_status tinyint NOT NULL COMMENT '执行状态 0 未执行 1 买入成功 2 买入失败',
    try:
        mc = DBClient()
    
        for record in buy_records:
            # sql = "insert into user_trade_simulation (user_id, stock_code, decide_date, decide_price, decide_type, execute_status, buy_date,buy_price, check_date, check_price, sell_boll_date, sell_boll_price, sell_ma5_date, sell_ma5_price, sell_ma10_date, sell_ma10_price, sell_ma20_date, sell_ma20_price, stop_date, stop_price) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            # sql = sql % (
            #     record['user_id'], record['stock_code'], record['decide_date'], record['decide_price'], record['decide_type'], 0, record['decide_date'], 0, record['decide_date'], 0, record['decide_date'], 0, record['decide_date'], 0, record['decide_date'], 0, record['decide_date'], 0, record['decide_date'], 0
            # )
            mc.execute(
                "insert into user_trade_simulation (user_id, stock_code, decide_date, decide_price, decide_type, execute_status, buy_date,buy_price, check_date, check_price, sell_boll_date, sell_boll_price, sell_ma5_date, sell_ma5_price, sell_ma10_date, sell_ma10_price, sell_ma20_date, sell_ma20_price, stop_date, stop_price) values (%s, %s,%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (record['user_id'], record['stock_code'], record['decide_date'], record['decide_price'], record['decide_type'], 0, '2000-01-01',0, '2000-01-01', 0, '2000-01-01', 0, '2000-01-01', 0, '2000-01-01', 0, '2000-01-01', 0,'2000-01-01',0)
            )
        mc.commit()
    except Exception as ex:
        print(ex)
        mc.rollback()
        return False
    finally:
        mc.close()
    # print(result)
    
    return code

def simulation_buy(code,uid):

    try:
        mc = DBClient()
        #选出所有还未执行购买策略的记录
        sql = f"select * from user_trade_simulation where stock_code ='{code}' and user_id={uid} and execute_status = 0"
        count, result = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        print(ex)
        mc.rollback()
        return False
    finally:
        mc.close()

    try:
        mc = DBClient()
        for row in result:
            sql = f"select * from stock_data_daily where stock_code = '{code}' and date > '{row['decide_date']}' order by date limit 0,1"
            count, daily = mc.select_one(sql)
            if count == 0:
                print(f"No daily data found for stock code {code} and date {row['decide_date']}")
                continue
           
            if daily['open'] >= row['decide_price']: #买入成功
                # Update the record with execute_status, buy_date, and buy_price
                update_sql = """
                    update user_trade_simulation 
                    set execute_status = 1, buy_date = %s, buy_price = %s 
                    where user_id = %s and stock_code = %s and decide_date = %s
                """
            elif daily['open'] >= row['decide_price']*Decimal('0.99'): #低于目标价1%买入，超过坚决不买，否则买入即亏损
                #如果买入失败，也生成对应的日期和开盘价
                update_sql = """
                    update user_trade_simulation 
                    set execute_status = 2, buy_date = %s, buy_price = %s 
                    where user_id = %s and stock_code = %s and decide_date = %s
                """
            mc.execute(update_sql, (daily['date'], daily['open'], uid, code, row['decide_date']))
        pass

        mc.commit()
    except Exception as ex:
        print(ex)
        mc.rollback()
        return False
    finally:
        mc.close()

    return code

def simulation_sell(code,uid):

    try:
        mc = DBClient()
        # 更新最新数据，同时更新股票的最后刷新时间
        sql = f"select * from user_trade_simulation where stock_code ='{code}' and user_id={uid}"
        count, result = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        print(ex)
        mc.rollback()
        return False
    finally:
        mc.close()

    
    try:
        mc = DBClient()
        #判定卖出策略
        for row in result:
            #读取每日的交易数据
            sql = f"""
                    select a.`date`, a.`open` ,a.`close` ,a.low ,a.high,b.ma5 ,b.ma10,b.ma20 
                    from stock_data_daily a,indicators_daily b
                    where a.stock_code ='{code}' and a.`date` >= '{row['buy_date']}'
                    and a.stock_code = b.stock_code 
                    and a.`date`  = b.`date` order by a.`date` 
            """
            count, daily_records = mc.select_many(sql)

            #1.止损%5 如果买入后的第n天最高和最低在买入价格低于%5则卖出
            # -- 需要修正策略，买入后看价格，如果价格比买入价高了，那么止损价应该用买入后的最高价格的5%，最终看按照这个卖出，能盈利多少。或者按照破20日线卖出
            #2.止盈破判定日前一天的5日线
            #3.止盈破判定日前一天的10日线
            #4.止盈破判定日前一天的20日线
            #5.止盈破判定日前一天的boll上轨
            last_ma5 = 0
            last_ma10 = 0
            last_low = 0
            last_high = 0
            #记录卖出是否执行过
            stop_flag = False
            ma5_flag = False
            ma10_flag = False
            first_deal = False
            #记录策略执行多少天了
            count_days = 0
            #止损价格
            stop_price = row['buy_price'] * Decimal('0.95')
            for daily in daily_records:

                #买入日的当天只记录数据，不做判断
                if daily['date'] > row['buy_date']:
                    
                    count_days += 1
                    sell_date = daily['date']
                    # Strategy 1: Stop loss 5%
                    stop_price = max(stop_price, daily['open'] * Decimal('0.95'))#如果开盘当天的止损价格高于之前的止损价格，则更新止损价格
                    if stop_flag == False and daily['low'] <= stop_price:
                        stop_flag = True

                        #如果止损价格在当天的最高和最低之间，则成交价为止损价，否则按照开盘价格成交
                        if daily['high'] >= stop_price:
                            deal_price = stop_price
                        else:
                            deal_price = daily['open']

                        update_sql = """
                            update user_trade_simulation 
                            set stop_date = %s, stop_price = %s 
                            where user_id = %s and stock_code = %s and decide_date = %s
                        """
                        mc.execute(update_sql, (sell_date, deal_price, uid, code, row['decide_date']))

                        if first_deal == False:
                            first_deal = True
                            update_sql = """
                                update user_trade_simulation 
                                set check_date = %s, check_price = %s 
                                where user_id = %s and stock_code = %s and decide_date = %s
                            """
                            mc.execute(update_sql, (sell_date, deal_price, uid, code, row['decide_date']))

                        pass

                    # Strategy 2: Break 5-day moving average
                    if ma5_flag == False and daily['low'] < last_ma5:
                        ma5_flag = True
                        
                        #如果止盈价格在当天的最高和最低之间，则成交价为止盈价，否则按照开盘价格成交
                        if daily['high'] >= last_ma5:
                            deal_price = last_ma5
                        else:
                            deal_price = daily['open']

                        update_sql = """
                            update user_trade_simulation 
                            set sell_ma5_date = %s, sell_ma5_price = %s 
                            where user_id = %s and stock_code = %s and decide_date = %s
                        """
                        mc.execute(update_sql, (sell_date, deal_price, uid, code, row['decide_date']))

                        if first_deal == False:
                            first_deal = True
                            update_sql = """
                                update user_trade_simulation 
                                set check_date = %s, check_price = %s 
                                where user_id = %s and stock_code = %s and decide_date = %s
                            """
                            mc.execute(update_sql, (sell_date, deal_price, uid, code, row['decide_date']))
                        pass

                    # Strategy 3: Break 10-day moving average
                    if ma10_flag == False and daily['low'] < last_ma10:
                        ma10_flag = True
                        #如果止盈价格在当天的最高和最低之间，则成交价为止盈价，否则按照开盘价格成交
                        if daily['high'] >= last_ma10:
                            deal_price = last_ma10
                        else:
                            deal_price = daily['open']

                        update_sql = """
                            update user_trade_simulation 
                            set sell_ma10_date = %s, sell_ma10_price = %s 
                            where user_id = %s and stock_code = %s and decide_date = %s
                        """
                        mc.execute(update_sql, (sell_date, deal_price, uid, code, row['decide_date']))

                        if first_deal == False:
                            first_deal = True
                            update_sql = """
                                update user_trade_simulation 
                                set check_date = %s, check_price = %s 
                                where user_id = %s and stock_code = %s and decide_date = %s
                            """
                            mc.execute(update_sql, (sell_date, deal_price, uid, code, row['decide_date']))
                        pass

                    #记录决策日近20天的最低价格和出现时间
                    if count_days<=20 and ( last_low == 0 or daily['low'] < last_low):
                        #记录最低价和时间
                        last_low = daily['low']

                        update_sql = """
                            update user_trade_simulation 
                            set sell_ma20_date = %s, sell_ma20_price = %s 
                            where user_id = %s and stock_code = %s and decide_date = %s
                        """
                        mc.execute(update_sql, (sell_date, last_low, uid, code, row['decide_date']))
                        pass

                    # 记录决策日近20天的最高价格和出现时间
                    if count_days<=20 and daily['high'] > last_high:
                        #记录最高价和时间
                        last_high = daily['high']

                        update_sql = """
                            update user_trade_simulation 
                            set sell_boll_date = %s, sell_boll_price = %s 
                            where user_id = %s and stock_code = %s and decide_date = %s
                        """
                        mc.execute(update_sql, (sell_date, last_high, uid, code, row['decide_date']))
                pass
                
                #5个卖出动作都完成后，退出循环
                if stop_flag and ma5_flag and ma10_flag and count_days >= 20:
                    break
                
                #记录前一天的数据
                last_ma5 = daily['ma5']
                last_ma10 = daily['ma10']
            pass
        pass

        mc.commit()
    except Exception as ex:
        print(ex)
        mc.rollback()
        return False
    finally:
        mc.close()

    return code


#检查交易完成的情况
def simulation_deal(code,uid,status = 0):
    try:
        mc = DBClient()
        # 更新最新数据，同时更新股票的最后刷新时间
        if '0' != status:
            sql = f"select * from user_trade_simulation where stock_code ='{code}' and user_id={uid} and execute_status = {status}"
        else:
            sql = f"select * from user_trade_simulation where stock_code ='{code}' and user_id={uid}"
        count, result = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        print(ex)
        mc.rollback()
        return False
    finally:
        mc.close()

    deals = []
    total_profit = {}
    total_profit['first'] = Decimal('0.0')
    total_profit['boll'] = Decimal('0.0')
    total_profit['ma5'] = Decimal('0.0')
    total_profit['ma10'] = Decimal('0.0')
    total_profit['ma20'] = Decimal('0.0')
    total_profit['stop'] = Decimal('0.0')

    for row in result:
        if row['execute_status'] == 0:  # Only consider successful buy records
            continue
        deal = {}
        deals.append(deal)
        deal['stock_code'] = row['stock_code']
        deal['decide_date'] = row['decide_date']
        deal['decide_price'] = row['decide_price']
        deal['decide_type'] = row['decide_type']
        deal['execute_status'] = row['execute_status']
        deal['buy_date'] = row['buy_date']
        deal['buy_price'] = row['buy_price']
        deal['check_date'] = row['check_date']
        deal['check_price'] = row['check_price']
        deal['sell_boll_date'] = row['sell_boll_date']
        deal['sell_boll_price'] = row['sell_boll_price']
        deal['sell_ma5_date'] = row['sell_ma5_date']
        deal['sell_ma5_price'] = row['sell_ma5_price']
        deal['sell_ma10_date'] = row['sell_ma10_date']
        deal['sell_ma10_price'] = row['sell_ma10_price']
        deal['sell_ma20_date'] = row['sell_ma20_date']
        deal['sell_ma20_price'] = row['sell_ma20_price']
        deal['stop_date'] = row['stop_date']
        deal['stop_price'] = row['stop_price']

        if row['check_price'] > 0:
            deal['profit_first'] = row['check_price'] - row['buy_price']
            total_profit['first'] += deal['profit_first']

        if row['sell_boll_price'] > 0:
            deal['profit_boll'] = row['sell_boll_price'] - row['buy_price']
            total_profit['boll'] += deal['profit_boll']

        if row['sell_ma5_price'] > 0:
            deal['profit_ma5'] = row['sell_ma5_price'] - row['buy_price']
            total_profit['ma5'] += deal['profit_ma5']
        
        if row['sell_ma10_price'] > 0:
            deal['profit_ma10'] = row['sell_ma10_price'] - row['buy_price']
            total_profit['ma10'] += deal['profit_ma10']
        
        if row['sell_ma20_price'] > 0:
            deal['profit_ma20'] = row['sell_ma20_price'] - row['buy_price']
            total_profit['ma20'] += deal['profit_ma20']
        
        if row['stop_price'] > 0:
            deal['profit_stop'] = row['stop_price'] - row['buy_price']
            total_profit['stop'] += deal['profit_stop']

    return code, deals, total_profit