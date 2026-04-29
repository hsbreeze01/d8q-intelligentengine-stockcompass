#A股票行情数据获取演示   https://github.com/mpquant/Ashare
from  Ashare import *

import akshare as ak    
from datetime import datetime


# 证券代码兼容多种格式 通达信，同花顺，聚宽
# sh000001 (000001.XSHG)    sz399006 (399006.XSHE)   sh600519 ( 600519.XSHG ) 

# df=get_price('sh600036',frequency='1d',count=10)      #默认获取今天往前5天的日线行情
# print('上证指数日线行情\n',df)

# df=get_price('000001.XSHG',frequency='1d',count=5,end_date='2021-04-30')   #可以指定结束日期，获取历史行情
# print('上证指数历史行情\n',df)
    
# df=get_price('sh600519',frequency='15m',count=5)     #分钟线行情，只支持从当前时间往前推，可用'1m','5m','15m','30m','60m'
# print('贵州茅台15分钟线\n',df)

# df=get_price('600519.XSHG',frequency='60m',count=6)  #分钟线行情，只支持从当前时间往前推，可用'1m','5m','15m','30m','60m'
# print('贵州茅台60分钟线\n',df)


stock_sse_summary_df = ak.stock_sse_summary()
print(stock_sse_summary_df)


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
stock_zh_a_daily_qfq_df = ak.stock_zh_a_daily(symbol="sh600036", start_date="20250215", end_date="20250220", adjust="qfq")
print(stock_zh_a_daily_qfq_df)


df = ak.stock_zh_a_hist(symbol='600036', period="daily",  start_date="20250215", end_date="20250220", adjust="qfq",timeout=60)
print(df)
# ask 是东方财富 股票编码不加头比如sh，sz
# 东方财富-行情报价 -- 实时报价
stock_bid_ask_em_df = ak.stock_bid_ask_em(symbol="600036")
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
print(stock_zh_a_spot_em_df[stock_zh_a_spot_em_df['代码'] == '600036'].to_string())


#东方财富的历史数据
stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol="600036", period="daily", start_date="20240301", end_date='20241228', adjust="qfq")
print(stock_zh_a_hist_df)


pass

#股票动态（可以给llm用）
stock_gsrl_gsdt_em_df = ak.stock_gsrl_gsdt_em(date="20250222")
print(stock_gsrl_gsdt_em_df[stock_gsrl_gsdt_em_df.apply(lambda row: row.astype(str).str.contains('招商银行').any(), axis=1)].to_string())


#东方财富 风险警示版
stock_zh_a_st_em_df = ak.stock_zh_a_st_em()
print(stock_zh_a_st_em_df)

#机构调研数据 （可以作为热点）
stock_jgdy_tj_em_df = ak.stock_jgdy_tj_em(date="20241128")
print(stock_jgdy_tj_em_df)
print(stock_jgdy_tj_em_df[stock_jgdy_tj_em_df['代码'] == '688227'].to_string())

#机构调研-详细(被禁止了)
# stock_jgdy_detail_em_df = ak.stock_jgdy_detail_em(date="20241128")
# print(stock_jgdy_detail_em_df)

#描述: 东方财富网-数据中心-特色数据-千股千评-主力控盘-机构参与度
#返回的数值是百分比
stock_comment_detail_zlkp_jgcyd_em_df = ak.stock_comment_detail_zlkp_jgcyd_em(symbol="600036")
print(stock_comment_detail_zlkp_jgcyd_em_df)

#用户关注的热度
stock_comment_detail_scrd_focus_em_df = ak.stock_comment_detail_scrd_focus_em(symbol="600036")
print(stock_comment_detail_scrd_focus_em_df)

#市场参与热度（接口已废弃）
# 日期时间	datetime64	-
# 大户	float64	-
# 全部	float64	-
# 散户	float64
# stock_comment_detail_scrd_desire_em_df = ak.stock_comment_detail_scrd_desire_em(symbol="600036")
# print(stock_comment_detail_scrd_desire_em_df)

#日度市场参与意愿
# 交易日	object	-
# 当日意愿上升	float64	-
# 5日平均参与意愿变化	float64	-
stock_comment_detail_scrd_desire_daily_em_df = ak.stock_comment_detail_scrd_desire_daily_em(symbol="600036")
print(stock_comment_detail_scrd_desire_daily_em_df)

#市场成本（接口已废弃）
# stock_comment_detail_scrd_cost_em_df = ak.stock_comment_detail_scrd_cost_em(symbol="600036")
# print(stock_comment_detail_scrd_cost_em_df)

#个股新闻
# 关键词	object	-
# 新闻标题	object	-
# 新闻内容	object	-
# 发布时间	object	-
# 文章来源	object	-
# 新闻链接	object	-
stock_news_em_df = ak.stock_news_em(symbol="600036")
today = datetime.today().strftime('%Y-%m-%d')
filtered_news = stock_news_em_df[stock_news_em_df['发布时间'].str.contains(today)]
print(filtered_news.to_string())
# 按照发布时间排序
stock_news_em_df = stock_news_em_df.sort_values(by='发布时间', ascending=False)
print(stock_news_em_df.to_string())

#股东增减
#  "全部": "",
#         "股东增持": '(DIRECTION="增持")',
#         "股东减持": '(DIRECTION="减持")',
# 该函数已经被改，只读最近2页的内容
stock_ggcg_em_df = ak.stock_ggcg_em(symbol="全部")
print(stock_ggcg_em_df)

# #筹码分布
# 90 成本 - 低：表示股票市场中 90% 的投资者的持仓成本处于较低的价位区间。它反映了大部分投资者在该股票上的成本相对较低，可能暗示着在当前股价附近存在较强的支撑，因为这些低成本的投资者在股价下跌时可能不太愿意轻易卖出.
# 90 集中度：指的是 90% 的流通股份集中在某一价位区间的程度。集中度数值越小，说明筹码越集中在少数价位上，通常意味着主力资金对该股票的控盘程度较高，股票的走势可能更容易受到主力的影响。例如，当 90 集中度在 10 以下时，说明筹码高度集中，主力吸筹可能已经接近尾声，股价有望迎来拉升.
# 70 成本 - 低：与 90 成本 - 低类似，是指 70% 的投资者的持仓成本处于较低水平。这表明在当前股价之下，有相当一部分投资者的成本较低，对股价的下跌有一定的支撑作用，同时也反映了股票的成本结构特点.
# 70 成本 - 高：则表示 70% 的投资者的持仓成本处于较高的价位区间。意味着大部分投资者的成本较高，如果股价处于当前价位或低于当前价位，这些投资者可能处于亏损状态，股票的上方套牢盘压力较大，对股价的上涨可能会形成一定的阻力.
# 70 集中度：即 70% 的流通股份在某一价位区间的集中程度。同样，集中度越低，说明筹码越集中，股票的稳定性和可操作性可能越强。当 70 集中度和 90 集中度都较低时，如都在 10 以下，通常表示筹码高度集中，股票的走势可能更具趋势性，主力控盘迹象明显.
stock_cyq_em_df = ak.stock_cyq_em(symbol="600036", adjust="qfq")
print(stock_cyq_em_df)

#每日明细 大宗交易
stock_dzjy_mrmx_df = ak.stock_dzjy_mrmx(symbol='A股', start_date='20241104', end_date='20241130')
print(stock_dzjy_mrmx_df)

#赚钱效应分析
# 涨跌比：即沪深两市上涨个股所占比例，体现的是市场整体涨跌，占比越大则代表大部分个股表现活跃。
# 涨停板数与跌停板数的意义：涨停家数在一定程度上反映了市场的投机氛围。当涨停家数越多，则市场的多头氛围越强。真实涨停是非一字无量涨停。真实跌停是非一字无量跌停。

stock_market_activity_legu_df = ak.stock_market_activity_legu()
print(stock_market_activity_legu_df)