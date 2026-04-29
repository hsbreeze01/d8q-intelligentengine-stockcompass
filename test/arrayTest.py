#!/usr/bin/python
# -*- coding: UTF-8 -*-



list1 = ['physics',3, 'chemistry', 1997, 2000]
 
print (list1)
del list1[2]
print ("After deleting value at index 2 : ")
print (list1)


list1.append("cccc")
print (list1)
list1 += [3]
print (list1)

print(list1.count(3))

dict = {'Name': 'Zara', 'Age': 7, 'Class': 'First',"School":"md"}
 
del dict['Name']  # 删除键是'Name'的条目
#dict.clear()      # 清空字典所有条目
#del dict          # 删除字典

print ("dict['Age']: ", dict['Age'] )
print ("dict['School']: ", dict['School'])