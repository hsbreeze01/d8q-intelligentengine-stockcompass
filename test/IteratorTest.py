#!/usr/bin/python
# -*- coding: UTF-8 -*-



#for i

for num in range(10):
    
    if num == 5:
        print("break")
        break
    elif num == 3:
        continue

    print(num)
    pass

print("===========================================")

for num in range(2,10):
    print(num)
    

print("===========================================")

fruits = ['banana', 'apple',  'mango']
for index in range(1,len(fruits)):
    print ('当前水果 :', fruits[index])
    if index == 1:
        print("find")
        pass
    else:
        print("not find")
    
    pass

    print("not find 1")



#while i
count = 0
while count < 9:
   print ('The count is:', count)
   count = count + 1

odd = []
even = []
numbers = [1,3,2,4,5,6]

while len(numbers) > 0:
    num = numbers.pop()
    if num%2 == 0:
        even.append(num)
        pass
    else:
        odd.append(num)
        pass
    pass

odd.sort()
for num in odd:
    print("odd",num)
    pass


for num in even:
    print("even",num)
    pass
else:
    print("for end")
    pass

