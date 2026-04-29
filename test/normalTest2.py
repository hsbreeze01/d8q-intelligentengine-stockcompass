#!/usr/bin/python
# -*- coding: UTF-8 -*-


import funcTest
import package_runoob.p1 as pp
from package_runoob.p2 import p2

#打印文件中所有变量，函数
print(dir(funcTest))
print("============")
print(globals())
print("============")

print(locals())

def func100():
    ccc = 1000
    print("1============")
    print(globals())
    print("============")
    print(locals())

func100()


pp.p1(1)
p2(1)
#reload(math)