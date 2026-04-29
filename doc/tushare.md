TuShare正是这么一个免费、开源的python财经数据接口包，已将各类数据整理为dataframe类型供我们使用。

主要用到的函数：

1.实时行情获取

tushare.get_today_all()

一次性获取当前交易所有股票的行情数据（如果是节假日，即为上一交易日，结果显示速度取决于网速）

2.历史数据获取

tushare.get_hist_data(code, start, end,ktype, retry_count,pause)

参数说明：

code：股票代码，即6位数字代码，或者指数代码（sh=上证指数 sz=深圳成指 hs300=沪深300指数 sz50=上证50 zxb=中小板 cyb=创业板）
start：开始日期，格式YYYY-MM-DD
end：结束日期，格式YYYY-MM-DD
ktype：数据类型，D=日k线 W=周 M=月 5=5分钟 15=15分钟 30=30分钟 60=60分钟，默认为D
retry_count：当网络异常后重试次数，默认为3
pause:重试时停顿秒数，默认为0
具体可参考官网http://tushare.org/index.html

而如果要进行完备详细的回测，每次在线获取数据无疑效率偏低，因此还需要入库

下面是数据库设计部分

表1：stocks

股票表，第一列为股票代码，第二列为名称，如果get_today_all()中存在的股票stocks表中没有，则插入之。

表2：hdata_date

日线表，由于分钟线只能获取一周内的数据，我们先对日线进行研究。

字段和get_hist_data返回值基本一致，多了stock_code列，并将record_date列本来是dataframe的index

stock_code,record_date,　　//主键
open,high,close,low,　　　　//开盘，最高，收盘，最低
volume,　　　　　　　　　　//成交量
price_change,p_change,　　//价差，涨幅
ma5,ma10,ma20　　　　　//k日收盘均价
v_ma5,v_ma10,v_ma20,　　//(k日volume均值)
turnover　　　　　　　　//换手率

 