#!/usr/bin/env python3
"""CLI: 输出单股czsc详情JSON到stdout. 注意先import标准库再改path避免types冲突"""
import sys
import json
import os
# 标准库已加载完毕，现在安全地加入项目路径
sys.path.insert(0, '/home/ecs-assist-user/d8q-intelligentengine-stockcompass')
from chanlun.engine.czsc_detail import get_stock_detail
code = sys.argv[1] if len(sys.argv) > 1 else '600030'
result = get_stock_detail(code)
print(json.dumps(result, ensure_ascii=False, default=str))
