# -*- coding: utf-8 -*-
"""vendored from czsc.envs (Apache-2.0, github.com/waditu/czsc)"""
import os
valid_true = ['1', 'True', 'true', 'Y', 'y', 'yes', 'Yes', True]

def use_python():
    return os.environ.get('CZSC_USE_PYTHON', False) in valid_true

def get_verbose(verbose=None):
    verbose = verbose if verbose else os.environ.get('czsc_verbose', None)
    return True if verbose in valid_true else False

def get_welcome():
    return os.environ.get('czsc_welcome', '0') in valid_true

def get_min_bi_len(v: int = None) -> int:
    return int(float(v if v else os.environ.get('czsc_min_bi_len', 6)))

def get_max_bi_num(v: int = None) -> int:
    return int(float(v if v else os.environ.get('czsc_max_bi_num', 50)))
