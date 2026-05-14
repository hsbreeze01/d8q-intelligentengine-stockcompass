"""LLM 特征提取器 — 三阶段分析编排

阶段 1: Doubao 结构化分析 — 提取事件类型、关键词、驱动因素
阶段 2: 关键词搜索确认 — 通过 DataGateway 搜索资讯，计算消息面确认度
阶段 3: DeepSeek 深度摘要 — 生成可读的事件分析摘要

每个阶段独立 try/except，失败不阻塞后续阶段（graceful degradation）。
"""
import json
import logging
from typing import Optional

from compass.strategy import db
from compass.services.data_gateway import DataGateway
from compass.llm import DoubaoLLM, DeepSeekLLM

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt 模板
# ---------------------------------------------------------------------------

_DOUBAO_SYSTEM = """你是专业的量化策略分析师。
根据提供的群体事件上下文数据，输出 JSON 格式的结构化分析结果。
必须严格输出如下 JSON 格式（不要输出其他内容）：
{
  "event_type": "<事件类型：板块联动/概念爆发/资金异动>",
  "confidence": <0-1 置信度>,
  "keywords": ["<关键词1>", "<关键词2>"],
  "possible_drivers": ["<驱动因素1>", "<驱动因素2>"],
  "related_themes": ["<关联主题1>", "<关联主题2>"]
}"""

_DEEPSEEK_SYSTEM = """你是专业资深的量化策略分析师。
根据提供的群体事件结构化分析和相关资讯，生成一段简洁的事件分析摘要。
输出要求：
1. 事件概述（1-2句）
2. 关键驱动因素分析
3. 消息面确认情况
4. 后续关注要点
以markdown格式输出，简洁专业，说人话。"""


def _extract_json(text: str) -> Optional[dict]:
    """从可能包含额外文本的 LLM 输出中提取 JSON。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("无法从 LLM 输出中提取 JSON: %s...", text[:200])
    return None


class LLMExtractor:
    """LLM 三阶段分析编排器"""

    def __init__(
        self,
        gateway: Optional[DataGateway] = None,
        doubao: Optional[DoubaoLLM] = None,
        deepseek: Optional[DeepSeekLLM] = None,
    ):
        self._gateway = gateway
        self._doubao = doubao
        self._deepseek = deepseek

    @property
    def gateway(self) -> DataGateway:
        if self._gateway is None:
            self._gateway = DataGateway()
        return self._gateway

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

    def analyze_event(self, event_id: int) -> dict:
        """对群体事件执行三阶段 LLM 分析并持久化结果。

        Parameters
        ----------
        event_id : int
            群体事件 ID

        Returns
        -------
        dict
            分析结果，包含 structured / news_matched / llm_summary 等
        """
        # Step 1: 读取事件上下文
        event = db.get_group_event(event_id)
        if not event:
            logger.error("事件 %d 不存在", event_id)
            return {"event_id": event_id, "error": "事件不存在"}

        context = self._build_context(event)

        # 阶段 1: Doubao 结构化分析
        structured = self._run_structured_analysis(context)

        # 阶段 2: 关键词搜索确认
        keywords = []
        if structured and structured.get("keywords"):
            keywords = structured["keywords"]

        news_matched = []
        news_confirm_score = 0.0
        news_confirmed = False

        if keywords:
            news_matched, news_confirm_score = self._run_keyword_search(keywords)
            news_confirmed = news_confirm_score >= 0.3

        # 阶段 3: DeepSeek 深度摘要
        llm_summary = self._run_summary_generation(
            event, structured, news_matched
        )

        # Step 5: 持久化
        try:
            db.update_event_llm_result(
                event_id=event_id,
                llm_keywords=keywords,
                llm_summary=llm_summary,
                llm_confidence=structured.get("confidence") if structured else None,
                llm_drivers=structured.get("possible_drivers") if structured else None,
                llm_related_themes=structured.get("related_themes") if structured else None,
                news_confirmed=news_confirmed,
                news_confirm_score=news_confirm_score,
                news_matched=news_matched,
            )
        except Exception as e:
            logger.error("持久化 LLM 分析结果失败 event=%d: %s", event_id, e)

        return {
            "event_id": event_id,
            "structured": structured,
            "news_matched": news_matched,
            "news_confirm_score": news_confirm_score,
            "news_confirmed": news_confirmed,
            "llm_summary": llm_summary,
        }

    def _build_context(self, event: dict) -> dict:
        """组装事件上下文数据"""
        matched_stocks = event.get("matched_stocks", [])
        stock_codes = []
        stock_names = []
        if isinstance(matched_stocks, list):
            for s in matched_stocks:
                if isinstance(s, str):
                    stock_codes.append(s)
                elif isinstance(s, dict):
                    stock_codes.append(s.get("code", ""))
                    stock_names.append(s.get("name", ""))

        # 获取微观指标数据
        micro = None
        try:
            micro = db.get_event_micro_data(event["id"])
        except Exception as e:
            logger.warning("获取微观数据失败 event=%d: %s", event["id"], e)

        return {
            "event_id": event["id"],
            "dimension": event.get("dimension", ""),
            "dimension_value": event.get("dimension_value", ""),
            "stock_count": event.get("stock_count", 0),
            "avg_buy_star": event.get("avg_buy_star"),
            "max_buy_star": event.get("max_buy_star"),
            "stock_codes": stock_codes,
            "stock_names": stock_names,
            "micro_data": micro,
        }

    def _run_structured_analysis(self, context: dict) -> Optional[dict]:
        """阶段 1: Doubao 结构化分析"""
        try:
            user_content = json.dumps(context, ensure_ascii=False, indent=2)
            result = self.doubao.standard_request([
                {"role": "system", "content": _DOUBAO_SYSTEM},
                {"role": "user", "content": f"请分析以下群体事件数据：\n{user_content}"},
            ])

            if result is None:
                logger.warning("Doubao 结构化分析返回空")
                return None
            return _extract_json(result)

        except Exception as e:
            logger.warning("Doubao 结构化分析失败: %s", e)
            return None

    def _run_keyword_search(
        self, keywords: list
    ) -> tuple:
        """阶段 2: 关键词搜索确认

        Returns
        -------
        tuple[list, float]
            (匹配资讯列表, 确认度评分 0-1)
        """
        try:
            matched = self.gateway.search_news_by_keywords(keywords, limit=20)
            if not matched:
                return [], 0.0

            # 计算确认度：有匹配则按匹配数量/关键词数量计算
            score = min(1.0, len(matched) / max(len(keywords), 1))
            return matched, round(score, 4)

        except Exception as e:
            logger.warning("关键词搜索失败: %s", e)
            return [], 0.0

    def _run_summary_generation(
        self,
        event: dict,
        structured: Optional[dict],
        news_matched: list,
    ) -> Optional[str]:
        """阶段 3: DeepSeek 深度摘要"""
        try:
            data = {
                "dimension": event.get("dimension", ""),
                "dimension_value": event.get("dimension_value", ""),
                "stock_count": event.get("stock_count", 0),
                "avg_buy_star": event.get("avg_buy_star"),
                "structured_analysis": structured,
                "news_count": len(news_matched),
                "news_sample": [
                    {"title": n.get("title", ""), "relevance": n.get("relevance")}
                    for n in (news_matched or [])[:5]
                ],
            }
            user_content = json.dumps(data, ensure_ascii=False, indent=2)

            result = self.deepseek.standard_request([
                {"role": "system", "content": _DEEPSEEK_SYSTEM},
                {"role": "user", "content": f"请根据以下数据生成事件分析摘要：\n{user_content}"},
            ])

            if result is None:
                logger.warning("DeepSeek 摘要生成返回空")
            return result

        except Exception as e:
            logger.warning("DeepSeek 摘要生成失败: %s", e)
            return None
