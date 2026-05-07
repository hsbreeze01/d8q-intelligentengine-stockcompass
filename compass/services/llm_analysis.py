"""StockCompass 双 LLM 综合分析服务

实现 Doubao（结构化分析）+ DeepSeek（深度文章）协同模式，
替代 StockShark 内部的 LLM 分析能力。

职责边界：
- DoubaoLLM: 快速结构化分析 — 评分、信号解读、趋势判断
- DeepSeekLLM: 深度文章生成 — 公众号风格综合分析文章
"""
import json
import logging
from typing import Optional

from compass.services.data_gateway import DataGateway
from compass.llm import DoubaoLLM, DeepSeekLLM

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt 模板
# ---------------------------------------------------------------------------
_DOUBAO_SYSTEM = """你是专业的股票结构化分析师。
根据提供的股票行情数据和资讯，输出 JSON 格式的结构化分析结果。
必须严格输出如下 JSON 格式（不要输出其他内容）：
{
  "overall_score": <0-100 综合评分>,
  "technical_view": "<技术面观点：看多/看空/中性，一句话>",
  "trend_signal": "<趋势信号：多头排列/空头排列/震荡>",
  "buy_signals": <买入信号数量>,
  "sell_signals": <卖出信号数量>,
  "key_levels": {
    "support": "<支撑位价格或描述>",
    "resistance": "<阻力位价格或描述>"
  },
  "short_term_outlook": "<短期展望：3-5句话>",
  "risk_factors": ["<风险因素1>", "<风险因素2>"],
  "news_sentiment": "<消息面情绪：正面/中性/负面>"
}"""

_DEEPSEEK_SYSTEM = """你是专业资深的股票分析师，模仿东北证券付鹏的语气和风格。
根据提供的结构化分析数据和资讯，生成一篇公众号财经分析文章。
输出要求：
1. 吸引人的标题（不要写"标题"二字）
2. 行情概览
3. 技术面分析（趋势、支撑阻力、买卖信号）
4. 消息面解读（相关资讯的关键影响）
5. 综合建议（操作策略和风险提示）
以markdown格式输出，简洁专业，说人话。"""


class DualLLMAnalysisService:
    """双 LLM 综合分析服务 — Doubao 结构化 + DeepSeek 文章"""

    def __init__(
        self,
        gateway: Optional[DataGateway] = None,
        doubao: Optional[DoubaoLLM] = None,
        deepseek: Optional[DeepSeekLLM] = None,
    ):
        self.gateway = gateway or DataGateway()
        self._doubao = doubao
        self._deepseek = deepseek

    @property
    def doubao(self) -> DoubaoLLM:
        if self._doubao is None:
            self._doubao = DoubaoLLM()
        return self._doubao

    @property
    def deepseek(self) -> DeepSeekLLM:
        if self._deepseek is None:
            self._deepseek = DeepSeekLLM()
        return self._deepseek

    def analyze(self, stock_code: str, scope: str = "all") -> dict:
        """执行双 LLM 综合分析。

        Parameters
        ----------
        stock_code : str
            6 位股票代码
        scope : str
            分析范围：all / technical / fundamental

        Returns
        -------
        dict
            {
                "stock_code": str,
                "entity_name": str,
                "structured": dict | None,   # Doubao 结构化分析
                "article": str | None,       # DeepSeek 深度文章
                "data_source": str,          # 数据来源标记
                "error": str | None,         # 错误信息
            }
        """
        # Step 1: 获取原始数据
        try:
            profile = self.gateway.get_stock_profile(stock_code)
        except Exception as e:
            logger.error("获取股票数据失败 %s: %s", stock_code, e)
            return {
                "stock_code": stock_code,
                "entity_name": "",
                "structured": None,
                "article": None,
                "data_source": "compass",
                "error": f"数据获取失败: {e}",
            }

        entity_name = profile.get("entity_name", "")
        quote = profile.get("quote")
        news = profile.get("news", [])

        # Step 2: Doubao 结构化分析
        structured = self._run_structured_analysis(stock_code, entity_name, quote, news)

        # Step 3: DeepSeek 深度文章（基于结构化分析结果 + 原始数据）
        article = self._run_article_generation(
            stock_code, entity_name, quote, news, structured
        )

        return {
            "stock_code": stock_code,
            "entity_name": entity_name,
            "structured": structured,
            "article": article,
            "data_source": "compass",
            "error": None,
        }

    def _run_structured_analysis(
        self,
        stock_code: str,
        entity_name: str,
        quote: Optional[dict],
        news: list,
    ) -> Optional[dict]:
        """使用 Doubao 生成结构化分析结果"""
        # 构建输入数据摘要
        data_summary = {
            "stock_code": stock_code,
            "entity_name": entity_name,
            "quote": quote,
            "news_count": len(news),
            "recent_news": [
                {
                    "title": n.get("title", ""),
                    "sentiment": n.get("sentiment", ""),
                    "publish_time": n.get("publish_time", ""),
                }
                for n in (news or [])[:5]
            ],
        }

        user_content = json.dumps(data_summary, ensure_ascii=False, indent=2)

        try:
            result = self.doubao.standard_request([
                {"role": "system", "content": _DOUBAO_SYSTEM},
                {"role": "user", "content": f"请分析以下股票数据：\n{user_content}"},
            ])

            if result is None:
                logger.warning("Doubao 结构化分析返回空: %s", stock_code)
                return None

            # 尝试解析 JSON（Doubao 可能在 JSON 外面加说明文字）
            return _extract_json(result)

        except Exception as e:
            logger.error("Doubao 结构化分析失败 %s: %s", stock_code, e)
            return None

    def _run_article_generation(
        self,
        stock_code: str,
        entity_name: str,
        quote: Optional[dict],
        news: list,
        structured: Optional[dict],
    ) -> Optional[str]:
        """使用 DeepSeek 生成深度分析文章"""
        # 构建综合数据
        article_data = {
            "stock_code": stock_code,
            "entity_name": entity_name,
            "quote": quote,
            "structured_analysis": structured,
            "recent_news": [
                {
                    "title": n.get("title", ""),
                    "content": (n.get("content", "") or "")[:200],
                    "sentiment": n.get("sentiment", ""),
                }
                for n in (news or [])[:5]
            ],
        }

        user_content = json.dumps(article_data, ensure_ascii=False, indent=2)

        try:
            result = self.deepseek.standard_request([
                {"role": "system", "content": _DEEPSEEK_SYSTEM},
                {"role": "user", "content": f"请根据以下数据生成股票分析文章：\n{user_content}"},
            ])

            if result is None:
                logger.warning("DeepSeek 文章生成返回空: %s", stock_code)
            return result

        except Exception as e:
            logger.error("DeepSeek 文章生成失败 %s: %s", stock_code, e)
            return None


def _extract_json(text: str) -> Optional[dict]:
    """从可能包含额外文本的 LLM 输出中提取 JSON。"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块
    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试找最外层 { }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("无法从 LLM 输出中提取 JSON: %s...", text[:200])
    return None
