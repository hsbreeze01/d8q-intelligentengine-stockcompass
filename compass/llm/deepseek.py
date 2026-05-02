import logging
import time
from openai import OpenAI
from compass.llm.base import LLM
from compass.config import Config

logger = logging.getLogger("compass.llm.deepseek")


class DeepSeekLLM(LLM):
    def __init__(self, api_key=None, base_url=None, model_id=None):
        cfg = Config()
        super().__init__(
            api_key=api_key or cfg.DEEPSEEK_API_KEY,
            base_url=base_url or cfg.DEEPSEEK_BASE_URL,
            model_id=model_id or cfg.DEEPSEEK_MODEL_ID,
        )
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=60.0)

    def standard_request(self, messages, max_retries=2):
        """LLM 调用（含重试）"""
        last_err = None
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_id,
                    temperature=1.3,
                    messages=messages,
                )
                return response.choices[0].message.content
            except Exception as e:
                last_err = e
                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning("DeepSeek request failed (%s), retry in %ds (attempt %d/%d)...", e, wait, attempt + 1, max_retries)
                    time.sleep(wait)
        logger.error("DeepSeek request failed after %d retries: %s", max_retries, last_err)
        return None

    def streaming_request(self, messages):
        stream = self.client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            stream=True,
            timeout=60.0,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            yield chunk.choices[0].delta.content

    def stock_message(self, message):
        content = """你是专业资深的股票分析师，模仿东北证券付鹏的语气和风格。
请对给出的股票分析数据进行深度解读，生成公众号财经文章。
输出要求：
1. 吸引人的标题（不要写"标题"二字）
2. 交易记录总结
3. 技术指标分析（趋势、强弱、金叉死叉）
4. 综合建议
以markdown格式输出，简洁专业。"""
        messages = [
            {"role": "system", "content": content},
            {"role": "user", "content": message},
        ]
        return self.standard_request(messages)
