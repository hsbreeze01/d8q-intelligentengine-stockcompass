#!/usr/bin/python
# -*- encoding: utf-8 -*-

"""
Description: 
Version: 1.0
Autor: Sam Zhu
Date: 2020-12-19 23:08:03
LastEditTime: 2020-12-27 17:39:12
""" 


class StockToday(object):


    def __init__(self,code,day):
        self.code = code
        self.day = day
        self.record = []
        self.date = []
        pass
    
    #追加当日明细
    def appendRecord(self,rec):
        if rec['day'] in self.date:
            print("exist date"+day)
            return

        self.date.append(rec['day'])
        self.record.append(rec)


    #计算截止目前当天的开盘等信息
    def calc(self):
        #按照日期排序
        self.record = sorted(self.record, key=lambda x:x['day'], reverse=False)

        self.open = float(self.record[0]['open'])
        self.close = float(self.record[-1]['close'])
        self.high = -1
        self.low = -1
        self.volume = 0

        for rec in self.record:
            self.volume = self.volume + float(rec['volume'])
            if self.high == -1 or self.high < rec['high']:
                self.high =  rec['high']
            
            if self.low == -1 or self.low > rec['low']:
                self.low =  rec['low']

        # print(self)            

    
            


            
            

    
  