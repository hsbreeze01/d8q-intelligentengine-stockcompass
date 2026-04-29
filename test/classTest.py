#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import glob

class Test:
    i = 10
    __tv = 100#私有成员

    def __init__(self,a = 311):
        self.data = [a]
        self.__tv = a+1000
        print(self.data)

    def f(self):
        print("aaa")

    def func(self,a):
        return a

    def func2(self,i):
        return i+1

    def getTV(self):
        print("i:",self.i)

        try:
            print("parent.i:",i)
        except Exception as identifier:
            pass
        finally:
            pass
        return self.__tv

x = Test(1111)

print(x.i)
print(x.func2(4))
print(x.func(3))

print("============")
x = Test()


print(x.i)
print(x.func2(4))
print(x.func(3))


print("tv:",x.getTV())

print("============")

class Test2(Test):
    i = 1000

    def __init__(self,a,b):
        print(Test.i)
        self.i = a
        Test.__init__(self,b)
        Test.__tv = a
        print(locals())
        print(Test.i)
    pass

    def func2(self,i):
        return "override"

x = Test2(112,333)

print(x.i)
print(x.func2(4))
print(x.func(3))
print("tv:",x.getTV())
print(super(Test2,x).func2(233))

#print(os.getcwd(),dir(os),help(os))

print(glob.glob('test/*.py'))
