
import akshare as ak
from buy.cache import *
import requests
import json
import pandas as pd

stock_zh_a_hist_df = ak.stock_zh_a_hist(symbol='000651', period="daily", start_date='2024-01-01', end_date='2025-05-26', adjust="qfq")
print("-------------------")
print(stock_zh_a_hist_df)
print("-------------------")


