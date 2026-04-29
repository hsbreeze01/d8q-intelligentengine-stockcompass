"""
StockCompass - 股票量化分析系统

基于 stock2 重构，采用 D8Q 生态统一服务模式。
提供技术指标计算、多策略分析、买卖决策引擎。
"""

__version__ = "0.1.0"
__author__ = "StockCompass Team"

from compass.config import Config
from compass.api.app import create_app

__all__ = ["create_app", "Config", "__version__"]
