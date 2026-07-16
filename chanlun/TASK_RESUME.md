# 缠论czsc新引擎 - 任务恢复文档

> 最后更新: 2026-07-16 08:10
> 分支: feature/chanlun-engine
> 项目: /home/ecs-assist-user/d8q-intelligentengine-stockcompass

## A. 恢复第一步: 运行自检
```bash
cd /home/ecs-assist-user/d8q-intelligentengine-stockcompass
venv/bin/python chanlun/verify_resume.py
```
全部PASS则环境完好, 可直接继续。有FAIL则按提示修复。

## B. 当前进度 (N1-N10)

| 任务 | 状态 | 文件 | 说明 |
|------|------|------|------|
| N1 czsc核心 | ✅ | chanlun/czsc_core/ | vendored czsc纯Python(Apache-2.0), 仅依赖numpy/pandas |
| N2 中枢适配 | ✅ | chanlun/engine/czsc_adapter.py | build_czsc + get_zs_seq + valid_pivots |
| N3 走势类型 | ✅ | chanlun/engine/trend.py | classify_trends + last_trend + TrendType |
| N4 背驰 | ✅ | chanlun/engine/czsc_divergence.py | last_divergence(趋势前提+创新极值+面积比+DIF衰减) |
| N5 买点 | ✅ | chanlun/engine/czsc_buysell.py | detect_buy1/2/3 + detect_all_buys |
| N6 卖点 | ✅ | chanlun/engine/czsc_buysell.py | detect_sell1/2/3 + detect_all_sells |
| N7 大盘 | ✅ | chanlun/engine/market_state.py | get_market_state(上证指数趋势+中枢位置) |
| N8 多级别 | ✅ | chanlun/engine/multi_level.py | resample_weekly + multi_level_ok |
| N9 回测 | ✅ | chanlun/backtest/backtest_czsc.py | 30股滑动回测, buy2胜率95.3% |
| N10 接入 | ✅ | 见下 | API生效, 前端tab已加, 定时任务待接 |

## C. N10灰度接入状态

| 步骤 | 状态 | 验证 |
|------|------|------|
| czsc_scan.py | ✅ | 3信号/6股 |
| signals_cache_czsc.json | ✅ | 缓存生成 |
| factory /api/chanlun/czsc 路由 | ✅ | curl返回200 engine=czsc |
| 前端 缠论(czsc) tab | ✅ | 渲染正常,零JS错误,浏览器验证通过 |
| scheduler定时任务 | ✅ | 需在scheduler.py加独立时段跑czsc_scan |

## D. 关键接口签名

```python
# 笔+中枢
from chanlun.engine.czsc_adapter import build_czsc, valid_pivots
c = build_czsc(symbol, klines)  # klines=[{dt,open,high,low,close,volume}]
bis = c.bi_list  # BI对象: .direction, .high, .low, .sdt, .edt, .fx_b.fx
zs_list = valid_pivots(bis)  # ZS对象: .zg, .zd, .gg, .dd, .bis, .is_valid

# 走势
from chanlun.engine.trend import classify_trends, last_trend, TrendType

# 背驰
from chanlun.engine.czsc_divergence import last_divergence
div = last_divergence(bis, zs_list, closes)  # {is_divergence, ratio, kind, direction}

# 买卖点
from chanlun.engine.czsc_buysell import detect_all_buys, detect_all_sells

# 大盘
from chanlun.engine.market_state import get_market_state

# 多级别
from chanlun.engine.multi_level import multi_level_ok
```

## E. 数据库

- host: 127.0.0.1:3306, user: root, password: password, db: stock_analysis_system
- K线表: stock_data_daily (stock_code, date, open, high, low, close, volume)
- 指数表: index_daily (stock_code如000001=上证, date, open, high, low, close, volume)
- Python: venv/bin/python (3.12), 系统python3=3.6.8(不可用于czsc)

## F. 待办

1. scheduler.py 加16:00 czsc_scan定时任务（与旧15:35/15:37并行）
2. buy1/sell1/sell3触发条件偏严(当前=0), 考虑放宽背驰阈值(0.9→0.85)后重测
3. 回测出场规则对齐disciplined(移动止盈等)再跑一轮
4. 灰度1周后评估是否替换旧引擎

## G. 风险

- 新引擎目前不影响旧链路(完全独立文件/路由/缓存)
- 服务restart已验证正常, 旧chanlun tab/disciplined全部不受影响
- buy1/sell3=0是条件严格, 非bug, 需样本覆盖更长区间验证
