# 指标分析
布林线（Boll）指标是股市技术分析的常用工具之一，通过计算股价的“标准差”，再求股价的“信赖区间”。
该指标在图形上画出三条线，其中上下两条线可以分别看成是股价的压力线和支撑线，而在两条线之间还有一条股价平均线，布林线指标的参数最好设为20。一般来说，股价会运行在压力线和支撑线所形成的通道中。

## 使用方法：

1. 当股价穿越上限压力线（动态上限压力线，静态最上压力线BOLB1）时，卖点信号；
2. 当股价穿越下限支撑线（动态下限支撑线，静态最下支撑线BOLB4）时，买点信号；
3. 当股价由下向上穿越中界限（静态从BOLB4穿越BOLB3）时，为加码信号；
4. 当股价由上向下穿越中界线（静态由BOLB1穿越BOLB2）时，为卖出信号.


## 公式
```python

```


## 策略分析

### 推论
该策略不能直接作为交易依据，需要结合kdj等其他指标看是否能提升成功率

#### 买入原则
1. 盘整期趋势向上时
2. 开口放大超过10% (upper_v-lower_v)/mid_v，且比前日大（放大趋势）
3. 转折点 前一天低于10%，当天高于10%
4. 收盘价> 中值 and 收盘价 < 高值
5. 


### 验证结论


## 数据导出
```sql
select a.*,b.*,c.* from stock_data_daily a,indicators_asi_daily b,indicators_ma_daily c where a.stock_code = 600036 and a.stock_code = b.stock_code and a.stock_code = c.stock_code and a.record_time = b.record_time and a.record_time = c.record_time 
```





