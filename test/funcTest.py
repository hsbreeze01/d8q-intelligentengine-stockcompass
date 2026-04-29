#!/usr/bin/python
# -*- coding: UTF-8 -*-

import func2Test

print("funcTest=======================================")

def func(a,b,c):
    print(a,b,c)
    return 1

print(func(3,4,5))

def func1():
    print("none")
    pass

func1()

def func2():
    pass

func2()

#可写函数说明
def printinfo( name, age ):
   "打印任何传入的字符串"
   print ("Name: ", name)
   print ("Age ", age)
   return
 
#调用printinfo函数 声明变量可以替代顺序
printinfo( age=50, name="miki" )
#printinfo( name="miki" )


#可写函数说明 同名函数可以重复定义
def printinfo( name, age = 35 ):
   "打印任何传入的字符串"
   print ("Name: ", name)
   print ("Age ", age)
   print("aa")
   return
 
#调用printinfo函数
printinfo( age=50, name="miki" )
printinfo( name="miki" )


# 可写函数说明
def printinfo( arg1, *vartuple ):
   "打印任何传入的参数"
   print ("输出: ")
   print (arg1)
   for var in vartuple:
      print (var)
   return
 
# 调用printinfo 函数
printinfo( 10 )
printinfo( 70, 60, "cc" )

# 可写函数说明
sum = lambda arg1, arg2: arg1 + arg2 #and print(arg1)
 
# 调用sum函数
print ("相加后的值为 : ", sum( 10, 20 ))
print ("相加后的值为 : ", sum( 20, 20 ))


total = 111 # 这是一个全局变量
total2 = 3 # 这是一个全局变量

# 可写函数说明 全局变量局部有引用则默认被替换
def sum( arg1, arg2 ):
   #返回2个参数的和."
   print("total:",total2)
   total = arg1 + arg2 # total在这里是局部变量.
   print ("函数内是局部变量 : ", total)
   return total
 
#调用sum函数
sum( 10, 20 )
print ("函数外是全局变量 : ", total)

total = 222