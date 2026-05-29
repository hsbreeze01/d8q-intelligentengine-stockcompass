# 技术指标计算公式参考

> 版本：1.0
> 更新日期：2026-05-29
> 计算引擎：StockShark (49.234.48.221)
> 核心库：TA-Lib (talib)
> 数据源：stock_data_daily -> indicators_daily (3.1M行, 5200股, 578天)

---

## 一、已启用的指标（当前生产环境）

以下指标每日由 StockShark Daemon 计算并写入 `indicators_daily` 表。

### 1.1 MA — 移动平均线

**计算库**：`talib.MA(close, timeperiod=N)`

| 指标 | 周期 | 公式 | 说明 |
|------|------|------|------|
| `ma5` | 5 日 | `MA(close, 5)` | 5 日均线 |
| `ma10` | 10 日 | `MA(close, 10)` | 10 日均线 |
| `ma20` | 20 日 | `MA(close, 20)` | 20 日均线（布林带中轨） |
| `ma30` | 30 日 | `MA(close, 30)` | 30 日均线 |
| `ma60` | 60 日 | `MA(close, 60)` | 60 日均线（季线） |

**公式**：

```
MA(N) = SUM(close_i, i=1..N) / N
```

**应用**：
- 均线多头排列：MA5 > MA10 > MA20 > MA60（强势上涨信号）
- 均线空头排列：MA5 < MA10 < MA20 < MA60（下跌趋势）
- 金叉：短期均线上穿长期均线
- 死叉：短期均线下穿长期均线

### 1.2 MACD — 指数平滑异同移动平均线

**计算库**：`talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)`

**参数**：
- 快线周期：12
- 慢线周期：26
- 信号线周期：9

**公式**：

```
EMA(N) = close * k + EMA_prev * (1 - k)    其中 k = 2 / (N + 1)

DIF (macd_dif) = EMA(12) - EMA(26)
DEA (macd_dea) = EMA(9) of DIF
MACD (macd_macd) = (DIF - DEA) * 2
```

**输出字段**：

| 字段 | 说明 |
|------|------|
| `macd_dif` | 快线与慢线差值 |
| `macd_dea` | DIF 的 9 日 EMA |
| `macd_macd` | 柱状图 = (DIF - DEA) * 2 |

**注意**：代码中 `macd_macd = (DIF - DEA) * 2`，符合国内股票软件的显示习惯。

**应用**：
- 金叉：DIF 上穿 DEA（看涨信号）
- 死叉：DIF 下穿 DEA（看跌信号）
- 零轴上方：多头市场
- 零轴下方：空头市场
- 顶背离：价格创新高，MACD 不创新高（看跌）
- 底背离：价格创新低，MACD 不创新低（看涨）

### 1.3 KDJ — 随机指标

**计算库**：`talib.STOCH(high, low, close, fastk_period=9, slowk_period=5, slowd_period=5)`

**参数**：
- fastk_period = 9
- slowk_period = 5, slowk_matype = 1 (SMA)
- slowd_period = 5, slowd_matype = 1 (SMA)

**公式**：

```
RSV = (close - LLV(low, 9)) / (HHV(high, 9) - LLV(low, 9)) * 100

K (kdjk) = SMA(RSV, 5)       // 对 RSV 做 5 日简单移动平均
D (kdjd) = SMA(K, 5)          // 对 K 做 5 日简单移动平均
J (kdjj) = 3 * K - 2 * D      // J 线
```

**输出字段**：

| 字段 | 范围 | 说明 |
|------|------|------|
| `kdjk` | 0-100（可超出） | K 线 |
| `kdjd` | 0-100（可超出） | D 线 |
| `kdjj` | 可超出 0-100 | J 线（敏感度最高） |

**应用**：
- 超买：K > 80, D > 80（卖出信号）
- 超卖：K < 20, D < 20（买入信号）
- J > 100：极度超买
- J < 0：极度超卖

### 1.4 RSI — 相对强弱指标

**计算库**：`talib.RSI(close, timeperiod=N)`

**输出字段**：

| 字段 | 周期 | 说明 |
|------|------|------|
| `rsi_6` | 6 日 | 短期 RSI（最敏感） |
| `rsi_12` | 12 日 | 中期 RSI |
| `rsi_24` | 24 日 | 长期 RSI（最平滑） |

**公式**：

```
delta = close_today - close_yesterday
gain = SMA(max(delta, 0), N)
loss = SMA(abs(min(delta, 0)), N)
RS = gain / loss
RSI = 100 - 100 / (1 + RS)
```

**应用**：
- 超买：RSI > 70（卖出信号）
- 超卖：RSI < 30（买入信号）
- RSI_6 最敏感，适合短线
- RSI_24 最平滑，适合趋势判断
- 背离判断与 MACD 类似

### 1.5 BOLL — 布林带

**计算库**：`talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)`

**参数**：
- 周期：20
- 标准差倍数：上轨 2 倍，下轨 2 倍
- matype = 0 (SMA)

**公式**：

```
中轨 (boll_mid) = MA(close, 20)
上轨 (boll_up)  = 中轨 + 2 * STD(close, 20)
下轨 (boll_low) = 中轨 - 2 * STD(close, 20)
```

**输出字段**：

| 字段 | 说明 |
|------|------|
| `boll_up` | 上轨 |
| `boll_mid` | 中轨（= MA20） |
| `boll_low` | 下轨 |

**应用**：
- 价格突破上轨：超买或突破信号
- 价格跌破下轨：超卖或破位信号
- 布林带收窄（squeeze）：变盘前兆
- 布林带开口放大：趋势加速

---

## 二、辅助指标字段

indicators_daily 表中除上述技术指标外，还包含以下辅助字段：

| 字段 | 说明 | 数据来源 |
|------|------|----------|
| `volume_ratio` | 量比 | stock_data_daily 计算 |
| `amplitude` | 振幅 = (high - low) / pre_close * 100 | stock_data_daily |
| `change_pct` | 涨跌幅 = (close - pre_close) / pre_close * 100 | stock_data_daily |
| `turnover_rate` | 换手率 | stock_data_daily |
| `stock_code` | 股票代码 | — |
| `date` | 交易日期 | — |

---

## 三、投资评分公式（当前版本）

**文件**：`stockshark/data/data_processor.py`（47 上当前版本，硬编码评分）

> **注意**：47 上运行的是旧版硬编码评分，报告中的 4 因子真实评分仅存在于 49 上（未提交）。

### 3.1 当前评分逻辑（旧版，47 上运行中）

```
总分 = 估值分 + 成长分 + 技术分 + 行业分
```

| 因子 | 权重 | 当前实现 | 实际数据源 |
|------|------|----------|-----------|
| 估值 | 30 分 | PE 区间评分 | akshare `pe_ttm` |
| 成长 | 30 分 | **固定 15 分**（硬编码） | 无 |
| 技术 | 20 分 | **固定 10 分**（硬编码） | 无 |
| 行业 | 20 分 | **固定 10 分**（有行业则给分） | 无 |

**评级**：

| 总分 | 评级 |
|------|------|
| >= 80 | 优秀 |
| >= 60 | 良好 |
| >= 40 | 一般 |
| < 40 | 较差 |

**估值评分规则**：

| PE 范围 | 得分 | 判定 |
|---------|------|------|
| 0 < PE < 10 | 30 | 低估值 |
| 10 <= PE < 20 | 20 | 合理 |
| 20 <= PE < 30 | 10 | 偏高 |
| PE >= 30 或 PE <= 0 | 0 | 高估或亏损 |

### 3.2 设计中的评分逻辑（新版，仅存在于变更报告中）

```
总分 = 估值(30) + 成长(30) + 技术(20) + 行业(20)
```

| 因子 | 权重 | 数据源 | 计算逻辑 |
|------|------|--------|----------|
| **估值** | 30 分 | PE/PB | PE 区间评分（0-8 < 15 倍，8-15 为 15-25 倍，15-25 为 25-40 倍）+ PB 破净加分 |
| **成长** | 30 分 | ROE/营收增长 | ROE 分级 + 营收增长加分/扣分 |
| **技术** | 20 分 | RSI/KDJ/MACD/MA | RSI 区间 + KDJ 超买超卖 + MACD 金叉/死叉 + 均线排列 |
| **行业** | 20 分 | — | 基础分 10（待接入行业数据） |

**成长因子 ROE 分级**：

| ROE 范围 | 得分 |
|----------|------|
| < 5% | 0 |
| 5%-10% | 5 |
| 10%-15% | 10 |
| 15%-20% | 15 |
| 20%-25% | 20 |
| >= 25% | 25 |

### 3.3 风险评分（当前版本）

```
风险等级 = 根据 risk_factors 数量判定
```

| 风险因素 | 触发条件 |
|----------|----------|
| 估值风险 | PE > 50 |
| 波动率风险 | abs(涨跌幅) > 7% |
| 行业风险 | 有行业字段则标记（占位） |

| 风险因素数量 | 风险等级 |
|-------------|----------|
| 0 | low |
| 1-2 | medium |
| >= 3 | high |

### 3.4 设计中的风险评分（新版，仅存在于变更报告中）

多维度综合判定：

| 维度 | 数据源 | 判定逻辑 |
|------|--------|----------|
| 估值风险 | PE | PE > 60 → high，PE > 40 → medium |
| 波动率 | change_pct | abs > 5% → high，abs > 3% → medium |
| 技术面 | RSI/KDJ | RSI > 80 或 KDJ > 90 → high |
| 财务 | ROE | ROE < 5% → high，ROE < 10% → medium |
| 行业 | — | 默认 medium |

输出：`low` / `medium` / `high` / `very_high`

---

## 四、StockShark DataProcessor 辅助计算

**文件**：`stockshark/data/data_processor.py`

以下公式在 `DataProcessor.calculate_technical_indicators()` 中，用于实时分析（非 indicators_daily 持久化流程）：

### 4.1 涨跌幅

```
change_pct = (close - open) / open * 100
```

### 4.2 成交量均线

```
volume_ma5 = MA(volume, 5)
volume_ma10 = MA(volume, 10)
```

### 4.3 MACD（DataProcessor 版本）

```
ema12 = EWM(close, span=12)
ema26 = EWM(close, span=26)
dif = ema12 - ema26
dea = EWM(dif, span=9)
macd = (dif - dea) * 2
```

> 与 TA-Lib 版本参数一致，但使用 pandas `ewm()` 计算。

### 4.4 RSI（DataProcessor 版本）

```
delta = close.diff()
gain = MA(delta.where(delta > 0, 0), window=14)
loss = MA(-delta.where(delta < 0, 0), window=14)
rs = gain / loss
rsi = 100 - 100 / (1 + rs)
```

> 此版本固定 14 日周期，indicators_daily 中使用 6/12/24 三个周期。

---

## 五、已禁用的指标（代码中已实现但未启用）

以下指标在 `stockdata/calc_indicator.py` 中有完整实现（注释状态），可在需要时启用：

| 指标 | TA-Lib 函数 | 说明 |
|------|-------------|------|
| TRIX | `tl.TRIX(close, 12)` | 三重指数平滑移动平均 |
| CR | 手动计算 | 能量指标（中间价） |
| ATR | `tl.ATR(high, low, close, 14)` | 真实波动幅度均值 |
| DMI/PDI/MDI/ADX/ADXR | `tl.PLUS_DI/MINUS_DI/ADX/ADXR` | 趋向指标 |
| WR | `tl.WILLR(high, low, close, N)` | 威廉指标（6/10/14日） |
| CCI | `tl.CCI(high, low, close, N)` | 商品通道指标 |
| DMA | `MA(10) - MA(50)` | 平行线差指标 |
| TEMA | `tl.TEMA(close, 14)` | 三重指数平滑均线 |
| MFI | `tl.MFI(high, low, close, volume, 14)` | 资金流量指标 |
| VWMA | `SUM(amount, 14) / SUM(volume, 14)` | 成交量加权均价 |
| PPO | `tl.PPO(close, 12, 26)` | 价格震荡百分比 |
| StochRSI | 手动计算 | RSI 的随机指标 |
| Supertrend | 手动计算（ATR * 3） | 超级趋势线 |
| ROC | `tl.ROC(close, 12)` | 变动率指标 |
| OBV | `tl.OBV(close, volume)` | 能量潮指标 |
| SAR | `tl.SAR(high, low)` | 抛物线指标 |
| BIAS | `(close - MA) / MA * 100` | 乖离率 |
| EMV | 手动计算 | 简易波动指标 |
| VHF | 手动计算 | 垂直水平滤波器 |

---

## 六、indicators_daily 表结构（策略扫描数据源）

| 列 | 类型 | 说明 | 来源 |
|----|------|------|------|
| stock_code | varchar(20) | 股票代码 | — |
| date | date | 交易日期 | — |
| ma5, ma10, ma20, ma30, ma60 | float | 均线 | TA-Lib MA |
| macd_dif, macd_dea, macd_macd | float | MACD | TA-Lib MACD |
| kdj_k, kdj_d, kdj_j | float | KDJ | TA-Lib STOCH + 计算 |
| rsi_6, rsi_12, rsi_24 | float | RSI | TA-Lib RSI |
| boll_up, boll_mid, boll_low | float | 布林带 | TA-Lib BBANDS |
| volume_ratio | float | 量比 | stock_data_daily |
| amplitude | float | 振幅 | stock_data_daily |
| change_pct | float | 涨跌幅 | stock_data_daily |
| turnover_rate | float | 换手率 | stock_data_daily |

**数据规模**：约 3,107,679 行（5200 股 x 578 交易日）

---

## 七、策略条件可用的指标名

Scanner 的 `_eval_condition` 直接从 `indicators_daily` 行数据中取字段值，因此条件中的 `indicator` 必须是表的列名：

**技术指标列**：
- `ma5`, `ma10`, `ma20`, `ma30`, `ma60`
- `macd_dif`, `macd_dea`, `macd_macd`
- `kdj_k`, `kdj_d`, `kdj_j`
- `rsi_6`, `rsi_12`, `rsi_24`
- `boll_up`, `boll_mid`, `boll_low`

**辅助指标列**：
- `volume_ratio`
- `amplitude`
- `change_pct`
- `turnover_rate`

**策略示例**：

```json
{
  "name": "RSI超卖反弹",
  "conditions": [
    {"indicator": "rsi_6", "operator": "<", "value": 30},
    {"indicator": "kdj_k", "operator": "<", "value": 20}
  ],
  "signal_logic": "AND"
}
```

```json
{
  "name": "底部共振",
  "conditions": [
    {"indicator": "rsi_6", "operator": "<", "value": 15},
    {"indicator": "kdj_k", "operator": "<", "value": 15}
  ],
  "signal_logic": "SCORING",
  "scoring_threshold": 2
}
```

```json
{
  "name": "放量突破",
  "conditions": [
    {"indicator": "volume_ratio", "operator": ">", "value": 2},
    {"indicator": "kdj_k", "operator": ">", "value": 0}
  ],
  "signal_logic": "AND"
}
```

```json
{
  "name": "MACD金叉",
  "conditions": [
    {"indicator": "macd_dif", "operator": "cross_above", "value": 0}
  ],
  "signal_logic": "AND"
}
```
