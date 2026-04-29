from flask import Flask, request, render_template, session, redirect
from flask import Blueprint
from buy.DBClient import DBClient
import json
from buy.cache import *
from llm import DoubaoLLM
from llm import DeepSeekLLM


import markdown
from datetime import datetime,timedelta
import traceback
from RecommendedStockCache import recommend_cache

page = Blueprint('page', __name__)
stockLLM = DoubaoLLM()
logger = logging.getLogger("my_logger")

@page.route('/recommended2/<date>', methods=['GET'])
def recommended_stock2(date):
    format = request.args.get('format', 'html')
    if date == 'today':
        date = datetime.now().strftime('%Y-%m-%d')

    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
        next_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
    except ValueError as ve:
        logger.error(ve)
        if format == 'json':
            return {'error': 'Invalid date format'}, 400
        return render_template('error.html', message="Invalid date format.")

    result = recommend_cache.get_recommended_stocks(date)

    # 添加industry和concept统计数据
    industry_stats = dicStock.getIndustryStats()
    concept_stats = dicStock.getConceptStats()
    

    if format == 'json':
        return {
            'recommended_stocks': result,
            'date': date,
            'prev_date': prev_date,
            'next_date': next_date,
            'industry_stats': {
                'total_industries': len(industry_stats),
                'all_stats': industry_stats
            },
            'concept_stats': {
                'total_concepts': len(concept_stats),
                'all_stats': concept_stats
            }
        }
    return render_template('recommended_stocks.html', 
                         recommended_stocks=result, 
                         date=date, 
                         prev_date=prev_date, 
                         next_date=next_date,
                         industry_stats={
                             'total_industries': len(industry_stats),
                             'all_stats': industry_stats
                         },
                         concept_stats={
                             'total_concepts': len(concept_stats),
                             'all_stats': concept_stats
                         })

@page.route('/recommended/<date>', methods=['GET'])
def recommended_stocks(date):
    format = request.args.get('format', 'html')
    if date == 'today':
        date = datetime.now().strftime('%Y-%m-%d')

    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
        next_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
    except ValueError as ve:
        logger.error(ve)
        if format == 'json':
            return {'error': 'Invalid date format'}, 400
        return render_template('error.html', message="Invalid date format.")
    
    try:
        mc = DBClient()
        sql = f"select a.stock_code, b.stock_name, b.industry, a.buy, a.record_time,c.open,c.close,c.high,c.low ,c.volume ,c.turnover ,c.amplitude ,c.change_percentage ,c.change_amount ,c.turnover_rate from stock_analysis a, dic_stock b,stock_data_daily c  where a.buy > 0 and a.stock_code = b.code and a.stock_code  = c.stock_code  and a.record_time = '{date}' and a.record_time  = c.`date`  order by b.industry,b.stock_name"
        # sql = f"select a.stock_code, b.stock_name, b.industry, a.buy, a.record_time from stock_analysis a, dic_stock b where a.buy > 0 and a.stock_code = b.code and a.record_time = '{date}' order by b.industry,b.stock_name"
        count, recommended_stocks = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        if format == 'json':
            return {'error': 'Error fetching recommended stocks'}, 500
        return render_template('error.html', message="Error fetching recommended stocks.")
    finally:
        mc.close()
    
    #拼接股票概念数据
    for stock in recommended_stocks:
        stock_code = stock['stock_code']
        try:
            concepts = dicStock.data[dicStock.data['code'] == stock_code]['concepts'].values[0]
            stock['concepts'] = concepts
        except Exception as ex:
            logger.error(f"Error processing stock_code: {stock_code}, Exception: {ex}")

    try:
        mc = DBClient()
        sql = f"select category_name, count(*) as total from stock_analysis_stat where date = '{date}' and type = 0 group by category_name order by total desc"
        count, industry_count = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        if format == 'json':
            return {'error': 'Error fetching category statistics'}, 500
        return render_template('error.html', message="Error fetching category statistics.")
    finally:
        mc.close()
    
    try:
        mc = DBClient()
        sql = f"select category_name, count(*) as total from stock_analysis_stat where date = '{date}' and type = 1 group by category_name order by total desc"
        count, concept_count = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        if format == 'json':
            return {'error': 'Error fetching category statistics'}, 500
        return render_template('error.html', message="Error fetching category statistics.")
    finally:
        mc.close()

    try:
        mc = DBClient()
        #查询stock_analysis_stat 表里日期<=date的最近5天的日期
        sql = "SELECT DISTINCT date FROM stock_analysis_stat WHERE date <= %s ORDER BY date DESC LIMIT 5"
        count, dates = mc.select_many(sql, (date,))

        # 遍历日期列表
        # 1. 查询每个日期的推荐股票数量
        # 2. 查询每个日期的行业股票数量
        # 3. 查询每个日期的概念股票数量
        date_stats = []
        for d in dates:
            d = d['date'].strftime('%Y-%m-%d')
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
                'recommended_count': recommended_count[0]['total'],
                'industry_stock_count': industry_stock_count,
                'concept_stock_count': concept_stock_count
            })
        
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        if format == 'json':
            return {'error': 'Error fetching dates'}, 500
        return render_template('error.html', message="Error fetching dates.")
    finally:
        mc.close()


    if format == 'json':
        return {
            'recommended_stocks': recommended_stocks,
            'industry_count': industry_count,
            'concept_count': concept_count,
            'prev_date': prev_date,
            'next_date': next_date,
            'date': date,
            'date_stats': date_stats
        }
    return render_template('recommended_stocks.html', recommended_stocks=recommended_stocks,industry_count = industry_count,concept_count = concept_count, prev_date=prev_date, next_date=next_date, date=date, date_stats=date_stats)


#查看最近7天这个行业都推荐了哪些股票
@page.route('/industry/recommended/<industry>', methods=['GET'])
def industry_recommended_stocks(industry):
    format = request.args.get('format', 'html')
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
        next_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
    except ValueError as ve:
        logger.error(ve)
        if format == 'json':
            return {'error': 'Invalid date format'}, 400
        return render_template('error.html', message="Invalid date format.")
    
    try:
        mc = DBClient()

        sql = f"select a.stock_code, b.stock_name , a.date,c.open,c.close,c.high,c.low ,c.volume ,c.turnover ,c.amplitude ,c.change_percentage ,c.change_amount ,c.turnover_rate from stock_analysis_stat a,dic_stock b,stock_data_daily c where a.type = 0 and a.stock_code = b.code and a.stock_code  = c.stock_code and a.date = '{date}' and a.date  = c.`date` and a.category_name  = '{industry}' order by b.stock_name"
        count, recommended_stocks = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        if format == 'json':
            return {'error': 'Error fetching recommended stocks'}, 500
        return render_template('error.html', message="Error fetching recommended stocks.")
    finally:
        mc.close()

    if format == 'json':
        return {
            'recommended_stocks': recommended_stocks,
            'category': industry,
            'date': date,
            'prev_date': prev_date,
            'next_date': next_date
        }
    return render_template('industry_recommended_stocks.html', recommended_stocks=recommended_stocks, category=industry , date=date,prev_date = prev_date,next_date = next_date)


#查看最近7天这个概念都推荐了哪些股票
@page.route('/concept/recommended/<concept>', methods=['GET'])
def concept_recommended_stocks(concept):
    format = request.args.get('format', 'html')
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
        next_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
    except ValueError as ve:
        logger.error(ve)
        if format == 'json':
            return {'error': 'Invalid date format'}, 400
        return render_template('error.html', message="Invalid date format.")
    
    try:
        mc = DBClient()

        sql = f"select a.stock_code, b.stock_name , a.date,c.open,c.close,c.high,c.low ,c.volume ,c.turnover ,c.amplitude ,c.change_percentage ,c.change_amount ,c.turnover_rate from stock_analysis_stat a,dic_stock b,stock_data_daily c where a.type = 1 and a.stock_code = b.code and a.stock_code  = c.stock_code and a.date = '{date}' and a.date  = c.`date` and a.category_name  = '{concept}' order by b.stock_name"

        # sql = f"select a.stock_code, b.stock_name , a.date from stock_analysis_stat a,dic_stock b where a.type = 1 and a.stock_code = b.code and a.date = '{date}' and a.category_name  = '{concept}' order by b.stock_name"
        count, recommended_stocks = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        if format == 'json':
            return {'error': 'Error fetching recommended stocks'}, 500
        return render_template('error.html', message="Error fetching recommended stocks.")
    finally:
        mc.close()

    if format == 'json':
        return {
            'recommended_stocks': recommended_stocks,
            'category': concept,
            'date': date,
            'prev_date': prev_date,
            'next_date': next_date
        }
    return render_template('concept_recommended_stocks.html', recommended_stocks=recommended_stocks, category=concept, date=date,prev_date = prev_date,next_date = next_date)


@page.route('/stock/<code>', methods=['GET'])
def stock_advice(code):
    format = request.args.get('format', 'html')
    logger.debug(f"uid: {session.get('uid')}")

    try:
        mc = DBClient()
        # 更新最新数据，同时更新股票的最后刷新时间
        sql = f"select stock_code, record_time, buy, sell from stock_analysis where stock_code ='{code}' order by record_time desc"
        count, result = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        if format == 'json':
            return {'error': 'Error fetching stock advice'}, 500
        return render_template('error.html', message="Error fetching stock advice.")
    finally:
        mc.close()

    if format == 'json':
        return {
            'code': code,
            'stocks': result
        }
    return render_template('stock_advice.html', code=code, stocks=result)

@page.route('/advice/<code>/<record_time>', methods=['GET'])
def advice_detail(code, record_time):
    format = request.args.get('format', 'html')

    #防止日期超过已获取数据的最大日期
    try:
        mc = DBClient()
        # 更新最新数据，同时更新股票的最后刷新时间
        sql = f"select max(a.record_time) as record_time from stock_analysis a where a.stock_code ='{code}'"
        count, result = mc.select_one(sql)
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        if format == 'json':
            return {'error': 'Error fetching stock advice'}, 500
        return render_template('error.html', error="Error fetching stock advice.")
    finally:
        mc.close()

    if count == 0:
        if format == 'json':
            return {'error': 'Error fetching stock advice'}, 500
        return render_template('error.html', error="Error fetching stock advice.")
    
    # Convert record_time string to datetime for comparison
    try:
        record_time_date = datetime.strptime(record_time, '%Y-%m-%d').date()
        
        if record_time_date > result['record_time']:
            record_time = result['record_time'].strftime('%Y-%m-%d')
    except ValueError as e:
        logger.error(f"Date conversion error: {e}")
        if format == 'json':
            return {'error': 'Invalid date format'}, 400 
        return render_template('error.html', error="Invalid date format")

    try:
        mc = DBClient()
        # 更新最新数据，同时更新股票的最后刷新时间
        sql = f"select a.*,b.stock_name from stock_analysis a,dic_stock b where a.stock_code ='{code}' and a.record_time='{record_time}' and a.stock_code = b.code"
        count, result = mc.select_one(sql)
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        if format == 'json':
            return {'error': 'Error fetching stock advice'}, 500
        return render_template('error.html', error="Error fetching stock advice.")
    finally:
        mc.close()
    
    if count == 0:
        if format == 'json':
            return {'error': '无今日数据'}, 500
        return render_template('error.html', error="无今日数据")

    analysis_data = json.loads(result['analysis_data'])
    buy_advice = json.loads(result['buy_advice'])
    analysis_data = json.loads(analysis_data)
    buy_advice = json.loads(buy_advice)

    buy = result['buy']
    sell = result['sell']
    record_time = result['record_time']
    stock_code = result['stock_code']
    stock_name = result['stock_name']

    try:
        mc = DBClient()
        sql = f"SELECT * FROM stock_events WHERE stock_code='{code}' AND date >= DATE_SUB('{record_time}', INTERVAL 10 DAY) and date <= '{record_time}'"
        count, events = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        logger.error(f"An error occurred while select llm {ex}\n"
                     f"Traceback: {traceback.format_exc()}")
        mc.rollback()
        if format == 'json':
            return {'error': '事件获取异常'}, 500
        return render_template('error.html', error="事件获取异常")
    finally:
        mc.close()

    if format == 'json':
        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'record_time': record_time.strftime('%Y-%m-%d'),
            'buy': buy,
            'sell': sell,
            'analysis_data': analysis_data,
            'buy_advice': buy_advice,
            'events': events
        }

    return render_template('stock_advice_detail.html', record_time=record_time, stock_code=stock_code, buy=buy, sell=sell,analysis_data=analysis_data, buy_advice=buy_advice,events=events)


@page.route('/llm/<code>/<record_time>', methods=['GET'])
def llm_detail(code, record_time):
    format = request.args.get('format', 'html')

# CREATE TABLE stock_llm (
#     id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
#     stock_code CHAR(10) NOT NULL COMMENT '股票代码',
#     record_time DATE NOT NULL COMMENT '记录时间',
#     content JSON NOT NULL COMMENT '内容',
#     UNIQUE INDEX unique_stock_record (stock_code, record_time)
# ) COMMENT='stock_llm table';

# 1.通过上面的表根据参数code和record_time查询出对应的数据
# 2.如果数据存在，将content字段的内容解析成json对象
# 3.如果数据不存在，则查询stock_analysis表中的数据，将analysis_data和buy_advice字段的内容解析成json对象
# 4.将数据存入stock_llm表中

    try:
        mc = DBClient()
        sql = f"SELECT content FROM stock_llm WHERE stock_code='{code}' AND record_time='{record_time}'"
        count, result = mc.select_one(sql)
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        return False
    finally:
        mc.close()

    if result:
        content = result['content']
        content = markdown.markdown(content)
        logger.debug(content)
        if format == 'json':
            return {
                'content': content
            }
        return render_template('stock_advice_detail_llm.html', content=content)
    
    #如果没有llm分析过，则查询后保存
    try:
        mc = DBClient()
        # 更新最新数据，同时更新股票的最后刷新时间
        sql = f"select a.*,b.stock_name from stock_analysis a,dic_stock b where a.stock_code ='{code}' and a.record_time='{record_time}' and a.stock_code = b.code"
        count, result = mc.select_one(sql)
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        return False
    finally:
        mc.close()

    # print(result)
    
    analysis_data = json.loads(result['analysis_data'])
    buy_advice = json.loads(result['buy_advice'])
    analysis_data = json.loads(analysis_data)
    buy_advice = json.loads(buy_advice)

    buy = result['buy']
    sell = result['sell']
    record_time = result['record_time']
    stock_code = result['stock_code']
    stock_name = result['stock_name']

    try:
        mc = DBClient()
        sql = f"SELECT * FROM stock_events WHERE stock_code='{code}' AND date >= DATE_SUB('{record_time}', INTERVAL 3 DAY) and date <= '{record_time}'"
        count, events = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        logger.error(f"An error occurred while select llm {ex}\n"
                     f"Traceback: {traceback.format_exc()}")
        mc.rollback()
        return render_template('error.html', message="Error fetching stock events.")
    finally:
        mc.close()

    message = generate_plain_text(stock_code, stock_name,record_time, buy, sell, buy_advice, analysis_data,events)
    

    # 通过llm分析数据
    try:
        message = stockLLM.stock_message(message)
    except Exception as ex:
        logger.error(ex)
        if format == 'json':
            return {
                'content': ex
            }
        return render_template('stock_advice_detail_llm.html', content=ex)

    logger.debug(message)

    # 提示错误依然保存，防止持续调用llm 产生费用
    if len(message) < 100:
        logger.error("The generated message is too short.")
    
    try:
        mc = DBClient()
        sql = "INSERT INTO stock_llm (stock_code, record_time, content) VALUES (%s, %s, %s)"
        params = (code, record_time, message)
        mc.execute(sql, params)
        logger.debug(sql)
        mc.commit()
    except Exception as ex:
        logger.error(f"An error occurred while insert llm {ex}\n"
                     f"Traceback: {traceback.format_exc()}")
        mc.rollback()
        return False
    finally:
        mc.close()

    message = markdown.markdown(message)
    
    if format == 'json':
        return {
            'content': message
        }

    return render_template('stock_advice_detail_llm.html', content=message)




def generate_plain_text(stock_code,stock_name ,record_time, buy, sell, buy_advice, analysis_data,events):
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

#     78	000526	学大教育	资产重组	紫光集团有限公司管理人(以下简称“管理人”)履行紫光集团等七家企业实质合并重整案重整计划相关规定,根据紫光集团指令进行减持安排,管理人与南京星纳赫源创业投资合伙企业(有限合伙)于2024年12月12日签署了《股份转让协议》,约定将其通过紫光集团有限公司破产企业财产处置专用账户持有的6,162,000股无限售条件流通股(占上市公司总股本的5.00%)通过协议转让方式以每股40.302元(不低于2024年12月11日收盘价44.78元/股的90%)转让给受让方。	2025-02-20
# 79	000591	太阳能	资产重组	五常分布式项目预计总投资约为6,170.69万元,其中资本金不低于1,234.14万元(不超过1,851.21万元),该项目拟由五常分公司作为投资建设主体,投资资本金由中节能太阳能科技有限公司(以下简称太阳能科技公司)通过向中节能太阳能科技哈尔滨有限公司(法人主体)增资的方式,根据项目建设需求分批陆续注入。	2025-02-20
    text.append("4.事件记录\n")
    for event in events:
        text.append(f"{event['date']} {event['stock_code']} {event['stock_name']} {event['event_type']} {event['event_detail']}\n")

    return "\n".join(text)

# plain_text = generate_plain_text(stock_code, record_time, buy, sell, buy_advice, analysis_data)
# print(plain_text)




