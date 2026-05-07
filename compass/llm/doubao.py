import logging
from volcenginesdkarkruntime import Ark
from compass.llm.base import LLM
from compass.config import Config

logger = logging.getLogger("compass.llm.doubao")


class DoubaoLLM(LLM):
    def __init__(self, api_key=None, base_url=None, model_id=None):
        cfg = Config()
        super().__init__(
            api_key=api_key or cfg.DOUBAO_API_KEY,
            base_url=base_url or cfg.DOUBAO_BASE_URL,
            model_id=model_id or cfg.DOUBAO_MODEL_ID,
        )
        self.client = Ark(api_key=self.api_key, base_url=self.base_url)
        self.is_executing = False

    def standard_request(self, messages):
        if self.is_executing:
            raise Exception("AI is busy, please try again later")
        self.is_executing = True
        try:
            completion = self.client.bot_chat.completions.create(
                model=self.model_id,
                messages=messages,
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error("Doubao request failed: %s", e)
            return None
        finally:
            self.is_executing = False

    def streaming_request(self, messages):
        stream = self.client.bot_chat.completions.create(
            model=self.model_id,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            yield chunk.choices[0].delta.content

    def stock_message(self, message):
        content = self._build_stock_prompt()
        messages = [
            {"role": "user", "content": f"{message}"},
        ]
        return self.standard_request(messages)

    def _build_stock_prompt(self):
        return """你是一位专业且资深的股票分析师，模仿东北证券付鹏的语气和风格。
对给出的股票技术分析数据（包含趋势、强弱、金叉死叉、交易记录等）进行深度解读。
输出格式：
1. 吸引人的标题（不要写"标题"二字），公众号财经文章风格
2. 交易记录总结
3. 技术指标分析
4. 综合建议
要求：说人话，简洁明了，重点突出，以markdown格式输出。"""
