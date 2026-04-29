# -*- coding: utf-8 -*-
#

from cached_property import cached_property

from .backend import DataBackend
from ..utils import lru_cache, get_str_date_from_int, get_int_date
import pymysql
import pandas as pd

class DBDataBackend(DataBackend):
    skip_suspended = False #关闭安全校验，否则如果最后一条记录的时间不是当天，会被跳过
#   @cached_property 表示只会计算一次，后面会把这个值直接缓存起来，并且访问时要当属性并不能当函数来使用
    def get_conn(self):
        connection = pymysql.connect(host="localhost",user="root",passwd="123456",database="stock" )
        return connection

    @cached_property
    def stock_basics(self):
        print("DBDataBackend.stock_basics")
        # return self.ts.get_stock_basics()
        raise NotImplementedError

    @cached_property
    def code_name_map(self):
        print("DBDataBackend.code_name_map")
        code_name_map = self.stock_basics[["name"]].to_dict()["name"]
        return code_name_map

    def convert_code(self, order_book_id):
        print("DBDataBackend.convert_code")
        return order_book_id.split(".")[0]

    '''
    date     open    close     high      low       volume      code
    0     1990-12-19   113.10   113.10   113.10   113.10       2650.0  sh000001
    1     1990-12-20   113.10   113.50   113.50   112.85       1990.0  sh000001
    2     1990-12-21   113.50   113.50   113.50   113.40       1190.0  sh000001
    3     1990-12-24   113.50   114.00   114.00   113.30       8070.0  sh000001
    4     1990-12-25   114.00   114.10   114.20   114.00       2780.0  sh000001
    6865  2019-09-30  2927.92  2905.19  2936.48  2905.19  116646811.0  sh000001
    6866  2019-10-08  2905.76  2913.57  2933.02  2905.76  125535812.0  sh000001
    6867  2019-10-09  2902.08  2924.86  2924.86  2891.54  130424144.0  sh000001
    6868  2019-10-10  2923.71  2947.71  2949.24  2918.23  134239752.0  sh000001
    6869  2019-10-11  2954.82  2973.66  2980.79  2943.01  161203746.0  sh000001
    '''
    #父类方法
    @lru_cache(maxsize=8192)
    def get_price(self, order_book_id, start, end, freq):
        print("DBDataBackend.get_price",order_book_id,start,end,freq)
        """
        :param order_book_id: e.g. 000002.XSHE
        :param start: 20160101
        :param end: 20160201
        :returns:
        :rtype: numpy.rec.array
        """
        self.code = order_book_id

        start = get_str_date_from_int(start)
        end = get_str_date_from_int(end)
        code = self.convert_code(order_book_id)
        is_index = False
        if ((order_book_id.startswith("0") and order_book_id.endswith(".XSHG")) or
            (order_book_id.startswith("3") and order_book_id.endswith(".XSHE"))
            ):
            is_index = True
        ktype = freq
        if freq[-1] == "m":
            ktype = freq[:-1]
        elif freq == "1d":
            ktype = "D"
        # else W M

        connection = self.get_conn()

        cur = connection.cursor()

        sql_temp="select * from stock_data_daily where stock_code="+"\'"+code+"\' and date >=\'"+start+"\' and date <=\'"+end+"\'  order by date;"
        print(sql_temp)
        cur.execute(sql_temp)
        rows = cur.fetchall()

        connection.commit()
        connection.close()


        # print("000000",[tuple[0] for tuple in cur.description])

        dataframe_cols=[tuple[0] for tuple in cur.description]#列名和数据库列一致


        df = pd.DataFrame(rows, columns=dataframe_cols)
        # df.rename(columns={'record_time':'date'},inplace=True) 
        del df["id"]
        del df["stock_code"]
        del df["turnover"]
        del df["amplitude"]
        del df["change_percentage"]
        del df["change_amount"]
        del df["turnover_rate"]

#   `record_time` date NOT NULL,
#   `open` float unsigned NOT NULL DEFAULT '0',
#   `close` float NOT NULL DEFAULT '0',
#   `high` float NOT NULL DEFAULT '0',
#   `low` float NOT NULL DEFAULT '0',
#   `volume` float NOT NULL DEFAULT '0',


        if freq[-1] == "m":
            df["datetime"] = df.apply(
                lambda row: int(row["date"].split(" ")[0].replace("-", "")) * 1000000 + int(row["date"].split(" ")[1].replace(":", "")) * 100, axis=1)
        elif freq in ("1d", "W", "M"):
            df["datetime"] = df["date"].apply(lambda x: int(x.strftime("%Y-%m-%d").replace("-", "")) * 1000000)

        arr = df.to_records()

        return arr

    #父类方法
    @lru_cache()
    def get_order_book_id_list(self):
        print("DBDataBackend.get_order_book_id_list")
        """获取所有的股票代码列表
        """
        info = self.ts.get_stock_basics()
        code_list = info.index.sort_values().tolist()
        order_book_id_list = [
            (code + ".XSHG" if code.startswith("6") else code + ".XSHE")
            for code in code_list
        ]
        return order_book_id_list
    
    #父类方法
    @lru_cache()
    def get_trading_dates(self, start, end):
        print("DBDataBackend.get_trading_dates")
        """获取所有的交易日

        :param start: 20160101
        :param end: 20160201
        """

        start = get_str_date_from_int(start)
        end = get_str_date_from_int(end)

        if(not hasattr(self,"code")):
            self.code = "000001"

        connection = self.get_conn()

        cur = connection.cursor()

        sql_temp="select date from stock_data_daily where stock_code="+"\'"+self.code+"\' and date >=\'"+start+"\' and date <=\'"+end+"\'  order by date;"
        print(sql_temp)
        cur.execute(sql_temp)
        rows = cur.fetchall()

        connection.commit()
        connection.close()


        trading_dates = []

        dataframe_cols=[tuple[0] for tuple in cur.description]#列名和数据库列一致
        df = pd.DataFrame(rows, columns=dataframe_cols)
        df["datetime"] = df["date"].apply(lambda x: x.strftime("%Y-%m-%d") )
        del df["date"]

        return df.to_records()

    #父类方法
    @lru_cache(maxsize=8192)
    def symbol(self, order_book_id):
        print("DBDataBackend.symbol")
        """获取order_book_id对应的名字
        :param order_book_id str: 股票代码
        :returns: 名字
        :rtype: str
        """
        code = self.convert_code(order_book_id)
        return "{}[{}]".format(order_book_id, self.code_name_map.get(code))

    #父类方法
    @lru_cache(maxsize=8192)
    def get_price_pd(self, order_book_id, start, end, freq):
        print("DBDataBackend.get_price",order_book_id,start,end,freq)
        """
        :param order_book_id: e.g. 000002.XSHE
        :param start: 20160101
        :param end: 20160201
        :returns:
        :rtype: numpy.rec.array
        """
        self.code = order_book_id

        start = get_str_date_from_int(start)
        end = get_str_date_from_int(end)
        code = self.convert_code(order_book_id)
        is_index = False
        if ((order_book_id.startswith("0") and order_book_id.endswith(".XSHG")) or
            (order_book_id.startswith("3") and order_book_id.endswith(".XSHE"))
            ):
            is_index = True
        ktype = freq
        if freq[-1] == "m":
            ktype = freq[:-1]
        elif freq == "1d":
            ktype = "D"
        # else W M

        connection = self.get_conn()

        cur = connection.cursor()

        sql_temp="select * from stock_data_daily where stock_code="+"\'"+code+"\' and date >=\'"+start+"\' and date <=\'"+end+"\' order by date;"
        print(sql_temp)
        cur.execute(sql_temp)
        rows = cur.fetchall()

        connection.commit()
        connection.close()


        # print("000000",[tuple[0] for tuple in cur.description])

        dataframe_cols=[tuple[0] for tuple in cur.description]#列名和数据库列一致


        df = pd.DataFrame(rows, columns=dataframe_cols)
        # df.rename(columns={'record_time':'date'},inplace=True) 
        del df["id"]
        del df["stock_code"]
        del df["turnover"]
        del df["amplitude"]
        del df["change_percentage"]
        del df["change_amount"]
        del df["turnover_rate"]

#   `record_time` date NOT NULL,
#   `open` float unsigned NOT NULL DEFAULT '0',
#   `close` float NOT NULL DEFAULT '0',
#   `high` float NOT NULL DEFAULT '0',
#   `low` float NOT NULL DEFAULT '0',
#   `volume` float NOT NULL DEFAULT '0',


        if freq[-1] == "m":
            df["datetime"] = df.apply(
                lambda row: int(row["date"].split(" ")[0].replace("-", "")) * 1000000 + int(row["date"].split(" ")[1].replace(":", "")) * 100, axis=1)
        elif freq in ("1d", "W", "M"):
            df["datetime"] = df["date"].apply(lambda x: int(x.strftime("%Y-%m-%d").replace("-", "")) * 1000000)

        return df

if __name__ == '__main__':
    print ('作为主程序运行')
else:
    print (__name__,' 初始化')