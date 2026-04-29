#!/usr/bin/python
# -*- coding: UTF-8 -*- 
#import _locale
#_locale._getdefaultlocale = (lambda *args: ['zh_CN', 'gbk'])

 
#str = raw_input("请输入：")
#str = input("请输入：")
str = "fa.txt"
print ("你输入的内容是: ", str)


# 打开一个文件
fo = open(str, "r",encoding="utf-16")
str = fo.read(10)
print ("文件名: ", fo.name)
print ("是否已关闭 : ", fo.closed)
print ("访问模式 : ", fo.mode)
print(str)


def funcname(val):
    """
    docstring
    """
    print(val)
    pass

funcname(1)

func = funcname
func(2)

def func_a(arg_a, func, **kwargs):
    print(arg_a)
    print(func(1,**kwargs))

def func_b(arg_a):
    print(arg_a)
    return 3

if __name__ == '__main__':
    func_a(arg_a='Hello Python', func=func_b)