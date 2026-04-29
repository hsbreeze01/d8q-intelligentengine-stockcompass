#!/usr/bin/python
# -*- coding: UTF-8 -*-

import pymysql

connection = pymysql.connect(host="localhost",user="gamer",passwd="123456",database="stock" )
cursor = connection.cursor()
# some other statements  with the help of cursor

#select records
sql = "select * from param"
result = cursor.execute(sql)

rows = cursor.fetchall()

for row in rows:
    print(row)
    print(row[0])
    print(row[1])
    pass


#delete records
sql = "delete  from param where id = 1"
result = cursor.execute(sql)
print("delete :",result)


#update records
sql = "update param set name ='中文2'  where id = 2"
result = cursor.execute(sql)
print("update :",result)

#update records
#sql = "insert into param (id,name) values(4,'中文3');"
#result = cursor.execute(sql)
#print("insert :",result)

sql = "insert into param (name) values('中文4');"
result = cursor.execute(sql)
print("insert :",result)

for i in range(10):
    print(i)
    pass

sql = "INSERT INTO param (id, name) VALUES (%s, %s)"
val = (100, "sssssss")
cursor.execute(sql, val)
 
 
print(cursor.rowcount, "记录插入成功。")

val = [
  (120, 'https://www.google.com'),
  (121, 'https://www.github.com'),
  (122, 'https://www.taobao.com'),
  (123, 'https://www.stackoverflow.com/')
]


cursor.executemany(sql, val)
print(cursor.rowcount, "记录插入成功。")

connection.commit()
connection.close()
