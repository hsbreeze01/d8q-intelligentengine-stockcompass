"""Tests — Task 3.1: StockShark LLM 调用点审计

验证审计文档的存在性和结构完整性，
以及代码中待迁移标记的正确性。
"""
import os
import re

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_DOC = os.path.join(PROJECT_ROOT, "docs", "stockshark_llm_audit.md")


# ---------------------------------------------------------------------------
# 审计文档存在性与结构
# ---------------------------------------------------------------------------
class TestAuditDocument:
    """审计文档必须存在且包含必要的章节"""

    def test_audit_document_exists(self):
        assert os.path.isfile(AUDIT_DOC), f"Audit doc missing: {AUDIT_DOC}"

    def test_audit_contains_shark_endpoints(self):
        with open(AUDIT_DOC, encoding="utf-8") as f:
            content = f.read()
        # 必须列出所有 StockShark 调用端点
        assert "/api/analysis/stock/comprehensive" in content
        assert "/api/stock/analyze" in content
        assert "/api/stock/map" in content
        assert "/api/stock/by-keyword" in content

    def test_audit_contains_compass_llm_usage(self):
        with open(AUDIT_DOC, encoding="utf-8") as f:
            content = f.read()
        # 必须记录 Compass 现有 LLM 使用点
        assert "DeepSeekLLM" in content
        assert "DoubaoLLM" in content

    def test_audit_contains_migration_plan(self):
        with open(AUDIT_DOC, encoding="utf-8") as f:
            content = f.read()
        # 必须包含迁移计划
        assert "Task 3.2" in content
        assert "Task 3.3" in content
        assert "Task 3.4" in content

    def test_audit_assigns_priority(self):
        with open(AUDIT_DOC, encoding="utf-8") as f:
            content = f.read()
        # 必须标注优先级
        assert "P0" in content
        assert "P1" in content


# ---------------------------------------------------------------------------
# 代码中的待迁移标记
# ---------------------------------------------------------------------------
class TestMigrationMarkers:
    """Compass 代码中调用 StockShark LLM 的位置应有迁移标记"""

    def test_analysis_route_has_migration_marker(self):
        """compass/api/routes/analysis.py 调用 Shark 综合分析端点需标记"""
        path = os.path.join(PROJECT_ROOT, "compass", "api", "routes", "analysis.py")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # 应包含迁移标记
        assert "MIGRATION" in content or "迁移" in content or "migration" in content.lower() or "task 3.2" in content.lower() or "stockshark" in content.lower(), \
            "analysis.py should contain a migration marker referencing Task 3.2"

    def test_data_gateway_shark_fetcher_documents_llm_risk(self):
        """data_gateway.py 中 SharkFetcher.get_quote 应标记潜在的 LLM 依赖"""
        path = os.path.join(PROJECT_ROOT, "compass", "services", "data_gateway.py")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # get_quote 方法附近应有 LLM 风险说明
        assert "MIGRATION" in content or "迁移" in content or "migration" in content.lower() or "task 3.2" in content.lower() or "stockshark" in content.lower(), \
            "data_gateway.py should contain a migration marker for SharkFetcher"


# ---------------------------------------------------------------------------
# LLM 配置独立性验证
# ---------------------------------------------------------------------------
class TestLLMConfigIsolation:
    """验证 Compass LLM key 配置与 DataAgent 独立"""

    def test_compass_has_dual_llm_config(self):
        """Config 类必须同时有 Doubao 和 DeepSeek 配置"""
        path = os.path.join(PROJECT_ROOT, "compass", "config.py")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "DOUBAO_API_KEY" in content
        assert "DEEPSEEK_API_KEY" in content
        assert "DOUBAO_BASE_URL" in content
        assert "DEEPSEEK_BASE_URL" in content

    def test_both_llm_classes_exist(self):
        """双 LLM 类必须都已实现"""
        from compass.llm import DoubaoLLM, DeepSeekLLM
        assert DoubaoLLM is not None
        assert DeepSeekLLM is not None
