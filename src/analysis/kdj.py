#! /usr/bin/python
# -*- coding: utf-8 -*-
#

import os
import sys

import numpy

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
path = os.path.split(rootPath)[0]
sys.path.append(path) # 这句是为了导入_config
sys.path.append(rootPath)

import math
from decimal import Decimal

from .IndicatorAnalysis import Analysis
import pandas as pd
import datetime
from sklearn.linear_model import LinearRegression
import numpy as np

class KDJAnalysis(Analysis):
    """
    KDJ指标分析
    """

    def __init__(self,code):
        Analysis.__init__(self, code)  #继承父类的构造方法，也可以写成：super(Chinese,self).__init__(name,age)
        pass

    def analysis(self):
        """
        分析数据
        """
        pd = self.data()
        
        '''
        if freq[-1] == "m":
            df["datetime"] = df.apply(
                lambda row: int(row["date"].split(" ")[0].replace("-", "")) * 1000000 + int(row["date"].split(" ")[1].replace(":", "")) * 100, axis=1)
        elif freq in ("1d", "W", "M"):
            df["datetime"] = df["date"].apply(lambda x: int(x.replace("-", "")) * 1000000)

        def num_missing(x):
            return sum(x.isnull())

            #应用列:
        print data.apply(num_missing, axis=0)
            #应用行:
        print data.apply(num_missing, axis=1).head()

        def get_title(name):
            title_search = re.search(' ([A-Za-z]+)\.', name)
            # If the title exists, extract and return it.
            if title_search:
                return title_search.group(1)
            return ""

        for dataset in full_data:
            dataset['Title'] = dataset['Name'].apply(get_title)
        '''
        #追加列
        pd["j3d"]=''
        pd["j2d"]=''
        pd["v2d"]=''
        pd["k>d"]=''
        pd["k>x"]=''
        pd["fork"]=''#金叉
        pd["buywin"]=''
        pd["buy_result_1_4"]=''
        pd["buy_result_1_5"]=''
        #522策略
        pd["522j3d"]=''
        pd["522j2d"]=''
        pd["522k>d"]=''
        pd["522k>x"]=''
        pd["522fork"]=''
        pd["522buy_result_1_4"]=''
        pd["522buy_result_1_5"]=''
        
        k = 79#常数
        k522 = 64#常数
        bonus = Decimal(1.01)#盈利百分比

        self.win = {}

        #数据处理 去掉头2天（因为数据要倒回2天） 去掉最后1天（因为盈利要看买入的第2天数据）
        for index in pd.index[2:-1]:
            # print(index,pd.loc[index]["record_time"])
            
            #记录操作结果
            result={}

            #数据整理
            pd.at[index,"j3d"] = (pd.loc[index]["j"] - pd.loc[index-1]["j"]) > (pd.loc[index-1]["j"] - pd.loc[index-2]["j"])
            pd.at[index,"j2d"] = pd.loc[index]["j"] > pd.loc[index-1]["j"]
            pd.at[index,"v2d"] = pd.loc[index]["volume"] > pd.loc[index-1]["volume"]
            pd.at[index,"k>d"] = pd.loc[index]["k"] > pd.loc[index-1]["d"]
            pd.at[index,"k>x"] = pd.loc[index]["k"] > k
            pd.at[index,"fork"] = pd.loc[index-1]["k"] < pd.loc[index-1]["d"] and pd.loc[index]["k"] > pd.loc[index]["d"]
            pd.at[index,"buywin"] = pd.loc[index+1]["high"] > pd.loc[index]["close"]*bonus
            #策略实施统计
            if(pd.loc[index]["j3d"] and pd.loc[index]["j2d"] and pd.loc[index]["v2d"] and pd.loc[index]["k>d"] and pd.loc[index]["k>x"]):
                # print(pd.loc[index]["record_time"],pd.loc[index]["buywin"])
                result['win14'] = pd.loc[index]["buywin"]
                pd.at[index,"buy_result_1_4"] = pd.loc[index]["buywin"]
                pass
            
            if(pd.loc[index]["j3d"] and pd.loc[index]["j2d"] and pd.loc[index]["v2d"] and pd.loc[index]["k>d"] and pd.loc[index]["k>x"] and pd.loc[index]["fork"]):
                # print(pd.loc[index]["record_time"],pd.loc[index]["buywin"])
                result['win15'] = pd.loc[index]["buywin"]
                pd.at[index,"buy_result_1_5"] = pd.loc[index]["buywin"]
                pass
            
            #数据整理
            pd.at[index,"522j3d"] = (pd.loc[index]["j522"] - pd.loc[index-1]["j522"]) > (pd.loc[index-1]["j522"] - pd.loc[index-2]["j522"])
            pd.at[index,"522j2d"] = pd.loc[index]["j522"] > pd.loc[index-1]["j522"]
            pd.at[index,"522k>d"] = pd.loc[index]["k522"] > pd.loc[index-1]["d522"]
            pd.at[index,"522k>x"] = pd.loc[index]["k522"] > k522
            pd.at[index,"522fork"] = pd.loc[index-1]["k522"] < pd.loc[index-1]["d522"] and pd.loc[index]["k522"] > pd.loc[index]["d522"]
            #策略实施统计
            if(pd.loc[index]["522j3d"] and pd.loc[index]["522j2d"] and pd.loc[index]["v2d"] and pd.loc[index]["522k>d"] and pd.loc[index]["522k>x"]):
                # print("                  ",pd.loc[index]["record_time"],pd.loc[index]["buywin"])
                result['win14_522'] = pd.loc[index]["buywin"]
                pd.at[index,"522buy_result_1_4"] = pd.loc[index]["buywin"]
                pass
            
            if(pd.loc[index]["522j3d"] and pd.loc[index]["522j2d"] and pd.loc[index]["v2d"] and pd.loc[index]["522k>d"] and pd.loc[index]["522k>x"] and pd.loc[index]["522fork"]):
                # print("                  ",pd.loc[index]["record_time"],pd.loc[index]["buywin"])
                result['win15_522'] = pd.loc[index]["buywin"]
                pd.at[index,"522buy_result_1_5"] = pd.loc[index]["buywin"]
                pass
            
            if(len(result) > 0):
                result['nexthigh'] = pd.loc[index+1]["high"]
                result['close'] = pd.loc[index]["close"]
                self.win[pd.loc[index]["date"]] = result
            pass

        pass
    
    def saveToDB(self):
        """
        保存数据
        """
        conn = self.get_conn()
        cur = conn.cursor()

        for key in self.win.keys():
            result = self.win[key]
            cur.execute(self.kdjSQL(self.code,key.strftime("%Y-%m-%d"),result.get('nexthigh',-1),result.get('close',-1),result.get('win14',-1),result.get('win15',-1),result.get('win14_522',-1),result.get('win15_522',-1)))
            pass

        conn.commit()
        conn.close()

        self.saveToStrategy()
        pass

    def getSQL(self):#返回的是插入语句
        # sql_temp = '''
        #     SELECT a.stock_code,a.date,a.`open`,a.`close`,a.high,a.low,a.volume ,b.k,b.d,b.j,c.k as k522,c.d as d522,c.j as j522
        #     from stock_data_daily a,indicators_kdj_daily b ,indicators_kdj_daily_522 c
        #     where a.stock_code =
        #     '''+ "\'"+self.code +"\' and a.stock_code = b.stock_code and a.stock_code = c.stock_code  and a.date = b.record_time and a.date = c.record_time order by a.date;"
        # # print(sql_temp)

        sql_temp = '''
            select a.stock_code,a.date,a.open,a.`close`,a.high,a.low,a.volume,b.kdj_k as k,b.kdj_d as d,b.kdj_j as j
            from stock_data_daily a,indicators_daily b where a.stock_code = \'''' + self.code + '''\' and a.stock_code = b.stock_code and a.date = b.date order by a.date;
        '''

        return sql_temp
    
    #提前准备插入语句
    def kdjSQL(self,stock_code,buydate,nexthigh,close,win14,win15,win14_522,win15_522):
        sql_temp = '''
            replace into analysis_kdj (stock_code,buy_date,next_day_high,today_close,win_1_4_result,win_1_5_result,win_1_4_522_result,win_1_5_522_result) values (
            '''+"\'"+stock_code+"\',\'"+buydate+"\',"+str(nexthigh)+","+str(close)+","+str(win14)+","+str(win15)+","+str(win14_522)+","+str(win15_522)+");"
        return sql_temp


    def saveToStrategy(self):
        """
        按照策略执行并存盘
        """
        sql = "select * from analysis_kdj where stock_code = \'"+self.code+"\' order by buy_date"

        conn = self.get_conn()
        cur = conn.cursor()

        cur.execute(sql)
        
        rows = cur.fetchall()

        if(len(rows) < 10):
            print(self.code, len(rows),"exit")
            conn.commit()
            conn.close()
            return

        dataframe_cols=[tuple[0] for tuple in cur.description]#列名和数据库列一致
        df = pd.DataFrame(rows, columns=dataframe_cols)

        #汇总统计数据
        for index in df.index:
            code = df.loc[index]["stock_code"]
            buy_date = df.loc[index]["buy_date"].strftime("%Y-%m-%d")
            high = df.loc[index]["next_day_high"]
            close = df.loc[index]["today_close"]
            buy_price = close
            
            if(df.loc[index]["win_1_4_result"] >= 0):
                result = df.loc[index]["win_1_4_result"]
                win = 0
                lose = 1
                sale_price = 0
                if(result == 1):#失败 不获得分数 获胜 买价*1.01
                    sale_price = buy_price*(1.01)
                    win = 1
                    lose = 0

                cur.execute(self.parseStrategySQL(code,"kdj_14",buy_date,close,high,buy_price,sale_price,win,lose))
            pass

            if(df.loc[index]["win_1_5_result"] >= 0):
                result = df.loc[index]["win_1_5_result"]
                sale_price = 0
                win = 0
                lose = 1
                if(result == 1):#失败 不获得分数 获胜 买价*1.01
                    sale_price = buy_price*1.01
                    win = 1
                    lose = 0

                cur.execute(self.parseStrategySQL(code,"kdj_15",buy_date,close,high,buy_price,sale_price,win,lose))
            pass

            if(df.loc[index]["win_1_4_522_result"] >= 0):
                result = df.loc[index]["win_1_4_522_result"]
                sale_price = 0
                win = 0
                lose = 1
                if(result == 1):#失败 不获得分数 获胜 买价*1.01
                    sale_price = buy_price*(1.01)
                    win = 1
                    lose = 0

                cur.execute(self.parseStrategySQL(code,"kdj_14_522",buy_date,close,high,buy_price,sale_price,win,lose))
            pass

        
            if(df.loc[index]["win_1_5_522_result"] >= 0):
                result = df.loc[index]["win_1_5_522_result"]
                sale_price = 0
                win = 0
                lose = 1
                if(result == 1):#失败 不获得分数 获胜 买价*1.01
                    sale_price = buy_price*1.01
                    win = 1
                    lose = 0

                cur.execute(self.parseStrategySQL(code,"kdj_15_522",buy_date,close,high,buy_price,sale_price,win,lose))
            pass

        conn.commit()
        conn.close()
        pass

    def parseStrategySQL(self,stock_code,strategy,buy_date,today_close,next_day_high,buy_price,sale_price,win,lose):
        sql_temp = '''
        replace into stat_strategy (stock_code,strategy,buy_date,today_close,next_day_high,buy_price,sale_price,win,lose) values (
        '''+"\'"+stock_code+"\',\'"+strategy+"\',\'"+buy_date+"\',"+str(today_close)+","+str(next_day_high)+","+str(buy_price)+","+str(sale_price)+","+str(win)+","+str(lose)+");"
        return sql_temp


# 预测趋势 RSI 的值范围是 -100 到 100，因此趋势按照线性回归预测的最大绝对值是 100
    # 返回的格式 {'rsi_1': -8.539820000000002, 'rsi_2': 0.9152569696969699, 'rsi_3': 0.2926642857142857}
    def predict_linear_trend(self, date=None):
        """
        预测趋势
        rsi1 6日均线 rsi2 12日均线 rsi3 24日均线
        """
        if date is None:#没有参数默认使用当前日期
            date = datetime.date.today().strftime('%Y%m%d')

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%Y%m%d').date()
        
        # print('预测日期',date)
        pd = self.data()
        # print(pd)
        # print('=======')
        #趋势只看k值的
        period = {"k": 5}

        if len(pd) < period['k']:
            print("数据不足")
            return 0
        
        aData = []

        for index in reversed(pd.index):
            #大于分析日期的不进入队列
            if pd.loc[index]["date"] > date:
                continue
            
            aData.append(pd.loc[index])
            #只需要筛选出够用的最长期间的数据即可
            if len(aData) >= period['k']:
                break
        

        # print(aData)
        #根据周期，使用线性回归算法预测回归的趋势
        result = {}
        for key, days in period.items():
            # Extract the last 'days' rsi values
            rsi_values = list(reversed([data[key] for data in aData[:days]]))
            # Prepare the data for linear regression
            X = np.array(range(len(rsi_values))).reshape(-1, 1)  # X轴的长度必须按照实际rsi的值来定，因为初期的时候会不足某个天数
            y = np.array(rsi_values).reshape(-1, 1)  # rsi values as dependent variable

            # Perform linear regression
            model = LinearRegression()
            model.fit(X, y)

            # print(key,y)

            # Get the slope (coefficient) of the line
            slope = model.coef_[0][0]

            result[key] = {'data':y,'slope':slope}
       
        return result, aData[0]["date"].strftime('%Y%m%d')
    

    def determine_strength(self, date=None):
        """
        判定股票多空双方的强弱
        """
        if date is None:#没有参数默认使用当前日期
            date = datetime.date.today().strftime('%Y%m%d')

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%Y%m%d').date()
        
        # print('预测日期',date)
        pd = self.data()
        # print(pd)
        # print('=======')
        #判定rsi指标5日内每天的强弱
        period = {"k": 5}

        if len(pd) < period['k']:
            print("数据不足")
            return 0
        
        aData = []

        for index in reversed(pd.index):
            #大于分析日期的不进入队列
            if pd.loc[index]["date"] > date:
                continue
            
            aData.append(pd.loc[index])
            #只需要筛选出够用的最长期间的数据即可
            if len(aData) >= period['k']:
                break
        # print(aData)
        #根据周期，使用线性回归算法预测回归的趋势
        result = {}
        for key, days in period.items():
            # Extract the last 'days' rsi values
            rsi_values = list(reversed([data[key] for data in aData[:days]]))
            y = []
            # Determine the strength for each RSI value
            for rsi_value in rsi_values:
                if rsi_value > 80:
                    y.append([rsi_value, "超买"])
                elif rsi_value > 50:
                    y.append([rsi_value, "强"])
                elif rsi_value == 50:
                    y.append([rsi_value, "平"])
                elif rsi_value < 20:
                    y.append([rsi_value, "超卖"])
                elif rsi_value < 50:
                    y.append([rsi_value, "弱"])

            result[key] = {'data':y}

       
        return result, aData[0]["date"].strftime('%Y%m%d')
    


    def check_cross(self, date=None):
        """
        判定KDJ的指标是否在KDJ的低位20或者高位80出现金叉或者死叉
        """
        if date is None:  # 没有参数默认使用当前日期
            date = datetime.date.today().strftime('%Y%m%d')

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%Y%m%d').date()

        # print('检查日期', date)
        pd = self.data()
        # print('=======')

        period = {"k": 5, "d": 5}

        if len(pd) < period['d']:
            print("数据不足")
            return 0
        
        aData = []

        for index in reversed(pd.index):
            #大于分析日期的不进入队列
            if pd.loc[index]["date"] > date:
                continue
            
            aData.append(pd.loc[index])
            #只需要筛选出够用的最长期间的数据即可
            if len(aData) >= period['d']:
                break
            pass
            
        
        result = {}

        aData = list(reversed(aData))

        for i in range(1, len(aData)):
            d = aData[i]['date'].strftime('%Y%m%d')
            
            k_today = aData[i]["k"]
            d_today = aData[i]["d"]
            k_yesterday = aData[i - 1]["k"]
            d_yesterday = aData[i - 1]["d"]

            # print(d, k_today, d_today, k_yesterday, d_yesterday)

            if k_today > d_today and k_yesterday <= d_yesterday:
                result[d] = "金叉"
                if k_today < 20:
                    result[d] = "低位金叉"
                elif k_today > 80:
                    result[d] = "高位金叉"

            if k_today < d_today and k_yesterday >= d_yesterday:
                result[d] = "死叉"
                if k_today < 20:
                    result[d] = "低位死叉"
                elif k_today > 80:
                    result[d] = "高位死叉"

        return result
    

    def identify_head_and_bottom(self, date=None):
        """
        根据J值5天的连续值判断头和底部
        """
        if date is None:  # 没有参数默认使用当前日期
            date = datetime.date.today().strftime('%Y%m%d')

        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%Y%m%d').date()

        # print('检查日期', date)
        pd = self.data()
        # print('=======')

        period = {"j": 5}

        if len(pd) < period['j']:
            print("数据不足")
            return 0
        
        aData = []

        for index in reversed(pd.index):
            #大于分析日期的不进入队列
            if pd.loc[index]["date"] > date:
                continue
            
            aData.append(pd.loc[index])
            #只需要筛选出够用的最长期间的数据即可
            if len(aData) >= period['j']:
                break
            pass

        aData = list(reversed(aData))
        
        min_value = min(aData, key=lambda x: x["j"])["j"]
        max_value = max(aData, key=lambda x: x["j"])["j"]
        #连续5天<=10 是底 >=90是顶
        return {'bottom':max_value<=10,'head':min_value>=90},aData[0]["date"].strftime('%Y%m%d')