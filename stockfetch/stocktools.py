#!/usr/bin/python
# -*- coding: UTF-8 -*-

import tushare as ts

class StockTools:

    def __init__(self):
        return

# 获取历史交易数据
# df = ts.get_hist_data('600848')
# ts.get_hist_data('600848'，ktype='W') #获取周k线数据
# ts.get_hist_data('600848'，ktype='M') #获取月k线数据
# ts.get_hist_data('600848'，ktype='5') #获取5分钟k线数据
# ts.get_hist_data('600848'，ktype='15') #获取15分钟k线数据
# ts.get_hist_data('600848'，ktype='30') #获取30分钟k线数据
# ts.get_hist_data('600848'，ktype='60') #获取60分钟k线数据
# ts.get_hist_data('sh'）#获取上证指数k线数据，其它参数与个股一致，下同
# ts.get_hist_data('sz'）#获取深圳成指k线数据 ts.get_hist_data('hs300'）#获取沪深300指数k线数据
# ts.get_hist_data('sz50'）#获取上证50指数k线数据
# ts.get_hist_data('zxb'）#获取中小板指数k线数据
# ts.get_hist_data('cyb'）#获取创业板指数k线数据

    def history(self,code):
        return ts.get_hist_data(code)

#获取历史分笔数据
#df = ts.get_tick_data('000756','2015-03-27')
#df.head(10)
    def tickData(self,code,date):
        return ts.get_tick_data(code,date)

#获取实时分笔数据
#df = ts.get_realtime_quotes('000581') 
#print df[['code','name','price','bid','ask','volume','amount','time']]
    def current(self,code):
        return ts.get_realtime_quotes(code)
#行业分类
    def industry(self):
        return ts.get_industry_classified() 


#概念分类，所有股票炒作概念，比如苹果、特斯拉等
    def concept(self):
        return ts.get_concept_classified()

#地域分类
    def area(self):
        return ts.get_area_classified()

#中小板分类
    def sme(self):
        return ts.get_sme_classified()

#创业板分类
    def gem(self):
        return ts.get_gem_classified()

#风险警示板分类
    def st(self):
        return ts.get_st_classified()

#沪深300成份股及权重
    def hs300(self):
        return ts.get_hs300s()

#上证50成份股
    def sz50(self):
        return ts.get_sz50s()

#沪深股票列表（基础数据，沪深所有股票情况）
    def stockBasic(self):
        return ts.get_stock_basics()

#业绩报告（主表）
#获取2014年第3季度的业绩报表数据
    def report(self,year,season):
        return ts.get_report_data(year,season)

#盈利能力数据
#获取2014年第3季度的盈利能力数据
    def profitData(self,year,season):
        return ts.get_profit_data(year,season)

#营运能力数据
#获取2014年第3季度的营运能力数据
    def operationData(self,year,season):
        return ts.get_operation_data(year,season)

#成长能力数据
    def growthData(self,year,season):
        return ts.get_growth_data(year,season)

#偿债能力数据
    def debtPaying(self,year,season):
        return ts.get_debtpaying_data(year,season)

#现金流量数据
    def cashFlow(self,year,season):
        return ts.get_cashflow_data(year,season)


def __TestCase():
    print("aaa")
    st = StockTools()
    print(st.area())

if __name__ == '__main__':
    print ('作为主程序运行')
    __TestCase()
else:
    print ('StockTools.py init')




