"""统一数据网关 — 消费 DataAgent 非结构化资讯 + StockShark 结构化行情"""
import logging
from typing import Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError
import json

logger = logging.getLogger(__name__)

DATAAGENT_BASE = "http://127.0.0.1:8000"
SHARK_BASE = "http://127.0.0.1:5000"
TIMEOUT = 10


def _http_get(url: str, timeout: int = TIMEOUT) -> Optional[dict]:
    """HTTP GET with graceful degradation."""
    try:
        with urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        logger.warning("请求失败 %s: %s", url, e)
        return None


def _http_post(url: str, data: dict, timeout: int = TIMEOUT) -> Optional[dict]:
    """HTTP POST with graceful degradation."""
    try:
        req = Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        logger.warning("请求失败 %s: %s", url, e)
        return None


class DataAgentFetcher:
    """通过 HTTP 调用 DataAgent API (localhost:8000) 获取非结构化资讯"""

    def get_news_by_code(self, stock_code: str, limit: int = 20) -> List[dict]:
        """按股票代码查询相关资讯"""
        data = _http_get(f"{DATAAGENT_BASE}/api/stats")
        if not data:
            return []
        # 通过tracks搜索包含该代码的资讯
        tracks = _http_get(f"{DATAAGENT_BASE}/api/tracks")
        if not tracks:
            return []
        # 搜索所有track的news
        all_news = []
        for track in tracks[:5]:
            resp = _http_get(f"{DATAAGENT_BASE}/api/tracks/{track[id]}/news?limit={limit}")
            if resp and "items" in resp:
                all_news.extend(resp["items"])
        # 过滤包含stock_code的资讯
        return [n for n in all_news if stock_code in (n.get("stock_codes") or "")][:limit]

    def get_news_by_subject(self, subject: str, limit: int = 20) -> List[dict]:
        """按主题查询资讯"""
        tracks = _http_get(f"{DATAAGENT_BASE}/api/tracks")
        if not tracks:
            return []
        for track in tracks:
            if track.get("name") == subject:
                resp = _http_get(f"{DATAAGENT_BASE}/api/tracks/{track[id]}/news?limit={limit}")
                return resp.get("items", []) if resp else []
        return []


class SharkFetcher:
    """通过 HTTP 调用 StockShark API (localhost:5000) 获取结构化行情

    [MIGRATION-StockShark→Compass] 部分端点可能在 Shark 内部使用 LLM。
    Task 3.2 完成后，Compass 将自行完成所有 LLM 分析，Shark 仅提供纯数据。
    """

    def get_quote(self, stock_code: str) -> Optional[dict]:
        """获取股票行情分析数据"""
        resp = _http_post(f"{SHARK_BASE}/api/stock/analyze", {"symbol": stock_code}, timeout=30)
        if resp and resp.get("success"):
            return resp.get("data")
        return None

    def get_stock_map(self, codes: List[str]) -> Dict[str, str]:
        """批量查询 code→name 映射"""
        resp = _http_get(f"{SHARK_BASE}/api/stock/map?codes={','.join(codes)}")
        return resp if isinstance(resp, dict) else {}

    def search_by_keyword(self, keyword: str) -> List[dict]:
        """按关键词搜索股票"""
        resp = _http_get(f"{SHARK_BASE}/api/stock/by-keyword?keyword={keyword}")
        if resp and resp.get("success"):
            return resp.get("data", [])
        return []


class DataGateway:
    """统一数据网关 — 聚合双源数据"""

    def __init__(self):
        self.agent = DataAgentFetcher()
        self.shark = SharkFetcher()

    def get_stock_profile(self, stock_code: str) -> dict:
        """聚合查询：结构化行情 + 非结构化资讯，统一格式输出"""
        quote = self.shark.get_quote(stock_code)
        news = self.agent.get_news_by_code(stock_code)

        # 从行情数据中提取entity_name
        entity_name = ""
        if quote and "stock_name" in quote:
            entity_name = quote["stock_name"]
        elif quote and "name" in quote:
            entity_name = quote["name"]

        return {
            "stock_code": stock_code,
            "entity_name": entity_name,
            "quote": quote,
            "news": news,
            "source": {
                "quote": "shark" if quote else None,
                "news": "dataagent" if news else None,
            },
        }


# 全局单例
gateway = DataGateway()
