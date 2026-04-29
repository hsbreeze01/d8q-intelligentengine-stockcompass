#!/usr/bin/python
# -*- coding: UTF-8 -*-

"""
测试DicStockFactory的统计功能
"""

import sys
import os

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from buy.cache.DicStockFactory import dicStock

def test_industry_stats():
    """测试行业统计功能"""
    print("=== 行业统计测试 ===")
    
    industry_stats = dicStock.getIndustryStats()
    print(f"总行业数量: {len(industry_stats)}")
    
    if industry_stats:
        print(f"\n行业列表（前5个）:")
        industries = list(industry_stats.items())[:5]
        for i, (industry, count) in enumerate(industries, 1):
            print(f"{i:2d}. {industry}: {count} 只股票")
    
    # 测试获取特定行业的股票数量
    if industry_stats:
        first_industry = list(industry_stats.keys())[0]
        count = dicStock.getIndustryStockCount(first_industry)
        print(f"\n'{first_industry}' 行业股票数量: {count}")

def test_concept_stats():
    """测试概念统计功能"""
    print("\n=== 概念统计测试 ===")
    
    concept_stats = dicStock.getConceptStats()
    print(f"总概念数量: {len(concept_stats)}")
    
    if concept_stats:
        print(f"\n概念列表（前5个）:")
        concepts = list(concept_stats.items())[:5]
        for i, (concept, count) in enumerate(concepts, 1):
            print(f"{i:2d}. {concept}: {count} 只股票")
    
    # 测试获取特定概念的股票数量
    if concept_stats:
        first_concept = list(concept_stats.keys())[0]
        count = dicStock.getConceptStockCount(first_concept)
        print(f"\n'{first_concept}' 概念股票数量: {count}")

def main():
    """主测试函数"""
    print("DicStockFactory 统计功能测试")
    print("=" * 50)
    
    try:
        print(f"加载的股票总数: {len(dicStock.data)}")
        test_industry_stats()
        test_concept_stats()
        
        print("\n" + "=" * 50)
        print("测试完成！")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()