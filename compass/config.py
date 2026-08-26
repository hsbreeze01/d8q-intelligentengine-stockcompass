"""StockCompass 配置模块 — 支持多 LLM provider 切换"""
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Provider 配置文件路径
PROVIDERS_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "llm_providers.json")


def load_providers_config():
    """加载 provider 配置"""
    if os.path.exists(PROVIDERS_CONFIG_PATH):
        try:
            with open(PROVIDERS_CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active": "qwen", "providers": {}}


def get_active_llm_config():
    """获取当前活跃的 LLM 配置"""
    providers_config = load_providers_config()
    active_provider = providers_config.get("active", "qwen")
    provider = providers_config.get("providers", {}).get(active_provider, {})
    
    return {
        "api_key": provider.get("api_key", ""),
        "base_url": provider.get("base_url", ""),
        "model": provider.get("model", ""),
    }


class Config:
    """基础配置类"""

    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY") or "stockcompass-secret-change-in-production"
    DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

    # MySQL
    MYSQL_HOST = os.environ.get("MYSQL_HOST") or "127.0.0.1"
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT") or 3306)
    MYSQL_USER = os.environ.get("MYSQL_USER") or "root"
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD") or ""
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE") or "stock_analysis_system"

    # DB Pool
    DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN") or 5)
    DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX") or 20)

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL") or "INFO"
    LOG_DIR = os.environ.get("LOG_DIR") or "/var/log/d8q"

    # Schedule
    SCHEDULE_HOUR = int(os.environ.get("SCHEDULE_HOUR") or 17)
    SCHEDULE_MINUTE = int(os.environ.get("SCHEDULE_MINUTE") or 0)

    # LLM - 从 provider 配置读取
    _llm_config = get_active_llm_config()
    LLM_API_KEY = _llm_config["api_key"]
    LLM_BASE_URL = _llm_config["base_url"]
    LLM_MODEL_ID = _llm_config["model"]

    # 保留旧的环境变量兼容性
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or LLM_API_KEY
    DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL") or LLM_BASE_URL
    DEEPSEEK_MODEL_ID = os.environ.get("DEEPSEEK_MODEL_ID") or LLM_MODEL_ID

    # Doubao (保留兼容)
    DOUBAO_API_KEY = os.environ.get("DOUBAO_API_KEY") or ""
    DOUBAO_BASE_URL = os.environ.get("DOUBAO_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL_ID = os.environ.get("DOUBAO_MODEL_ID") or ""

    # WeChat
    WX_APPID = os.environ.get("WX_APPID") or ""
    WX_SECRET = os.environ.get("WX_SECRET") or ""

    # API
    API_PREFIX = "/api"

    # Session
    SESSION_LIFETIME = int(os.environ.get("SESSION_LIFETIME") or 86400)

    # CORS
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS") or "*"

    # Ontology Service
    ONTOLOGY_SERVICE_URL = os.environ.get("ONTOLOGY_SERVICE_URL") or "http://127.0.0.1:8080"


class DevelopmentConfig(Config):
    DEBUG = True
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE") or "stock"


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    MYSQL_DATABASE = "test_stock_analysis_system"


_config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config(env: str = None) -> Config:
    """获取配置对象"""
    if env is None:
        env = os.environ.get("FLASK_ENV", "development")
    return _config_map.get(env, _config_map["default"])()
