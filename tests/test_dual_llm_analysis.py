"""Tests — Task 3.2: 双 LLM 综合分析服务

覆盖范围：
- DualLLMAnalysisService.analyze() 主流程（mock Gateway + 双 LLM）
- _extract_json 从 LLM 输出中提取 JSON
- /api/analysis/dual-llm 路由端到端测试（mock 依赖）
- DoubaoLLM is_executing 初始化修复
"""
import json
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from compass.services.llm_analysis import DualLLMAnalysisService, _extract_json


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------
class TestExtractJson:
    """JSON 提取工具函数"""

    def test_pure_json(self):
        text = '{"overall_score": 80}'
        assert _extract_json(text) == {"overall_score": 80}

    def test_json_in_markdown_block(self):
        text = '分析结果：\n```json\n{"score": 75}\n```\n以上是分析。'
        assert _extract_json(text) == {"score": 75}

    def test_json_embedded_in_text(self):
        text = '根据分析，结果如下：{"overall_score": 60, "view": "中性"}仅供参考。'
        result = _extract_json(text)
        assert result is not None
        assert result["overall_score"] == 60

    def test_no_json_returns_none(self):
        assert _extract_json("这段文本没有 JSON") is None

    def test_invalid_json_returns_none(self):
        assert _extract_json("{invalid json}") is None


# ---------------------------------------------------------------------------
# DualLLMAnalysisService.analyze — mock 全部依赖
# ---------------------------------------------------------------------------
class TestDualLLMAnalysisService:
    """双 LLM 分析主流程"""

    def _make_service(self, doubao_result, deepseek_result, profile_data):
        """构造 service 并注入 mock"""
        mock_doubao = MagicMock()
        mock_doubao.standard_request.return_value = doubao_result

        mock_deepseek = MagicMock()
        mock_deepseek.standard_request.return_value = deepseek_result

        mock_gateway = MagicMock()
        mock_gateway.get_stock_profile.return_value = profile_data

        return DualLLMAnalysisService(
            gateway=mock_gateway,
            doubao=mock_doubao,
            deepseek=mock_deepseek,
        )

    def test_full_analysis_success(self):
        """正常流程：Gateway 有数据 → Doubao 结构化 → DeepSeek 文章"""
        profile = {
            "stock_code": "600519",
            "entity_name": "贵州茅台",
            "quote": {"open": 1800, "close": 1810, "high": 1820, "low": 1790},
            "news": [{"title": "茅台利好", "sentiment": "positive"}],
        }
        doubao_result = json.dumps({
            "overall_score": 85,
            "technical_view": "看多",
            "trend_signal": "多头排列",
            "buy_signals": 3,
            "sell_signals": 1,
        })
        deepseek_result = "# 贵州茅台分析\n技术面强势..."

        svc = self._make_service(doubao_result, deepseek_result, profile)
        result = svc.analyze("600519")

        assert result["stock_code"] == "600519"
        assert result["entity_name"] == "贵州茅台"
        assert result["structured"] is not None
        assert result["structured"]["overall_score"] == 85
        assert result["article"] == deepseek_result
        assert result["data_source"] == "compass"
        assert result["error"] is None

    def test_analysis_with_gateway_failure(self):
        """Gateway 数据获取失败 → 返回 error"""
        mock_gateway = MagicMock()
        mock_gateway.get_stock_profile.side_effect = Exception("连接失败")

        svc = DualLLMAnalysisService(gateway=mock_gateway)
        result = svc.analyze("600519")

        assert result["error"] is not None
        assert "连接失败" in result["error"]
        assert result["structured"] is None
        assert result["article"] is None

    def test_analysis_doubao_returns_none(self):
        """Doubao 返回 None → structured 为 None，文章仍可生成"""
        profile = {
            "stock_code": "000001",
            "entity_name": "平安银行",
            "quote": {"close": 15},
            "news": [],
        }
        svc = self._make_service(None, "# 分析文章", profile)
        result = svc.analyze("000001")

        assert result["structured"] is None
        assert result["article"] == "# 分析文章"

    def test_analysis_deepseek_returns_none(self):
        """DeepSeek 返回 None → article 为 None，structured 正常"""
        profile = {
            "stock_code": "000001",
            "entity_name": "平安银行",
            "quote": {"close": 15},
            "news": [],
        }
        doubao_result = json.dumps({"overall_score": 70})
        svc = self._make_service(doubao_result, None, profile)
        result = svc.analyze("000001")

        assert result["structured"]["overall_score"] == 70
        assert result["article"] is None

    def test_analysis_empty_news(self):
        """无资讯数据 → 仍能完成分析"""
        profile = {
            "stock_code": "300001",
            "entity_name": "特锐德",
            "quote": {"close": 25},
            "news": [],
        }
        doubao_result = json.dumps({"overall_score": 60})
        svc = self._make_service(doubao_result, "文章", profile)
        result = svc.analyze("300001")

        assert result["structured"]["overall_score"] == 60

    def test_analysis_doubao_invalid_json(self):
        """Doubao 返回非 JSON → structured 为 None"""
        profile = {
            "stock_code": "600036",
            "entity_name": "招商银行",
            "quote": {"close": 35},
            "news": [],
        }
        svc = self._make_service("这不是JSON格式", "文章", profile)
        result = svc.analyze("600036")

        assert result["structured"] is None

    def test_service_lazy_init_llm(self):
        """LLM 实例应延迟初始化"""
        mock_gateway = MagicMock()
        svc = DualLLMAnalysisService(gateway=mock_gateway)
        # 属性访问应触发初始化（会因无真实 key 失败，此处仅验证 mock 路径）
        mock_doubao = MagicMock()
        svc._doubao = mock_doubao
        assert svc.doubao is mock_doubao

        mock_deepseek = MagicMock()
        svc._deepseek = mock_deepseek
        assert svc.deepseek is mock_deepseek


# ---------------------------------------------------------------------------
# /api/analysis/dual-llm 路由测试
# ---------------------------------------------------------------------------
class TestDualLLMRoute:
    """API 端到端测试"""

    @pytest.fixture
    def client(self):
        from compass.api.app import create_app
        app = create_app("testing")
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_missing_stock_code(self, client):
        """缺少 stock_code → 400"""
        resp = client.post("/api/analysis/dual-llm",
                           data=json.dumps({}),
                           content_type="application/json")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    @patch("compass.services.llm_analysis.DualLLMAnalysisService.analyze")
    def test_successful_analysis(self, mock_analyze, client):
        """正常分析 → 200"""
        mock_analyze.return_value = {
            "stock_code": "600519",
            "entity_name": "贵州茅台",
            "structured": {"overall_score": 85},
            "article": "# 分析文章",
            "data_source": "compass",
            "error": None,
        }
        resp = client.post("/api/analysis/dual-llm",
                           data=json.dumps({"stock_code": "600519"}),
                           content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["stock_code"] == "600519"
        assert data["structured"]["overall_score"] == 85
        assert data["data_source"] == "compass"

    @patch("compass.services.llm_analysis.DualLLMAnalysisService.analyze")
    def test_analysis_with_error(self, mock_analyze, client):
        """分析返回 error → 500"""
        mock_analyze.return_value = {
            "stock_code": "000001",
            "entity_name": "",
            "structured": None,
            "article": None,
            "data_source": "compass",
            "error": "数据获取失败",
        }
        resp = client.post("/api/analysis/dual-llm",
                           data=json.dumps({"stock_code": "000001"}),
                           content_type="application/json")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# DoubaoLLM is_executing 初始化修复验证
# ---------------------------------------------------------------------------
class TestDoubaoLLMInit:
    """DoubaoLLM.is_executing 必须在 __init__ 中初始化"""

    @patch("compass.llm.doubao.Ark")
    def test_is_executing_initialized(self, MockArk):
        from compass.llm.doubao import DoubaoLLM
        llm = DoubaoLLM(api_key="test", base_url="http://test", model_id="test")
        assert hasattr(llm, "is_executing")
        assert llm.is_executing is False
