# -*- coding: utf-8 -*-
import requests
import os
from openai import OpenAI
from volcenginesdkarkruntime import Ark
import logging
from abc import ABC, abstractmethod

#deepseek api_key sk-4c521f89ee42495d93b4b315942f479d
# model='deepseek-reasoner'

#doubao api_key="0d8fc20e-c862-4542-b66e-cc26b028db09", base_url="https://ark.cn-beijing.volces.com/api/v3", model_id="bot-20250119142523-cd55z"

#ep-20250223224336-v7d69
#ep-20250119142208-ctl59

# Abstract class LLM
class LLM(ABC):
    logger = logging.getLogger("my_logger")

    def __init__(self, api_key, base_url, model_id):
        self.api_key = api_key
        self.base_url = base_url
        self.model_id = model_id
        self.is_excuting = False

    @abstractmethod
    def standard_request(self, messages):
        pass

    @abstractmethod
    def streaming_request(self, messages):
        pass

    @abstractmethod
    def stock_message(self, message):
        pass

# Concrete class DoubaoLLM
class DoubaoLLM(LLM):
    def __init__(self, api_key="0d8fc20e-c862-4542-b66e-cc26b028db09", base_url="https://ark.cn-beijing.volces.com/api/v3", model_id="bot-20250224115324-hl69c"):
        super().__init__(api_key, base_url, model_id)
        self.client = Ark(api_key=api_key, base_url=base_url)

    def standard_request(self, messages):
        if self.is_excuting:
            raise Exception("AI 目前正在执行任务，请稍后再试.")

        self.is_excuting = True
        try:
            completion = self.client.bot_chat.completions.create(
                model=self.model_id,
                # temperature = 1.3,
                messages=messages,
            )
        except Exception as e:
            self.is_excuting = False
            self.logger.error(e)
            return None

        self.is_excuting = False
        return completion.choices[0].message.content

    def streaming_request(self, messages):
        stream = self.client.bot_chat.completions.create(
            model=self.model_id,
            messages=messages,
            stream=True
        )
        # print("----- streaming request -----")
        for chunk in stream:
            if chunk.references:
                print(chunk.references)
            if not chunk.choices:
                continue
            print(chunk.choices[0].delta.content, end="")
        print()

    def stock_message(self, message):
        content = f"""
# 角色
你是一位专业且资深的股票分析师,喜欢模仿东北证券的付鹏。凭借深厚的专业知识和丰富的经验，你将根据用户输入的详细内容进行全面、精准的分析，并按照特定要求总结输出。
# 任务描述与要求
1. 首先仔细剖析用户输入内容，分别对“建议”“指数分析明细”“交易记录”进行详细解读和总结。对于“建议”，买入策略为 -1 是指当天推荐买入但出现了比较危险的信号终止交易；对于“指数分析明细”，如（rsi1、rsi2、rsi3、kdj、macd）表示趋势的斜率；以及kdj的头部和底部描述，只针对true的情况分析
2. 接着通过可靠网络渠道，查询用户输入股票代码当天的相关信息，重点关注重大新闻以及该股票所属板块是否为热门板块。
3. 最后，按照特定输出格式，先以标题模式呈现内容，先对指数分析明细和交易记录进行深度分析和总结，再结合“建议”部分的信息，形成完整、有条理且具有参考价值的输出内容。
4. 以markdown的格式输出
5. 整篇文章是为了发送到公众号去
6. 标题要吸引人
# 参考示例
示例 1：
用户：提供了股票 A 当日的建议、指数分析明细 和近5天的股票分析

输出：
### 交易记录总结
最近 5 天股票 A 股价平稳上升且成交量适中，基本面状况良好。
### 指数分析明细总结
各项指标显示股票 A 整体呈上升趋势，但上升斜率不算特别大，目前未出现头部或底部信号。
### 综合分析与建议
结合建议中买入策略为 1，以及网络查询到股票 A 当天无重大负面新闻且属于热门板块，综合判断股票 A 短期内具有一定投资价值，可考虑适当买入。

# 相关限制
1. 仅依据用户提供的输入内容以及网络查询到的当天相关信息进行分析。
2. 分析和总结需基于专业知识和客观事实，不添加无根据的主观臆断。
3. 输出内容严格按照规定的标题模式和结构进行组织。
"""
        content2 = f"""
# 角色
你是一位专业且资深的股票分析师，凭借深厚的专业知识和丰富的经验，你将根据用户输入的详细内容进行全面、精准的分析，并按照特定要求总结输出。
你可以模拟东北证券付鹏的语气和风格，对用户输入的股票分析内容进行深度解读和分析。
# 任务描述与要求
1. 对给出的信息进行分析，根据提供的这些信息进行深度解读，分析出股票的走势和未来的发展趋势，最后给出专业的建议。
2. 可以对网络上的相关信息进行查询，获取当天股票的相关信息，重点关注重大新闻以及该股票所属板块是否为热门板块。
3. 说人话，不要加入付鹏的名字，但是可以模拟他的语气和风格，对用户输入的股票分析内容进行深度解读和分析，写作的方式可以按照公众号的风格，简洁明了，重点突出。
4. 我是要写公众号的文章，按照公众号财经文章的方式写
5. 要有一个吸引人的标题，引导用户阅读。开头不要显示标题这2个字，直接写标题内容。

        """

        messages = [
            #  {"role": "system", "content": content},
            {"role": "user", "content": f"{message}"},
        ]
        return self.standard_request(messages)

# Concrete class DeepSeekLLM
class DeepSeekLLM(LLM):
    # model='deepseek-chat' , 'deepseek-reasoner'
    def __init__(self, api_key="sk-4c521f89ee42495d93b4b315942f479d", base_url="https://api.deepseek.com", model_id="deepseek-reasoner"):
        super().__init__(api_key, base_url, model_id)
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def standard_request(self, messages):
        if self.is_excuting:
            raise Exception("AI 目前正在执行任务，请稍后再试.")

        self.is_excuting = True
        # temperature 参数说明
        # 代码生成/数学解题   	0.0
        # 数据抽取/分析	1.0
        # 通用对话	1.3
        # 翻译	1.3
        # 创意类写作/诗歌创作	1.5
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                temperature = 1.3,
                messages=messages,
            )
        except Exception as e:
            self.is_excuting = False
            self.logger.error(e)
            return None

        self.is_excuting = False
        return response.choices[0].message.content

    def streaming_request(self, messages):
        stream = self.client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            stream=True
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            print(chunk.choices[0].delta.content, end="")
        print()

    def stock_message(self, message):
        content = f"""
# 角色
你是一位专业且资深的股票分析师,喜欢模仿东北证券的付鹏。凭借深厚的专业知识和丰富的经验，你将根据用户输入的详细内容进行全面、精准的分析，并按照特定要求总结输出。
# 任务描述与要求
1. 首先仔细剖析用户输入内容，分别对“建议”“指数分析明细”“交易记录”进行详细解读和总结。对于“建议”，买入策略为 -1 是指当天推荐买入但出现了比较危险的信号终止交易；对于“指数分析明细”，如（rsi1、rsi2、rsi3、kdj、macd）表示趋势的斜率；以及kdj的头部和底部描述，只针对true的情况分析
2. 接着通过可靠网络渠道，查询用户输入股票代码当天的相关信息，重点关注重大新闻以及该股票所属板块是否为热门板块。
3. 最后，按照特定输出格式，先以标题模式呈现内容，先对指数分析明细和交易记录进行深度分析和总结，再结合“建议”部分的信息，形成完整、有条理且具有参考价值的输出内容。
4. 以markdown的格式输出
5. 整篇文章是为了发送到公众号去
6. 标题要吸引人
# 参考示例
示例 1：
用户：提供了股票 A 当日的建议、指数分析明细 和近5天的股票分析

输出：
### 交易记录总结
最近 5 天股票 A 股价平稳上升且成交量适中，基本面状况良好。
### 指数分析明细总结
各项指标显示股票 A 整体呈上升趋势，但上升斜率不算特别大，目前未出现头部或底部信号。
### 综合分析与建议
结合建议中买入策略为 1，以及网络查询到股票 A 当天无重大负面新闻且属于热门板块，综合判断股票 A 短期内具有一定投资价值，可考虑适当买入。

# 相关限制
1. 仅依据用户提供的输入内容以及网络查询到的当天相关信息进行分析。
2. 分析和总结需基于专业知识和客观事实，不添加无根据的主观臆断。
3. 输出内容严格按照规定的标题模式和结构进行组织。
"""
        messages = [
            {"role": "system", "content": content},
            {"role": "user", "content": f"{message}"},
        ]
        return self.standard_request(messages)



# Usage example
if __name__ == "__main__":
    llm = DoubaoLLM(model_id="bot-20250224115324-hl69c")
    # llm = DeepSeekLLM()
    result = llm.stock_message("""
000001 2025-01-16 的分析记录

1.建议

策略命中情况 买入策略 0 次 卖出策略 1 次

趋势 [Ma5趋势指标预期向下，建议卖出]

强弱 [多方强，推荐买入]

交叉 [金叉死叉不明朗，建议观望]

买入建议

下影线大于实体和上影线，如果当前价格是近期低位，对价格有支撑，利多

2.指数分析明细

RSI

强弱 [[27.0505, "弱"], [22.2357, "弱"], [43.8308, "弱"], [52.6051, "强"], [59.4468, "强"]]

趋势 rsi1 9.516200000000001 rsi2 0.7076387878787883 rsi3 -0.5359326315789475

交叉 {"20250114": "金叉"}

KDJ

强弱 [[23.2116, "弱"], [19.87, "超卖"], [27.7394, "弱"], [42.7354, "弱"], [58.1872, "强"]]

趋势 kdj 9.28166

交叉 {"20250114": "金叉"}

头部形成 False 底部形成 False

MACD

强弱 [[-0.102655, "弱"], [-0.117643, "弱"], [-0.0977145, "弱"], [-0.0669337, "弱"], [-0.0320882, "弱"]]

趋势 macd 0.01918429

MA

趋势 ma5 -0.011800000000000034 ma10 -0.04153333333333339 ma20 0.002280827067669168

VOLUME

趋势 24632.500000000004

3.交易记录

20250116 开盘[高开] 收盘[涨]

 open[11.55] close[11.57] high[11.59] low[11.47]

MA指标 5日 [11.386 支撑
]

10日 [11.416 支撑
]

20日 [11.5825 压力
]

BOLL指标 上轨 [12.0089
]

中轨 [11.5825]

下轨 [11.1561
 | 支撑 位
]

成交量 872964 比昨日 0.8461979137889419

换手率 0.45 比昨日 0.8490566037735849

20250115 开盘[平开] 收盘[涨]

 open[11.38] close[11.48] high[11.58] low[11.36]

MA指标 5日 [11.352 支撑
]

10日 [11.402 支撑
 |👆买入信号
]

20日 [11.5865 压力
]

BOLL指标 上轨 [12.0138
]

中轨 [11.5865]

下轨 [11.1592
 | 支撑 位
]

成交量 1031631 比昨日 1.2510244000635438

换手率 0.53 比昨日 1.2619047619047619

20250114 开盘[平开] 收盘[涨]

 open[11.20] close[11.38] high[11.40] low[11.19]

MA指标 5日 [11.356 支撑
 |👆买入信号
]

10日 [11.424 压力
]

20日 [11.589 压力
]

BOLL指标 上轨 [12.0144
]

中轨 [11.589]

下轨 [11.1636
 | 支撑 位
]

成交量 824629 比昨日 0.8819882220316033

换手率 0.42 比昨日 0.875

20250113 开盘[低开] 收盘[跌]

❗️股价 创新低 volume背离 turnover_rate背离

 open[11.25] close[11.20] high[11.26] low[11.08]

MA指标 5日 [11.382 压力
]

10日 [11.481 压力
]

20日 [11.5985 压力
]

BOLL指标 上轨 [12.0131
]

中轨 [11.5985]

下轨 [11.1839
 | 支撑 位
]

成交量 934966 比昨日 1.1714398835283297

换手率 0.48 比昨日 1.170731707317073

20250110 开盘[平开] 收盘[跌]

 open[11.40] close[11.30] high[11.46] low[11.28]

MA指标 5日 [11.43 压力
]

10日 [11.544 压力
]

20日 [11.6165 压力
]

BOLL指标 上轨 [11.9896
]

中轨 [11.6165]

下轨 [11.2434
 | 支撑 位
]

成交量 798134 比昨日 1.062078583281325

换手率 0.41 比昨日 1.0512820512820513
                      """)
    
    print(result)
    print('---')
