#!/usr/bin/env python3
"""兼容入口：缠论扫描已统一到 v3 czsc 引擎。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from chanlun.strategy.czsc_scan import scan


if __name__ == "__main__":
    scan()
