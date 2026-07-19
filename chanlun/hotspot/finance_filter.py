# -*- coding: utf-8 -*-
"""
财经关键词过滤器
对热搜标题做关键词匹配，标记is_finance_related并分类
"""
import re
from typing import List, Dict, Any, Tuple

# ==================== 关键词配置 ====================

# 金融/股市关键词
FINANCE_KEYWORDS = [
    '股市', 'A股', '港股', '美股', '沪指', '深指', '创业板', '科创板', '北交所',
    '牛市', '熊市', '涨停', '跌停', '大盘', '指数', '基金', '券商', '证券',
    '利率', '降准', '降息', '加息', 'LPR', '逆回购', '国债', '债券',
    'GDP', 'CPI', 'PPI', 'PMI', 'M2', '社融', '通胀', '通缩',
    'IPO', '注册制', '退市', '借壳', '重组', '并购', '定增', '增发',
    '市值', '估值', '市盈率', 'PE', 'ROE', '分红', '回购', '减持', '增持',
    '期货', '原油', '黄金', '白银', '外汇', '汇率', '人民币',
    '北向资金', '融资融券', '两融', '杠杆', '爆仓', '主力', '游资',
    '板块', '概念股', '龙头股', '妖股', '题材',
]

# 政策/监管关键词
POLICY_KEYWORDS = [
    '政策', '监管', '央行', '证监会', '银保监', '发改委', '财政部', '国务院',
    '工信部', '商务部', '科技部', '住建部', '两会', '政府工作报告',
    '改革', '开放', '试点', '规划', '意见', '通知', '办法', '条例',
    '反垄断', '合规', '处罚', '罚款', '调查', '审查',
    '十四五', '双循环', '共同富裕', '乡村振兴', '一带一路',
    '自贸区', '大湾区', '京津冀', '长三角', '成渝',
    '房住不炒', '房地产', '限购', '限贷', '棚改', '保障房',
]

# 科技关键词
TECH_KEYWORDS = [
    '新能源', '光伏', '风电', '锂电', '储能', '氢能', '充电桩', '电动车',
    '芯片', '半导体', '光刻机', '晶圆', '封装', 'EDA', 'GPU',
    '人工智能', 'AI', 'ChatGPT', '大模型', '机器学习', '深度学习', 'AIGC',
    '5G', '6G', '物联网', '云计算', '大数据', '区块链', '元宇宙',
    '自动驾驶', '智能驾驶', '车联网', '激光雷达',
    '量子计算', '量子通信', '卫星互联网', '北斗', '航天',
    '生物医药', '创新药', 'CRO', 'CDMO', '基因', '细胞治疗',
    '机器人', '工业互联网', '智能制造', '数字经济', '数字货币',
]

# 消费关键词
CONSUMER_KEYWORDS = [
    '消费', '零售', '电商', '直播带货', '下沉市场',
    '白酒', '医美', '旅游', '免税', '奢侈品',
    '猪肉', '粮食', '食品', '乳制品',
    '汽车', '家电', '服装', '化妆品',
]

# 预编译正则 (用词边界优化匹配)
def _build_pattern(keywords: List[str]) -> re.Pattern:
    escaped = [re.escape(kw) for kw in sorted(keywords, key=len, reverse=True)]
    return re.compile('|'.join(escaped))


_FINANCE_RE = _build_pattern(FINANCE_KEYWORDS)
_POLICY_RE = _build_pattern(POLICY_KEYWORDS)
_TECH_RE = _build_pattern(TECH_KEYWORDS)
_CONSUMER_RE = _build_pattern(CONSUMER_KEYWORDS)


def classify_title(title: str) -> Tuple[bool, str, List[str]]:
    """
    对标题进行分类
    返回: (is_finance_related, category, matched_keywords)
    """
    if not title:
        return False, 'general', []

    matched = []

    # 各类别匹配
    finance_matches = _FINANCE_RE.findall(title)
    policy_matches = _POLICY_RE.findall(title)
    tech_matches = _TECH_RE.findall(title)
    consumer_matches = _CONSUMER_RE.findall(title)

    matched.extend(finance_matches)
    matched.extend(policy_matches)
    matched.extend(tech_matches)
    matched.extend(consumer_matches)

    # 判断是否金融相关(任意类别命中都算)
    is_finance_related = len(matched) > 0

    # 分类优先级: finance > policy > tech > consumer > general
    if finance_matches:
        category = 'finance'
    elif policy_matches:
        category = 'policy'
    elif tech_matches:
        category = 'tech'
    elif consumer_matches:
        category = 'consumer'
    else:
        category = 'general'

    # 去重
    matched = list(dict.fromkeys(matched))

    return is_finance_related, category, matched


def filter_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    对采集数据列表做关键词过滤和分类标记
    为每条数据添加: is_finance_related, category, tags
    """
    for item in items:
        title = item.get('title', '')
        is_finance, category, keywords = classify_title(title)
        item['is_finance_related'] = is_finance
        # 如果source已经是finance类(如概念板块)，保留原category
        if item.get('source', '') in ('eastmoney_concept',):
            item['category'] = 'finance'
            item['is_finance_related'] = True
        else:
            item['category'] = category
        item['tags'] = ','.join(keywords[:10])  # 最多10个标签
    return items


if __name__ == '__main__':
    # 测试
    test_titles = [
        '央行宣布降准0.5个百分点',
        '人工智能概念股集体涨停',
        '某明星官宣离婚',
        'A股三大指数集体高开 新能源板块领涨',
        '国务院印发关于促进消费的意见',
        '特斯拉自动驾驶新进展',
    ]
    for t in test_titles:
        is_fin, cat, kws = classify_title(t)
        print(f"[{cat:10s}] finance={is_fin} | {t} | keywords={kws}")
