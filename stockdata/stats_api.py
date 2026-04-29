#!/usr/bin/python
# -*- coding: UTF-8 -*-

"""
统计数据API
"""

import sys
import os

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from buy.cache.DicStockFactory import dicStock
from flask import jsonify

def get_market_overview():
    """
    获取市场概览数据
    """
    industry_stats = dicStock.getIndustryStats()
    concept_stats = dicStock.getConceptStats()
    
    overview = {
        'total_stocks': len(dicStock.data),
        'total_industries': len(industry_stats),
        'total_concepts': len(concept_stats)
    }
    
    return overview

def get_industry_analysis():
    """
    获取行业分析数据
    """
    industry_stats = dicStock.getIndustryStats()
    
    if not industry_stats:
        return {'error': '暂无行业数据'}
    
    # 计算统计信息
    stock_counts = list(industry_stats.values())
    avg_stocks_per_industry = sum(stock_counts) / len(stock_counts)
    max_stocks = max(stock_counts)
    min_stocks = min(stock_counts)
    
    analysis = {
        'industry_count': len(industry_stats),
        'avg_stocks_per_industry': round(avg_stocks_per_industry, 2),
        'max_stocks_in_industry': max_stocks,
        'min_stocks_in_industry': min_stocks,
        'industries': industry_stats
    }
    
    return analysis

def get_concept_analysis():
    """
    获取概念分析数据
    """
    concept_stats = dicStock.getConceptStats()
    
    if not concept_stats:
        return {'error': '暂无概念数据'}
    
    # 计算统计信息
    stock_counts = list(concept_stats.values())
    avg_stocks_per_concept = sum(stock_counts) / len(stock_counts)
    max_stocks = max(stock_counts)
    min_stocks = min(stock_counts)
    
    analysis = {
        'concept_count': len(concept_stats),
        'avg_stocks_per_concept': round(avg_stocks_per_concept, 2),
        'max_stocks_in_concept': max_stocks,
        'min_stocks_in_concept': min_stocks,
        'concepts': concept_stats
    }
    
    return analysis

# Flask路由函数
def add_stats_routes(app):
    """
    添加统计相关的路由到Flask应用
    """
    
    @app.route('/api/market/overview')
    def api_market_overview():
        """市场概览API"""
        try:
            data = get_market_overview()
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/industry/analysis')
    def api_industry_analysis():
        """行业分析API"""
        try:
            data = get_industry_analysis()
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/concept/analysis')
    def api_concept_analysis():
        """概念分析API"""
        try:
            data = get_concept_analysis()
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500