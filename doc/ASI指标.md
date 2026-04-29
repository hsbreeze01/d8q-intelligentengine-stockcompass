# 指标分析
ASI和OBV同样维持“N”字型的波动，并且也以突破或跌破“N”型高、低点，为观察ASI的主要方法。ASI不仅提供辨认股价真实与否的功能？另外也具备了“停损”的仍用，及时地给投资人多一层的保护

## 使用方法：

1．当ASI向下跌破前一次低点时为卖出讯号，
2．当ASI向上突破前一次高点时为买入讯号，
3．价由下往上，欲穿过前一波的高点套牢区时，于接近高点处，尚未确定能否顺利穿越之际。如果ASI领先股价，提早一步，通过相对股价的前一波ASI高点，则次一日之后，可以确定股价必然能顺利突破高点套牢区。
4．股价由上往下，欲穿越前一波低点的密集支撑区时，于接近低点处，尚未确定是否将因失去信心，而跌破支撑之际。如果ASI领先股价，提早一步，跌破相对股价的前一波ASI低点，则次一日之后，可以确定股价将随后跌破价点支撑区。
5．股价走势一波比一波高，而ASI却未相对创新高点形成“牛背离”时，应卖出。
6．股价走势一波比一波低，而ASI却未相对创新低点形成“熊背离”时，应买进。


## 公式
```python

```


## 策略分析

### 推论
#### 买入原则
1. asi是正且高于asit ？
2. asi和asit的差值为放大趋势？
3. asi在某个周期内突破了自己？
4. 前一日收盘站在5日？30日？线上？
5. asi到asit的金叉且绝对值大于10

### 验证结论


## 数据导出
```sql
select a.*,b.*,c.* from stock_data_daily a,indicators_asi_daily b,indicators_ma_daily c where a.stock_code = 600036 and a.stock_code = b.stock_code and a.stock_code = c.stock_code and a.record_time = b.record_time and a.record_time = c.record_time 
```





