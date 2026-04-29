#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
Description: 
Version: 1.0
Autor: Sam Zhu
Date: 2020-10-26 00:48:13
LastEditTime: 2020-12-27 17:43:47
""" 


#!/usr/bin/python
# -*- coding: UTF-8 -*-

import time  # 引入time模块
import calendar
import datetime

ticks = time.time()
print ("当前时间戳为:", ticks)

 
localtime = time.localtime(time.time())
print ("本地时间为 :", localtime)

localtime = time.asctime( time.localtime(time.time()) )
print ("本地时间为 :", localtime)

# 格式化成2016-03-20 11:45:39形式
print (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) )
 
# 格式化成Sat Mar 28 22:24:24 2016形式
print (time.strftime("%a %b %d %H:%M:%S %Y", time.localtime()) )
  
# 将格式字符串转换为时间戳
a = "Sat Mar 28 22:24:24 2016"
print (time.mktime(time.strptime(a,"%a %b %d %H:%M:%S %Y")))


#calendar
cal = calendar.month(2016, 1)
print(cal)

# 字符类型的时间
tss1 = '2013-10-10 23:40:00'
# 转为时间数组
timeArray = time.strptime(tss1, "%Y-%m-%d %H:%M:%S")


print( timeArray)
# timeArray可以调用tm_year等
print (timeArray.tm_yday )  # 2013
# 转为时间戳

dateTime_p = datetime.datetime.strptime(tss1,'%Y-%m-%d %H:%M:%S')
str_p = datetime.datetime.strftime(dateTime_p,'%Y-%m-%d')

print(str_p)
timeStamp = int(time.mktime(timeArray))
print (timeStamp ) # 1381419600




while True:
    print(time.time_ns())
    time.sleep(1)
    pass

