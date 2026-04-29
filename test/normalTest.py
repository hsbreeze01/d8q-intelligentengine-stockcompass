#!/usr/bin/python
# -*- coding: UTF-8 -*-

import random


ls = [1,2,3]
random.shuffle(ls)
print(ls)
ls = ["a",'b',"c"]
print(ls)
ls[1]=3
print(ls)

ls = (1,"a",3)
print(ls)
#ls[1]=3 #error tuple can not assignment
#print(ls)

a = 10
#a > 3 ? print("1"):print(10)

#dict

dict = {}
dict['one'] = "This is one"
dict[2] = "This is two"
 
tinydict = {'name': 'runoob','code':6734, 'dept': 'sales'}
 
 
print( dict['one'])          # 输出键为'one' 的值
print (dict[2]     )         # 输出键为 2 的值
print (tinydict     )        # 输出完整的字典
print (tinydict.keys())      # 输出所有键
print (tinydict.values())    # 输出所有值


print(eval("3+4*3"))

print(chr(97),ord('a'),hex(20),oct(20),int('12'))


#string
str = "abcdefg"
if 'a' in str:
    print("find a")

if 'abd' in str:
    print("find a")

if 'i' in str:
    print("find i")
else:
    print("not find")

if 'h' not in str:
    print("not find h")


print("i is %d c is %c" %(10,'c'))

hi = '''asfas
asdfasdf
sadf'''
print(hi)

num = 10
def func():
#    num = 11 
#    print(num)
    global num #表示后面的数字都是全局的,如果上面注释打开，则后面global声明会失效。默认local的优先级最高
    num+=1110
    print(num)

func()

print(num)
func()
