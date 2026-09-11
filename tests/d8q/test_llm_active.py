import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from compass.llm import DeepSeekLLM, QwenLLM, active_llm


def test_active_llm_follows_config_active_qwen():
    llm = active_llm()
    assert isinstance(llm, QwenLLM)
    assert "maas.aliyuncs.com" in llm.base_url
    assert llm.model_id == "qwen3.7-plus"
    assert llm.api_key


def test_active_llm_dispatch_deepseek(monkeypatch):
    import compass.llm as llm_mod
    monkeypatch.setattr(
        llm_mod, "get_active_llm_config",
        lambda: {"api_key": "k", "base_url": "https://api.deepseek.com", "model": "deepseek-reasoner"})
    assert isinstance(llm_mod.active_llm(), DeepSeekLLM)


def test_active_llm_dispatch_doubao(monkeypatch):
    pytest.importorskip("volcenginesdkarkruntime")  # CI 不装私有 SDK，跳过
    import compass.llm as llm_mod
    from compass.llm import DoubaoLLM
    monkeypatch.setattr(
        llm_mod, "get_active_llm_config",
        lambda: {"api_key": "k", "base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "bot-x"})
    assert isinstance(llm_mod.active_llm(), DoubaoLLM)


def test_active_llm_rejects_missing_config(monkeypatch):
    import compass.llm as llm_mod
    monkeypatch.setattr(llm_mod, "get_active_llm_config",
                        lambda: {"api_key": "", "base_url": "", "model": ""})
    with pytest.raises(RuntimeError):
        llm_mod.active_llm()
