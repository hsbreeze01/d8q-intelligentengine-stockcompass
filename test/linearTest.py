
import math
from decimal import Decimal

import pandas as pd
import datetime
from sklearn.linear_model import LinearRegression
import numpy as np



rsi_values = [112.538,111.432,110.286,110.072,112.304 ]
# rsi_values = [x + 5 for x in rsi_values]

# Prepare the data for linear regression
X = np.array(range(len(rsi_values))).reshape(-1, 1)  # X轴的长度必须按照实际rsi的值来定，因为初期的时候会不足某个天数
y = np.array(rsi_values).reshape(-1, 1)  # rsi values as dependent variable

# Perform linear regression
model = LinearRegression()
model.fit(X, y)


# Get the slope (coefficient) of the line
slope = model.coef_[0][0]
print(rsi_values,slope)