import os
import sys

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
path = os.path.split(rootPath)[0]
print(curPath,rootPath,path)

sys.path.append(path) # 这句是为了导入_config
sys.path.append(rootPath)

import logging

from stockfetch.db_kdj import *
from stockfetch.db_asi import *
from stockfetch.db_bias import *
from stockfetch.db_boll import *
from stockfetch.db_macd import *
from stockfetch.db_rsi import *
from stockfetch.db_vr import *
from stockfetch.db_wr import *
from stockfetch.db_ma import *
from calc_indicator import *

from src.analysis import *
import json

import pymysql
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from compass.data.database import Database
from buy.Config import taskConfig as config

def test_000001():
    #TODO 遍历所有大盘股票，每天把所有的指标都再计算一次
    calcIndicatorAndSaveToDB("601168","20241216")


# test_000001()

def testAnalysis():
    analysis = ASIAnalysis("600036")
    analysis.action()
    # analysis.executeStrategy()

    analysis = BOLLAnalysis("600036")
    analysis.action()

    analysis = BIASAnalysis("600036")
    analysis.action()
    analysis = RSIAnalysis("600036")
    analysis.action()

    analysis = KDJAnalysis("600036")
    analysis.action()
    
    #统计上述所有策略执行成功的次数
    analysis = StrategyAggregation("600036")
    analysis.action()
    
    pass

# testAnalysis()




def testWin(code,endDate):
    
    #设置数据来源
    set_data_backend(DBDataBackend())

    #获取数据
    T(endDate)#日期必须是开盘日（有数据的那一天）
    S(code)

    print("=======================================")
    print("CLOSE",CLOSE,C[len(CLOSE)-1],len(C))
    print("DATETIME",DATETIME)

    win = 0
    win_pct = 0
    lose = 0
    lose_pct=0
    balance = 0

    for i in range(len(CLOSE)):
        v = CLOSE[i] - OPEN[i]
        v = v/OPEN[i]
        if CLOSE[i] > OPEN[i]:
            win += 1
            win_pct += v
        elif CLOSE[i] < OPEN[i]:
            lose += 1
            lose_pct += v
        else:
            balance += 1

    print(f"当日情况 Win: {win},{win_pct}%, Lose: {lose},{lose_pct}%, Balance: {balance}")

    win = 0
    lose = 0
    balance = 0

    prev_close = CLOSE[0] 
    for i in range(1, len(CLOSE)):
        if CLOSE[i] > prev_close:# 当前和前一天比较
            lose += 1
        elif CLOSE[i] < prev_close:
            win += 1
        else:
            balance += 1
        prev_close = CLOSE[i]

    print(f"与昨日收盘对比 Win: {win}, Lose: {lose}, Balance: {balance}")


# testWin('600036','20240130')


def rsi_trend(code,endDate):
    analysis = RSIAnalysis(code)
    result = analysis.predict_linear_trend(endDate)
    print(result)

def kdj_trend(code,endDate):
    analysis = KDJAnalysis(code)
    result = analysis.predict_linear_trend(endDate)
    print(result)

def ma_trend(code,endDate):
    analysis = MAAnalysis(code)
    result = analysis.predict_linear_trend(endDate)
    print(result)

def macd_trend(code,endDate):
    analysis = MACDAnalysis(code)
    result = analysis.predict_linear_trend(endDate)
    print(result)

def volume_trend(code,endDate):
    analysis = VOLUMEAnalysis(code)
    result = analysis.predict_linear_trend(endDate)
    print(result)

def rsi_determine_strength(code,endDate):
    analysis = RSIAnalysis(code)
    result = analysis.determine_strength(endDate)
    print(result)

def kdj_determine_strength(code,endDate):
    analysis = KDJAnalysis(code)
    result = analysis.determine_strength(endDate)
    print(result)

def macd_determine_strength(code,endDate):
    analysis = MACDAnalysis(code)
    result = analysis.determine_strength(endDate)
    print(result)

def rsi_check_cross(code,endDate):
    analysis = RSIAnalysis(code)
    result = analysis.check_cross(endDate)
    print(result)

def kdj_check_cross(code,endDate):
    analysis = KDJAnalysis(code)
    result = analysis.check_cross(endDate)
    print(result)

def kdj_head_bottom(code,endDate):
    analysis = KDJAnalysis(code)
    result = analysis.identify_head_and_bottom(endDate)
    print(result)

def predict_trade(code,endDate):
    analysis = TradeAnalysis(code)
    result = analysis.predict_trade(endDate)
    print(result)


def _load_combined_data(code):
    sql = (
        "SELECT a.stock_code, a.date, a.open, a.close, a.high, a.low, "
        "a.volume, a.turnover_rate, "
        "b.ma5, b.ma10, b.ma20, b.ma30, b.ma60, "
        "b.boll_up, b.boll_mid, b.boll_low, "
        "b.macd_macd, b.macd_dif, b.macd_dea, "
        "b.rsi_6, b.rsi_12, b.rsi_24, "
        "b.kdj_k, b.kdj_d, b.kdj_j "
        "FROM stock_data_daily a, indicators_daily b "
        "WHERE a.stock_code = %s AND a.stock_code = b.stock_code AND a.date = b.date "
        "ORDER BY a.date"
    )
    with Database() as db:
        count, rows = db.select_many(sql, (code,))
        cols = [t[0] for t in db._cursor.description]
    return pd.DataFrame(rows, columns=cols)


def _make_rsi_df(combined_df):
    df = combined_df[['stock_code', 'date', 'open', 'close', 'high', 'low', 'volume',
                      'ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'rsi_6', 'rsi_12', 'rsi_24']].copy()
    df = df.rename(columns={'rsi_6': 'rsi_1', 'rsi_12': 'rsi_2', 'rsi_24': 'rsi_3'})
    return df


def _make_kdj_df(combined_df):
    df = combined_df[['stock_code', 'date', 'open', 'close', 'high', 'low', 'volume',
                      'kdj_k', 'kdj_d', 'kdj_j']].copy()
    df = df.rename(columns={'kdj_k': 'k', 'kdj_d': 'd', 'kdj_j': 'j'})
    return df


def _make_macd_df(combined_df):
    df = combined_df[['stock_code', 'date', 'open', 'close', 'high', 'low', 'volume',
                      'macd_macd', 'macd_dif', 'macd_dea', 'rsi_6', 'rsi_12', 'rsi_24']].copy()
    df = df.rename(columns={'macd_macd': 'macd', 'macd_dif': 'diff', 'macd_dea': 'dea',
                            'rsi_6': 'rsi_1', 'rsi_12': 'rsi_2', 'rsi_24': 'rsi_3'})
    return df


def _make_ma_df(combined_df):
    df = combined_df[['stock_code', 'date', 'open', 'close', 'high', 'low', 'volume',
                      'ma5', 'ma10', 'ma20', 'ma30', 'ma60',
                      'rsi_6', 'rsi_12', 'rsi_24']].copy()
    df = df.rename(columns={'rsi_6': 'rsi_1', 'rsi_12': 'rsi_2', 'rsi_24': 'rsi_3'})
    return df


def _make_volume_df(combined_df):
    df = combined_df[['stock_code', 'date', 'open', 'close', 'high', 'low', 'volume',
                      'macd_macd', 'macd_dif', 'macd_dea', 'rsi_6', 'rsi_12', 'rsi_24']].copy()
    df = df.rename(columns={'macd_macd': 'macd', 'macd_dif': 'diff', 'macd_dea': 'dea',
                            'rsi_6': 'rsi_1', 'rsi_12': 'rsi_2', 'rsi_24': 'rsi_3'})
    return df


def _make_trade_df(combined_df):
    df = combined_df[['stock_code', 'date', 'open', 'close', 'high', 'low', 'volume',
                      'turnover_rate', 'ma5', 'ma10', 'ma20', 'ma30', 'ma60',
                      'boll_up', 'boll_mid', 'boll_low',
                      'macd_macd', 'rsi_6', 'kdj_k']].copy()
    df = df.rename(columns={'boll_up': 'upper_v', 'boll_mid': 'mid_v', 'boll_low': 'lower_v',
                            'macd_macd': 'macd', 'rsi_6': 'rsi_1', 'kdj_k': 'k'})
    return df

def summery_trade(code,endDate):
    data = {}

    # ONE query instead of 6
    combined_df = _load_combined_data(code)

    # RSI
    analysis = RSIAnalysis(code)
    analysis.set_data(_make_rsi_df(combined_df))
    result = analysis.predict_linear_trend(endDate)
    data['rsi_trend'] = result
    result = analysis.determine_strength(endDate)
    data['rsi_strength'] = result
    result = analysis.check_cross(endDate)
    data['rsi_cross'] = result

    # KDJ
    analysis = KDJAnalysis(code)
    analysis.set_data(_make_kdj_df(combined_df))
    result = analysis.predict_linear_trend(endDate)
    data['kdj_trend'] = result
    result = analysis.determine_strength(endDate)
    data['kdj_strength'] = result
    result = analysis.check_cross(endDate)
    data['kdj_cross'] = result
    result = analysis.identify_head_and_bottom(endDate)
    data['kdj_head_bottom'] = result

    # MACD
    analysis = MACDAnalysis(code)
    analysis.set_data(_make_macd_df(combined_df))
    result = analysis.predict_linear_trend(endDate)
    data['macd_trend'] = result
    result = analysis.determine_strength(endDate)
    data['macd_strength'] = result

    # MA
    analysis = MAAnalysis(code)
    analysis.set_data(_make_ma_df(combined_df))
    result = analysis.predict_linear_trend(endDate)
    data['ma_trend'] = result

    # Volume
    analysis = VOLUMEAnalysis(code)
    analysis.set_data(_make_volume_df(combined_df))
    result = analysis.predict_linear_trend(endDate)
    data['volume_trend'] = result

    # Trade
    analysis = TradeAnalysis(code)
    analysis.set_data(_make_trade_df(combined_df))
    result = analysis.predict_trade(endDate)
    data['trade'] = result

    return data

def summery_trade_json(code,endDate):
    # print('综合分析')
    data = summery_trade(code,endDate)
    # print(data)
    # print('综合分析 end')

    analysis_result = {
        'rsi_analysis_date': data['rsi_trend'][1],
        'rsi1_data': data['rsi_trend'][0]['rsi_1']['data'].tolist(),
        'rsi1_slope': data['rsi_trend'][0]['rsi_1']['slope'],
        'rsi2_slope': data['rsi_trend'][0]['rsi_2']['slope'],
        'rsi3_slope': data['rsi_trend'][0]['rsi_3']['slope'],
        'rsi_strength': json.dumps(data['rsi_strength'][0]['rsi_1']['data'], ensure_ascii=False),
        'rsi_cross': json.dumps(data['rsi_cross'], ensure_ascii=False),
        'kdj_analysis_date': data['kdj_trend'][1],
        'kdj_data': data['kdj_trend'][0]['k']['data'].tolist(),
        'kdj_slope': data['kdj_trend'][0]['k']['slope'],
        'kdj_strength': json.dumps(data['kdj_strength'][0]['k']['data'], ensure_ascii=False),
        'kdj_cross': json.dumps(data['kdj_cross'], ensure_ascii=False),
        'kdj_head_bottom_head': bool(data['kdj_head_bottom'][0]['head']),
        'kdj_head_bottom_bottom': bool(data['kdj_head_bottom'][0]['bottom']),
        'macd_analysis_date': data['macd_trend'][1],
        'macd_data': data['macd_trend'][0]['macd']['data'].tolist(),
        'macd_slope': data['macd_trend'][0]['macd']['slope'],
        'macd_strength': json.dumps(data['macd_strength'][0]['macd']['data'], ensure_ascii=False),
        'ma5_slope': data['ma_trend'][0]['ma5']['slope'],
        'ma10_slope': data['ma_trend'][0]['ma10']['slope'],
        'ma20_slope': data['ma_trend'][0]['ma20']['slope'],
        'volume_slope': data['volume_trend'][0]['volume']['slope'],
        'trade':data['trade']
    }
    
    analysis_result_json = json.dumps(analysis_result, ensure_ascii=False,indent=4)
    # print(analysis_result_json)
    return analysis_result_json



#分析 1.趋势 2.强弱 3.金叉死叉 4.KDJ头底
def buy_advice_v2(data):
    jdata = json.loads(data)
    #记录分析的日期
    result = {}
    adate = jdata['rsi_analysis_date']
    result['date'] = adate
    #趋势分析 MA5要求高的一点，rsi和macd可以降低，但是至少不能太差
    rsi_slope = jdata['rsi1_slope'] > -0.01 # and jdata['rsi2_slope'] > 0 and jdata['rsi3_slope'] > 0
    kdj_slope = jdata['kdj_slope'] > -0.01
    macd_slope = jdata['macd_slope'] > 0


    ma5_slope = jdata['ma5_slope'] > 0.01#如果是>0就作为好趋势，很容易陷入震荡区间买入，这个区间坚决不能买入的,至少用>0.01 1%作为趋势
    ma10_slope = jdata['ma10_slope'] > 0
    ma20_slope = jdata['ma20_slope'] > 0

    up_trends = sum([ma5_slope, rsi_slope, macd_slope])
    down_trends = 3 - up_trends

    #ma5的趋势向下时不建议购入
    result['trend'] = f"RSI Slope: {jdata['rsi1_slope']}, KDJ Slope: {jdata['kdj_slope']}, MACD Slope: {jdata['macd_slope']}, MA5 Slope: {jdata['ma5_slope']}, MA10 Slope: {jdata['ma10_slope']}, MA20 Slope: {jdata['ma20_slope']}"
    if up_trends >=3:#趋势看好
        result['trend_advice'] = "buy"
        result['trend_advice_comments'] = f"Ma5 、rsi 、macd 趋势指标预期向好，是买入时机"
        trend_advice = "buy"
    elif ma5_slope == False :
        result['trend_advice'] = "sell"
        result['trend_advice_comments'] = f"Ma5趋势指标预期向下，建议卖出"
        trend_advice = "sell"
    else:
        result['trend_advice'] = "hold"
        result['trend_advice_comments'] = "趋势不明朗，建议观望"
        trend_advice = "hold"
    
    #强弱分析
    #对rsi,kdj,macd的强弱进行分析，
    #在多方强时推荐买入，超强时如果持有股票推荐卖出，空方强推荐卖出，空方超强时推荐观望转折点买入
    rsi_strength = jdata['rsi1_data'][4][0] > 50
    kdj_strength = jdata['kdj_data'][4][0] > 50
    macd_strength = jdata['macd_data'][4][0] > -0.2

    rsi_super_strength = jdata['rsi1_data'][4][0] > 80
    kdj_super_strength = jdata['kdj_data'][4][0] > 80
    macd_super_strength = jdata['macd_data'][4][0] > 1

    rsi_weak = jdata['rsi1_data'][4][0] <= 50
    kdj_weak = jdata['kdj_data'][4][0] <= 50
    macd_weak = jdata['macd_data'][4][0] <= -0.2

    rsi_super_weak = jdata['rsi1_data'][4][0] < 20
    kdj_super_weak = jdata['kdj_data'][4][0] < 20
    macd_super_weak = jdata['macd_data'][4][0] < -1


    if rsi_super_strength or macd_super_strength:
        strength_advice = "sell"
        result['strength_advice'] = "sell"
        result['strength_advice_comments'] = "多超强-超买，如果持有股票，建议卖出"
    elif rsi_strength and macd_strength:
        strength_advice = "buy"
        result['strength_advice'] = "buy"
        result['strength_advice_comments'] = "多方强，推荐买入"
    elif rsi_super_weak and macd_super_weak:
        strength_advice = "hold"
        result['strength_advice'] = "hold"
        result['strength_advice_comments'] = "空超强-超卖，建议观望转折点"
    elif rsi_weak and macd_weak:
        strength_advice = "sell"
        result['strength_advice'] = "sell"
        result['strength_advice_comments'] = "空方强，推荐卖出"
    else:
        strength_advice = "hold"
        result['strength_advice'] = "hold"
        result['strength_advice_comments'] = "强弱不明朗，建议观望"

    #金叉死叉分析
    rsi_cross = "低位金叉" in jdata['rsi_cross']
    kdj_cross = "低位金叉" in jdata['kdj_cross']
    rsi_dead_cross = "高位死叉" in jdata['rsi_cross']
    kdj_dead_cross = "高位死叉" in jdata['kdj_cross']

    if rsi_cross or kdj_cross:
        cross_advice = "buy"
        result['cross_advice'] = "buy"
        result['cross_advice_comments'] = "低位金叉出现，推荐买入"
    elif rsi_dead_cross or kdj_dead_cross:
        cross_advice = "sell"
        result['cross_advice'] = "sell"
        result['cross_advice_comments'] = "高位死叉出现，推荐卖出"
    else:
        cross_advice = "hold"
        result['cross_advice'] = "hold"
        result['cross_advice_comments'] = "金叉死叉不明朗，建议观望"
    
    #kdj头底分析
    kdj_head = jdata['kdj_head_bottom_head']
    kdj_bottom = jdata['kdj_head_bottom_bottom']
    head_bottom_advice =''

    if kdj_head:
        head_bottom_advice = "sell"
        result['kdj_head_advice'] = "sell"
        result['kdj_head_comments'] = "KDJ头部出现，推荐卖出"
    
    if kdj_bottom:
        head_bottom_advice = "buy"
        result['kdj_bottom_advice'] = "buy"
        result['kdj_bottom_comments'] = "KDJ底部出现，推荐买入"
    
    #分析3天的数据
    trade_records = [record for key, record in sorted(jdata['trade'].items(), reverse=False)]
    # Guard: need at least 3 trade records for 3-day analysis
    if len(trade_records) < 3:
        result["buy_advice"] = "insufficient_data"
        result["buy_star"] = 0
        analysis_result_json = json.dumps(result, ensure_ascii=False, indent=4)
        return 0, 0, analysis_result_json

    record_today = trade_records[-1]
    record_yesterday = trade_records[-2]
    record_before_yesterday = trade_records[-3]




    purchase_signal = False
    # 倒序遍历trade_records，查找是否存在5, 10, 20日的买入信号
    for record in reversed(trade_records[:-1]):
        if record['buy_signal_ma5'] == '买入信号' or record['buy_signal_ma10'] == '买入信号' or record['buy_signal_ma20'] == '买入信号':
            purchase_signal = True
            break

    buy_star = 0 # 按位来看（用int拼装） 低4位置是辅助位0000 高位位买入位 111111 （高位+低位拼装出buystar）
    stars = 0
    # 思路1的代码实现 -- 顺势而为
    # 1.必须多方力量强（超强不买） 2.MA的趋势必须多头向上
    #4.连续2天放量上涨（今天比昨天量高 高0.3 倍至少、活跃度也高、并且不是低开高走 -- 低开有可能回调，也有可能是下跌的开始）
    if (purchase_signal and trend_advice == 'buy' and strength_advice == 'buy' and record_today['volume'] > record_yesterday['volume']*0.8
        and record_today['turnover_rate'] > record_yesterday['turnover_rate']*0.8
        and record_today['open'] >= record_yesterday['open'] 
        and record_today['close'] > record_today['open']):
        # and record_yesterday['close'] > record_yesterday['open']):
        #3.股价收盘在连续3天5日线以上，尤其20日线
        #当必选择条件满足（趋势和状态都好但不一定是低位，买入点尽量低，因此需要让转折点起效果） 和 转折点（股价从m5穿过） 单一满足，是买入信号
        result['summary_advice_1'] = 'MA5 趋势向好 、 多方力量强 、连续2日量价齐升 、今日开盘高于昨日收盘'
        if '支撑' in record_today['judge_ma5']:
            result['summary_advice_1'] = f"连续1日MA5支撑，建议买入 ++++"
            buy_star += 10000
            stars += 1
            if '支撑' in record_yesterday['judge_ma5']:
                result['summary_advice_1'] = f"连续2日MA5支撑，建议买入 ++++"
                buy_star += 100000
                stars += 1
                if '支撑' in record_before_yesterday['judge_ma5']:
                    result['summary_advice_1'] = f"连续3日MA5支撑，建议买入 ++++"
                    buy_star += 1000000
                    stars += 1
        
        result['summary_advice_2'] = ''
        if '支撑' in record_today['judge_ma20']:
            result['summary_advice_2'] += f" 今日有20日支撑"
            buy_star += 20000000
            stars += 1

        # result['summary_advice_3'] = ''
        result['summary_advice_4'] = f"【思路1 顺势而为】辅助判断:"
        if head_bottom_advice == 'buy':
            buy_star += 10
            stars += 1
            result['summary_advice_4'] += f" [KDJ底部出现] "

        if cross_advice == 'buy':
            buy_star += 1
            stars += 1
            result['summary_advice_4'] += f" [底部金叉出现] "
        
        result['summary_advice_4'] += f" 买入推荐指数 {buy_star} 累计好运{stars}"
    pass

    #特殊的判定逻辑，未看股价情况（有可能当日其实是跌的或者有其他情况）
    result['summary_advice_8'] = ''
    if 'buy_signal_boll' in record_today and record_today['buy_signal_boll'] == '买入信号':
        result['summary_advice_8'] = f"boll站上mid,建议买入"
        buy_star += 300000000

    #思路2的代码实现 -- 逆势买入 （依赖人判断，不做自动化买入动作）
    #如果存在十字星是反转信号
    cross = False
    if 'judge_cross' in record_today and '十字星' in record_today['judge_cross']:
        print(f"{adate}: 十字星，反转信号")
        result['cross_change'] = f"{adate}: 十字星，反转信号"
        if buy_star > 0:
            buy_star = -1 #如果存在十字星且在上升通道决策购买，取消购买
        
        cross = True

    result['summary_advice_5'] = ''
    if 'judge_low' in record_today and '创新低' in record_today['judge_low'] and '背离' in record_today['judge_low']:
        # print(f"{adate}: 新低背离，反转信号")
        result['low_change'] = f"{adate}: 新低背离，反转信号"
        if cross:
            result['low_change'] = f"{adate}:新低背离，反转信号，十字星出现，是买入信号" 
            result['summary_advice_5'] = '出现低位十字星，为反转信号，可以考虑买入'
            buy_star += 1000 #作为购买的辅助参数

    if 'judge_high' in record_today and '创新高' in record_today['judge_high'] and '背离' in record_today['judge_high']:
        # print(f"{adate}: 新高背离，反转信号")
        result['high_change'] = f"{adate}: 新高背离，反转信号"
        if cross:
            result['high_change'] = f"{adate}: 新高背离，反转信号，十字星出现，是卖出信号"
            buy_star = -1
    
    #如果close是在boll上轨，是卖出信号，此时不建议买入，因此购买取消
    result['summary_advice_6'] = ''
    if 'sell_signal_boll' in record_today and record_today['sell_signal_boll'] == '卖出信号':
        # print(f"boll上轨 取消交易")
        result['summary_advice_6'] = f"{adate}: boll上轨 取消交易"
        buy_star = -1

    result['summary_advice_7'] = ''
    if 'sell_signal_volume' in record_today and record_today['sell_signal_volume'] == '卖出信号':
        print(f"volume卖出信号 取消交易")
        result['summary_advice_7'] = f"{adate}: volume卖出信号 取消交易"
        buy_star = -1
    
    # 判断上影线和下影线
    upper_shadow = record_today['high'] - max(record_today['open'], record_today['close'])
    lower_shadow = min(record_today['open'], record_today['close']) - record_today['low']
    body_length = abs(record_today['open'] - record_today['close'])

    #涨
    result['summary_advice_9'] = ''
    if record_today['close'] > record_today['open']:
        if lower_shadow > body_length and lower_shadow > upper_shadow:
            result['summary_advice_9'] = f"下影线大于实体和上影线，如果当前价格是近期低位，对价格有支撑，利多"
        #如果上面的条件成立，但是上影线大于实体，仍然按照有风险进行判定
        if upper_shadow > body_length:
            result['summary_advice_9'] = f"上影线大于于实体，如果当前价格是近期高位，会受到空方打压，注意反转信号，可能存在风险"
    else :
        if upper_shadow > body_length:
            result['summary_advice_9'] = f"上影线大于于实体，且下跌，证明空方力量强，建议卖出"


    #遍历trade_records，求ma5, ma10, ma20的平均值，并且根据这3个数据判断当前是否在震荡区间，如果在则不建议买入
    ma5_avg = sum([record['ma5'] for record in trade_records]) / len(trade_records)
    ma10_avg = sum([record['ma10'] for record in trade_records]) / len(trade_records)
    ma20_avg = sum([record['ma20'] for record in trade_records]) / len(trade_records)

    #根据平均值的差距百分比，判断是否在震荡区间，目前暂时判断2%以内的波动为震荡区间
    result['summary_advice_10'] = ''
    if abs((ma5_avg - ma10_avg) / ma5_avg) < 0.01 and abs((ma5_avg - ma20_avg) / ma5_avg) < 0.01:
        result['summary_advice_10'] = '当前处于震荡区间，建议持有或卖出'

    analysis_result_json = json.dumps(result, ensure_ascii=False,indent=4)

    buy_count = buy_star #analysis_result_json.count("买入")
    sell_count = analysis_result_json.count("卖出")

    return buy_count, sell_count, analysis_result_json




if __name__ == '__main__':
    endData = '20240915'
    # rsi_trend('600036',endData)
    # rsi_determine_strength('600036',endData)

    # kdj_trend('600036',endData)
    # kdj_determine_strength('600036',endData)

    # macd_trend('600036',endData)
    # macd_determine_strength('600036',endData)

    # ma_trend('600036',endData)
    
    # volume_trend('600036',endData)

    # rsi_check_cross('600036',endData)
    # kdj_check_cross('600036',endData)

    # #KDJ的头底判定
    # kdj_head_bottom('600036',endData)

    # #交易分析
    # predict_trade('600036',endData)

    # #综合分析
    print('综合分析')
    data = summery_trade_json('600036',endData)
    # print(data)
    result = buy_advice_v2(data)
    print(result)
    print('综合分析 end')


    pass


