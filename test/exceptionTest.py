#!/usr/bin/python
# -*- coding: UTF-8 -*-

try:
    fh = open("testfile", "w")
    fh.write("这是一个测试文件，用于测试异常!!")
except IOError:
    print ("Error: 没有找到文件或读取文件失败")
else:
    print ("内容写入文件成功")
    fh.close()
finally:
    print("END")


class Networkerror(RuntimeError):
    def __init__(self, arg):
        self.args = arg


def f1(i):
    if(i == 2):
        raise IndexError("out",i)

def functionName( level ):
    assert level < 10
    if level < 1:
        raise Exception("Invalid level!", level)
        # 触发异常后，后面的代码就不会再执行
    print("aaaa")

    try:
        f1(level)
        #raise Networkerror("Bad hostname")
    except Networkerror as d1:
        print ("e1.args",d1)
    except IndexError as d1:
        print ("e1.args",d1)
    
    print("end")

functionName(2)

