#!/usr/bin/python
# -*- coding: UTF-8 -*-

from urllib.request import urlopen


for line in urlopen('http://www.sohu.com'):
    line = line.decode('utf-8')  # Decoding the binary data to text.
    print(line)
    if 'EST' in line or 'EDT' in line:  # look for Eastern Time
        print(line)