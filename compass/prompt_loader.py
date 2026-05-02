"""统一的 Prompt 配置加载器 — 各工程共用"""
import os
import yaml
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 各工程通过环境变量或参数指定 prompts 目录
DEFAULT_PROMPTS_DIR = "prompts"

class PromptManager:
    """Prompt 模板管理器
    
    YAML 格式:
    prompts:
      policy_classify:
        name: "政策分类"
        version: 1
        model: "deepseek-chat"
        temperature: 0.2
        max_tokens: 1000
        system: "你是专业政策分析师，严格按照JSON格式返回结果。"
        template: |
          请分析以下新闻内容，判断是否为政策/监管类资讯。
          新闻内容：{{ content }}
          请按以下JSON格式返回...
    """
    
    def __init__(self, prompts_dir: str = None):
        self.prompts_dir = prompts_dir or os.environ.get("PROMPTS_DIR", DEFAULT_PROMPTS_DIR)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._mtimes: Dict[str, float] = {}
    
    def _load_file(self, filename: str) -> Dict[str, Any]:
        """加载单个 YAML 文件"""
        filepath = os.path.join(self.prompts_dir, filename)
        if not os.path.exists(filepath):
            return {}
        
        mtime = os.path.getmtime(filepath)
        if filename in self._cache and self._mtimes.get(filename) == mtime:
            return self._cache[filename]
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        self._cache[filename] = data
        self._mtimes[filename] = mtime
        return data
    
    def get(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """获取指定 prompt 配置
        
        prompt_id 格式: "filename.key" 或 "key" (默认从 prompts.yml)
        例: "policy_classify" → 从 prompts.yml 加载
            "analysis.stock_eval" → 从 analysis.yml 加载
        """
        if "." in prompt_id:
            filename, key = prompt_id.split(".", 1)
            filename += ".yml"
        else:
            filename = "prompts.yml"
            key = prompt_id
        
        data = self._load_file(filename)
        prompts = data.get("prompts", {})
        prompt = prompts.get(key)
        
        if not prompt:
            logger.warning("Prompt not found: %s (file=%s, key=%s)", prompt_id, filename, key)
            return None
        
        return prompt
    
    def get_system(self, prompt_id: str) -> str:
        """获取 system message"""
        p = self.get(prompt_id)
        return p.get("system", "") if p else ""
    
    def get_template(self, prompt_id: str, **kwargs) -> str:
        """获取渲染后的 template（支持 {{ var }} 变量替换）"""
        p = self.get(prompt_id)
        if not p:
            return ""
        template = p.get("template", "")
        for k, v in kwargs.items():
            template = template.replace("{{ " + k + " }}", str(v))
            template = template.replace("{{" + k + "}}", str(v))
        return template
    
    def get_model_config(self, prompt_id: str) -> Dict[str, Any]:
        """获取模型配置 (model, temperature, max_tokens)"""
        p = self.get(prompt_id)
        if not p:
            return {}
        return {
            "model": p.get("model", ""),
            "temperature": p.get("temperature", 0.3),
            "max_tokens": p.get("max_tokens", 2000),
        }
    
    def list_all(self) -> Dict[str, Dict[str, Any]]:
        """列出所有 prompt 配置"""
        result = {}
        if not os.path.exists(self.prompts_dir):
            return result
        for filename in sorted(os.listdir(self.prompts_dir)):
            if not filename.endswith((".yml", ".yaml")):
                continue
            data = self._load_file(filename)
            prompts = data.get("prompts", {})
            prefix = filename.replace(".yml", "").replace(".yaml", "")
            if prefix == "prompts":
                prefix = ""
            for key, val in prompts.items():
                full_key = f"{prefix}.{key}" if prefix else key
                result[full_key] = val
        return result
    
    def save(self, prompt_id: str, config: Dict[str, Any]) -> bool:
        """保存/更新 prompt 配置"""
        if "." in prompt_id:
            filename, key = prompt_id.split(".", 1)
            filename += ".yml"
        else:
            filename = "prompts.yml"
            key = prompt_id
        
        filepath = os.path.join(self.prompts_dir, filename)
        os.makedirs(self.prompts_dir, exist_ok=True)
        
        # Load existing
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}
        
        if "prompts" not in data:
            data["prompts"] = {}
        data["prompts"][key] = config
        
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        # Invalidate cache
        self._cache.pop(filename, None)
        self._mtimes.pop(filename, None)
        logger.info("Prompt saved: %s", prompt_id)
        return True


# 全局单例 — 各工程直接 import 使用
_manager: Optional[PromptManager] = None

def get_prompt_manager() -> PromptManager:
    global _manager
    if _manager is None:
        _manager = PromptManager()
    return _manager
