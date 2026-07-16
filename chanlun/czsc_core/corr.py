# -*- coding: utf-8 -*-
"""vendored from czsc.utils.analysis.corr (Apache-2.0, github.com/waditu/czsc)"""
from typing import Union
import numpy as np

def single_linear(y: Union[np.ndarray, list], x: Union[np.ndarray, list] = None) -> dict:
    if not x:
        x = list(range(len(y)))
    x_squred_sum = sum([x1 * x1 for x1 in x])
    xy_product_sum = sum([x[i] * y[i] for i in range(len(x))])
    num = len(x); x_sum = sum(x); y_sum = sum(y)
    delta = float(num * x_squred_sum - x_sum * x_sum)
    if delta == 0:
        return {'slope': 0, 'intercept': 0, 'r2': 0}
    y_intercept = (1 / delta) * (x_squred_sum * y_sum - x_sum * xy_product_sum)
    slope = (1 / delta) * (num * xy_product_sum - x_sum * y_sum)
    y_mean = np.mean(y)
    ss_tot = sum([(y1 - y_mean) ** 2 for y1 in y]) + 0.00001
    ss_err = sum([(y[i] - slope * x[i] - y_intercept) ** 2 for i in range(len(x))])
    rsq = 1 - ss_err / ss_tot
    return {'slope': round(slope, 4), 'intercept': round(y_intercept, 4), 'r2': round(rsq, 4)}
