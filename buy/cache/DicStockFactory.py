#!/usr/bin/python
# -*- encoding: utf-8 -*-

"""
Description: 
Version: 1.0
Autor: Sam Zhu
Date: 2021-01-02 15:24:57
LastEditTime: 2021-03-06 14:22:07
""" 

import logging
import yaml #pip3 install pyyaml
from ..DBClient import DBClient
import pandas as pd

import os

class DicStockFactory(object):
    """
    docstring
    """
    log = logging.getLogger("mainModule.DicStockFactory")

    def __init__(self):
        self.load()
        self.needReload = False
        pass

    #只看流通市值在200亿以上的股票，股价过低的股票容易被人操盘，技术指标的参考性不高
    def load(self):
        """
        加载默认字典
        """
        mc = DBClient()
        stocks = [
            '600036', '600050', '000651', '000858', '601168', '000725',
            '688981', '002594', '002600', '601360', '601998', '000301', '000883',
            '002152', '000830', '603659', '600000', '002271', '600038', '000921',
            '600085', '601995', '600745', '689009', '600363', '603596', '000988',
            '603658', '300496', '688169', '688012', '300832', '688363'
        ]
        
        # stocks = ['688393', '688435', '688315', '688358', '688246', '688225', '688244', '688196', '688229', '688590', '688031', '688158', '688222', '688369', '688560', '688615', '688561', '688258', '688629', '600397', '600539', '600734', '603768', '603803', '603117']

        # stocks = ['603007']

        prefix = ['000', '001', '600', '601', '603', '605']
        # sql = 'SELECT * FROM dic_stock where circulating_market_value  > 20000000000 and stock_prefix in (' + ','.join([f"'{p}'" for p in prefix]) + ')'

        # sql = 'SELECT * FROM dic_stock where code in (' + ','.join(stocks) + ')'
        #查找所有未退市，latest_price > 0的股票
        
        env = os.getenv('DevENV', 'dev')
        if env == 'dev':
            sql = 'SELECT * FROM dic_stock where code in (' + ','.join(stocks) + ') and status = 0'
            # sql = 'SELECT * FROM dic_stock where latest_price > 0 and status = 0'
        else:
            sql = 'SELECT * FROM dic_stock where latest_price > 0 and status = 0'

        count,rows = mc.select_many(sql)

        # dataframe_cols=[tuple[0] for tuple in cur.description]#列名和数据库列一致
        self.data = pd.DataFrame(rows)

        # Query stock_concept table and append concepts to self.data
        concepts_dict = {}
        for index, row in self.data.iterrows():
            stock_code = row['code']
            sql = f"SELECT concept_name FROM stock_concept WHERE stock_code = '{stock_code}'"
            count, concepts = mc.select_many(sql)
            concepts_dict[stock_code] = [concept['concept_name'] for concept in concepts]

        self.data['concepts'] = self.data['code'].map(concepts_dict)


        #统计industry和concepts共有多少股票，并存储在缓存
        #industry在dic_stock 表，concept在stock_concept表，表结构在db.sql中
        
        # 统计各行业的股票数量
        industry_sql = """
            SELECT industry, COUNT(*) as stock_count 
            FROM dic_stock 
            WHERE latest_price > 0 AND status = 0 
            GROUP BY industry
        """
        count, industry_stats = mc.select_many(industry_sql)
        self.industry_stats = {row['industry']: row['stock_count'] for row in industry_stats}
        
        # 统计各概念的股票数量
        concept_sql = """
            SELECT sc.concept_name, COUNT(DISTINCT sc.stock_code) as stock_count
            FROM stock_concept sc
            INNER JOIN dic_stock ds ON sc.stock_code = ds.code
            WHERE ds.latest_price > 0 AND ds.status = 0
            GROUP BY sc.concept_name
        """
        count, concept_stats = mc.select_many(concept_sql)
        self.concept_stats = {row['concept_name']: row['stock_count'] for row in concept_stats}
        
        # 记录统计信息到日志
        self.log.info(f"Industry statistics loaded: {len(self.industry_stats)} industries")
        self.log.info(f"Concept statistics loaded: {len(self.concept_stats)} concepts")

        mc.close()

        # print(self.data)
        pass

    def reload(self):
        if self.needReload:
            self.load()
            self.needReload = False
        
        pass

    def setNeedReload(self):
        self.needReload = True
        pass
    
    def isExist(self, code):
        """
        指定code是否存在
        """
        return code in self.data['code'].values
    
    def getIndustryStats(self):
        """
        获取行业统计数据
        返回: dict {industry_name: stock_count}
        """
        return getattr(self, 'industry_stats', {})
    
    def getConceptStats(self):
        """
        获取概念统计数据
        返回: dict {concept_name: stock_count}
        """
        return getattr(self, 'concept_stats', {})
    
    def getIndustryStockCount(self, industry_name):
        """
        获取指定行业的股票数量
        """
        return self.getIndustryStats().get(industry_name, 0)
    
    def getConceptStockCount(self, concept_name):
        """
        获取指定概念的股票数量
        """
        return self.getConceptStats().get(concept_name, 0)
    

    
dicStock = DicStockFactory()