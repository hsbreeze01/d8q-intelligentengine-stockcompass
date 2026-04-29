import requests
import concurrent.futures
import os
import sys
curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
path = os.path.split(rootPath)[0]
# print(curPath,rootPath,path)
sys.path.append(path) # 这句是为了导入_config
sys.path.append(rootPath)

from bs4 import BeautifulSoup
from buy.cache import *

def get_stock_info(stock_code):
    url = f'https://finance.sina.com.cn/realstock/company/{stock_code}/nc.shtml'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'accept-language':'zh-CN,zh;q=0.9,en;q=0.8'
    }
    response = requests.get(url, headers=headers)
    # response.encoding = response.apparent_encoding  # 自动检测编码
    response.encoding = 'GB2312'

    soup = BeautifulSoup(response.text, 'lxml')
    
    # 获取股票名称
    stock_name = ""
    try:
        stock_name_tag = soup.find('h1', id='stockName').find('i', class_='c8_name')
        if stock_name_tag:
            stock_name = stock_name_tag.text.strip()
    except Exception as e:
        print(f"解析股票名称时出错: {e}")

    # 获取所属板块信息
    concepts = []
    try:
        # 找到包含所属板块的 <p> 标签
        overview_div = soup.find('div', class_='com_overview blue_d')
        if overview_div:
            # 找到所有 <p> 标签
            p_tags = overview_div.find_all('p')
            for p in p_tags:
                # 找到包含 "所属板块：" 的 <p> 标签
                if '所属板块：' in p.text:
                    # 提取所有 <a> 标签中的文本
                    concept_tags = p.find_all('a')
                    for tag in concept_tags:
                        concepts.append(tag.text.strip())
                    break  # 找到后退出循环
    except Exception as e:
        print(f"解析网页时出错: {e}")
    
    return stock_name, concepts

def all_stock_concepts():
    # os.environ['DevENV'] = 'prod'
    print(os.getenv('DevENV'))
    # dicStock.setNeedReload()
    dicStock.reload()
    pd = dicStock.data
    mc = DBClient()
    for index in pd.index:
        # 根据股票id补全每日股票数据
        stock_code = pd.loc[index]["code"]
        # 示例股票代码
        # stock_code = '301150'  # 浦发银行
        stock_code = f'sh{stock_code}' if stock_code.startswith('6') else f'sz{stock_code}'

        stock_name, concepts = get_stock_info(stock_code)

        print(f"股票代码: {stock_code}")
        print(f"股票名称: {stock_name}")
        print(f"所属板块: {', '.join(concepts)}")
        print("=" * 50)
        # break

all_stock_concepts()