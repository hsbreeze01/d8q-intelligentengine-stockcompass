# 指标分析
rsi指标是一个预测个股强弱的指标，投资者可以根据它来分析个股。rsi指标三条线分别为：白色线，一般为6天线；黄色线，一般为12天线；紫色线，一般为24天指标的白色线。

当6日、12日rsi指标线在rsi值的50附近向上击穿24日线，此时如果出现了金叉，那么往往是买入信号；当24日rsi指标线下降并跌破rsi值的50平衡线时，就会形成一个死叉，股票价格就会下跌，这是一个很好的卖出信号；当6日和12日RSI指标之前都在50平衡线下方运动，突然同时向上突破该平衡线时，说明多方力量不断增强，已经蓄势待发，股票的价格将继续上升，投资者可以适量的买入；当6日、12日RSI指标线同时上升到80以上，表明此时股价已经达到峰值，股价可能会下跌，投资者可以选择卖出。



## 公式
```python
RSI(N1=6, N2=12, N3=24):
LC = REF(CLOSE, 1)
RSI1 = SMA(MAX(CLOSE - LC, 0), N1, 1) / SMA(ABS(CLOSE - LC), N1, 1) * 100
RSI2 = SMA(MAX(CLOSE - LC, 0), N2, 1) / SMA(ABS(CLOSE - LC), N2, 1) * 100
RSI3 = SMA(MAX(CLOSE - LC, 0), N3, 1) / SMA(ABS(CLOSE - LC), N3, 1) * 100

```


## 策略分析

### 推论
#### 买入原则
1. 6日rsi斜率上升趋势
2. 6日rsi比前日高
3. 量比前日高且低于2倍，防止有疯狂买入后的抛盘
4. 6日rsi高于12日rsi
5. 有金叉出现
6. 6日rsi值高于某个区间 策略1-4为70-90 策略1-5为65-90

### 验证结论
默认参数  6 12 24 比短期 3 6 12测试结果好

## 数据导出
```sql
select a.*,b.* from stock_data_daily a,indicators_rsi_daily b where a.stock_code = 600036 and a.stock_code = b.stock_code and a.record_time = b.record_time 
```





