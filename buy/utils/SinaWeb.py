#!/usr/bin/python
# -*- encoding: utf-8 -*-

"""
Description: 
Version: 1.0
Autor: Sam Zhu
Date: 2021-01-02 14:56:09
LastEditTime: 2021-01-02 14:56:09
""" 

import datetime
baseUrl = 'http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?scale=60&ma=no&datalen=1023&symbol='

def getHistoryUrls(stockID):

    if int(stockID) >= 600000:
	    stockUrl = baseUrl + 'sh' + (stockID)
    else:
        stockUrl = baseUrl + 'sz' + (stockID)
    
    return stockUrl



def getCurrentUrls(page):
    """    
    获取所有当日数据的列表,page为页码目前43页，最多50即可
    """
    url_temp = 'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={}&num=100&sort=symbol&asc=1&node=hs_a&symbol=&_s_r_a=auto'
    urls = []
    for i in range(1,page+1):
        url = url_temp.format(i)
        urls.append(url)
    return urls