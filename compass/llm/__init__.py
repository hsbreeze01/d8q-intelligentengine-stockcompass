from compass.llm.base import LLM
from compass.llm.doubao import DoubaoLLM
from compass.llm.deepseek import DeepSeekLLM
from compass.llm.qwen import QwenLLM
from compass.config import get_active_llm_config


def active_llm() -> LLM:
    """按 config/llm_providers.json 的 active provider 实例化对应 LLM 客户端。

    当前 active=qwen（阿里 MaaS OpenAI 兼容端点）。
    切换 deepseek/doubao 只需改 json 的 active 字段，无需改代码。
    """
    cfg = get_active_llm_config()
    base = (cfg.get("base_url") or "").lower()
    if not cfg.get("api_key") or not base:
        raise RuntimeError(
            "config/llm_providers.json active provider 缺 api_key/base_url，无法构建 LLM 客户端"
        )
    if "maas.aliyuncs.com" in base or "dashscope.aliyuncs.com" in base:
        return QwenLLM(api_key=cfg["api_key"], base_url=cfg["base_url"], model_id=cfg["model"])
    if "deepseek.com" in base:
        return DeepSeekLLM(api_key=cfg["api_key"], base_url=cfg["base_url"], model_id=cfg["model"])
    if "volces.com" in base:
        return DoubaoLLM(api_key=cfg["api_key"], base_url=cfg["base_url"], model_id=cfg["model"])
    raise RuntimeError("未识别的 LLM provider base_url: %s" % cfg.get("base_url"))


__all__ = ["LLM", "DoubaoLLM", "DeepSeekLLM", "QwenLLM", "active_llm", "get_active_llm_config"]
