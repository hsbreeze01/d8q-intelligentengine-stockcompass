"""每日自动评分选股 - 收盘后运行，产出入选名单"""
import json, logging, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from data_fetcher import DataFetcher
from strategy import ShortTermStrategy, MidTermStrategy, compute_technical_signals
from config import SHORT_TERM_POOL, MID_TERM_POOL, SHORT_SCORE_THRESHOLD, MID_SCORE_THRESHOLD

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def run_daily_scoring():
    fetcher = DataFetcher(use_cache=True)
    today = datetime.now().strftime('%Y%m%d')
    start = '20240101'
    
    # 获取北向和融资数据
    north = fetcher.get_north_flow_history(start, today)
    margin = fetcher.get_margin_data()
    north_5d_total = float(north.tail(5).sum()) if len(north) >= 5 else 0

    short_strategy = ShortTermStrategy()
    mid_strategy = MidTermStrategy()
    
    short_selected = []
    mid_selected = []
    
    all_pool = list(set(SHORT_TERM_POOL + MID_TERM_POOL))
    logger.info('Scoring %d stocks...', len(all_pool))
    
    for code in all_pool:
        df = fetcher.get_stock_history(code, start, today)
        if df.empty or len(df) < 20:
            continue
        
        tech = compute_technical_signals(df)
        fin = fetcher.get_financial_data(code)
        fund = fetcher.get_stock_fund_flow(code)
        
        data = {
            **tech,
            'main_net_inflow': fund.get('main_net_inflow', 0),
            'north_rank': 15 if north_5d_total > 0 else 50,
            'margin_increasing': margin.get('margin_increasing', False),
            'profit_growth_positive': fin.get('net_profit_growth', 0) > 0,
            'pe_below_industry': True,
            'market_cap': 100e8,
            'avg_turnover': 3e8,
            'industry_profit_growth': fin.get('net_profit_growth', 0),
            'policy_support': True,
            'net_profit_growth': fin.get('net_profit_growth', 0),
            'roe': fin.get('roe', 0),
            'cash_flow_positive': True,
            'peg': 1.2,
            'pe_percentile': 0.5,
            'dividend_yield': 2.0,
            'is_leader': True,
            'rd_ratio': 6,
        }
        
        # 短期评分
        if code in SHORT_TERM_POOL:
            score = short_strategy.score(data)
            if score >= SHORT_SCORE_THRESHOLD:
                short_selected.append({'code': code, 'score': score})
        
        # 中期评分
        if code in MID_TERM_POOL:
            score = mid_strategy.score(data)
            if score >= MID_SCORE_THRESHOLD:
                mid_selected.append({'code': code, 'score': score})
    
    short_selected.sort(key=lambda x: -x['score'])
    mid_selected.sort(key=lambda x: -x['score'])
    
    result = {
        'date': today,
        'short_term': {'selected': short_selected, 'threshold': SHORT_SCORE_THRESHOLD},
        'mid_term': {'selected': mid_selected, 'threshold': MID_SCORE_THRESHOLD},
        'market_context': {
            'north_5d_flow': north_5d_total,
            'margin_increasing': margin.get('margin_increasing', False),
        }
    }
    
    out = Path(__file__).parent / 'output' / 'daily_score.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    
    logger.info('=== 每日评分完成 ===')
    logger.info('短期入选: %d只 %s', len(short_selected), [s['code'] for s in short_selected[:5]])
    logger.info('中期入选: %d只 %s', len(mid_selected), [s['code'] for s in mid_selected[:5]])
    return result


if __name__ == '__main__':
    run_daily_scoring()
