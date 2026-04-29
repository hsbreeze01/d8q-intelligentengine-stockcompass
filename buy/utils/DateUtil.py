#!/usr/bin/python
# -*- encoding: utf-8 -*-

"""
Description: 
Version: 1.0
Autor: Sam Zhu
Date: 2021-01-02 14:56:09
LastEditTime: 2021-01-02 14:56:09
""" 

import datetime


def dayDif(first,second):
    """
    返回 first-second的天数差 (datetime)
    """
    # print(first,second)
    # print(first.toordinal() ,second.toordinal())
    return first.toordinal() - second.toordinal()

def isSameDay(first,second):
    """
    是否同天 (datetime)
    """
    return first.toordinal() == second.toordinal()

def getDate(datetimeStr):
    dateTime_p = datetime.datetime.strptime(datetimeStr,'%Y-%m-%d %H:%M:%S')
    str_p = datetime.datetime.strftime(dateTime_p,'%Y-%m-%d')
    return str_p

