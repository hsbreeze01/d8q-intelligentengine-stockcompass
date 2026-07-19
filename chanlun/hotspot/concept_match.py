# -*- coding: utf-8 -*-
"""概念关联匹配: 将个股与热点概念板块关联，输出共振信息。

用途: czsc_scorer 调用，判断信号标的是否处于升温概念中。
只有当概念连续升温>=2天时才认为有效共振，否则不输出。
"""
import pymysql
from datetime import date, timedelta
from typing import Optional, Dict

DB = {'host': '127.0.0.1', 'port': 3306, 'user': 'root',
      'password': 'password', 'database': 'stock_analysis_system', 'charset': 'utf8mb4'}


def get_warming_concepts(min_days: int = 2) -> Dict[str, dict]:
    """获取当前正在升温的概念(连续升温>=min_days天)。
    
    Returns: {concept_name: {heat_score, anomaly_type, days_warming, board_code}}
    """
    try:
        conn = pymysql.connect(**DB, cursorclass=pymysql.cursors.DictCursor)
        cur = conn.cursor()
        today = date.today()
        # 查最近7天有异动的概念
        cur.execute('''SELECT topic, source, heat_score, anomaly_type, 
                       DATEDIFF(%s, MIN(trend_date)) + 1 as days_active
                       FROM t_heat_trend 
                       WHERE is_anomaly=1 AND trend_date >= %s
                       GROUP BY topic, source, heat_score, anomaly_type
                       HAVING days_active >= %s
                       ORDER BY heat_score DESC''',
                    (today, today - timedelta(days=7), min_days))
        rows = cur.fetchall()
        conn.close()
        
        result = {}
        for r in rows:
            result[r['topic']] = {
                'heat_score': float(r['heat_score']),
                'anomaly_type': r['anomaly_type'],
                'days_active': r['days_active'],
                'source': r['source'],
            }
        return result
    except Exception:
        return {}


def get_concept_board_hot(min_flow: float = 1e8) -> Dict[str, dict]:
    """获取当日资金净流入>1亿的概念板块。
    
    Returns: {board_name: {board_code, change_pct, net_inflow, rank}}
    """
    try:
        conn = pymysql.connect(**DB, cursorclass=pymysql.cursors.DictCursor)
        cur = conn.cursor()
        today = date.today()
        cur.execute('''SELECT board_code, board_name, change_pct, net_inflow, rank_by_flow
                       FROM t_concept_board_daily
                       WHERE trade_date = %s AND net_inflow >= %s
                       ORDER BY net_inflow DESC LIMIT 20''',
                    (today, min_flow))
        rows = cur.fetchall()
        conn.close()
        
        result = {}
        for r in rows:
            result[r['board_name']] = {
                'board_code': r['board_code'],
                'change_pct': float(r['change_pct']) if r['change_pct'] else 0,
                'net_inflow': float(r['net_inflow']) if r['net_inflow'] else 0,
                'rank': r['rank_by_flow'],
            }
        return result
    except Exception:
        return {}


# 概念→关键词映射(用于匹配个股所属概念)
CONCEPT_KEYWORDS = {
    '人工智能': ['AI', '人工智能', '大模型', '算力', '智能', 'GPT'],
    '芯片半导体': ['芯片', '半导体', '光刻', '晶圆', 'EDA', '封装'],
    '新能源': ['锂电', '光伏', '储能', '风电', '新能源', '充电桩'],
    '军工': ['军工', '国防', '航空', '航天', '船舶', '导弹'],
    '消费': ['白酒', '食品', '零售', '品牌', '消费'],
    '医药': ['医药', '生物', '创新药', '医疗', 'CXO'],
    '金融': ['银行', '券商', '保险', '证券', '基金'],
    '汽车': ['汽车', '智驾', '自动驾驶', '电动车', '充电'],
    '机器人': ['机器人', '具身智能', '人形', '减速器', '伺服'],
}


def match_stock_to_concepts(stock_name: str, stock_code: str) -> list:
    """将个股名称/代码匹配到可能的概念。"""
    matches = []
    name_lower = stock_name.lower()
    for concept, keywords in CONCEPT_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in name_lower:
                matches.append(concept)
                break
    return matches


def check_resonance(stock_name: str, stock_code: str) -> Optional[Dict]:
    """检查个股是否与当前升温概念共振。
    
    Returns: None(无共振) 或 {concept, reason, bonus_score, detail}
    仅在确认有效共振时返回，不达标不输出。
    """
    # 获取升温概念
    warming = get_warming_concepts(min_days=2)
    hot_boards = get_concept_board_hot(min_flow=1e8)
    
    if not warming and not hot_boards:
        return None
    
    # 匹配个股所属概念
    stock_concepts = match_stock_to_concepts(stock_name, stock_code)
    if not stock_concepts:
        return None
    
    # 检查是否有交集
    best_match = None
    best_score = 0
    
    for concept in stock_concepts:
        # 检查微博/百度热点中是否有相关概念在升温
        for topic, info in warming.items():
            for kw in CONCEPT_KEYWORDS.get(concept, []):
                if kw in topic:
                    score = 5 + min(info['days_active'], 5)  # 5-10分
                    if score > best_score:
                        best_score = score
                        best_match = {
                            'concept': concept,
                            'reason': '%s概念升温(%s,连续%d天)' % (concept, topic, info['days_active']),
                            'bonus_score': score,
                            'source': 'hotspot',
                            'detail': info,
                        }
        
        # 检查概念板块资金流入
        if concept in hot_boards:
            board = hot_boards[concept]
            score = 8 if board['net_inflow'] > 5e8 else 5
            if score > best_score:
                best_score = score
                best_match = {
                    'concept': concept,
                    'reason': '%s板块资金净流入%.1f亿' % (concept, board['net_inflow'] / 1e8),
                    'bonus_score': score,
                    'source': 'concept_board',
                    'detail': board,
                }
    
    return best_match
