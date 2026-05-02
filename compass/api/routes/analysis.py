import os
import sys
import logging

from flask import Blueprint, request, jsonify, session

bp = Blueprint("analysis", __name__)
logger = logging.getLogger("compass.analysis")


def _ensure_legacy_path():
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    for p in [base, os.path.dirname(base)]:
        if p not in sys.path:
            sys.path.insert(0, p)


@bp.route("/llm/analyze", methods=["POST"])
def llm_analyze():
    """股票 LLM 分析文章生成（调 Shark 拿数据 + 自有 LLM 生成文章）"""
    import json
    import urllib.request
    data = request.json or {}
    stock_code = data.get("stock_code", "")
    scope = data.get("scope", "all")

    if not stock_code:
        return jsonify({"error": "stock_code required"}), 400

    try:
        # 1. 从 Shark 获取结构化分析数据
        shark_req = urllib.request.Request(
            "http://localhost:5000/api/analysis/stock/comprehensive",
            data=json.dumps({"stock_code": stock_code, "scope": scope}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(shark_req, timeout=90) as resp:
            shark_data = json.loads(resp.read().decode())

        if "error" in shark_data:
            return jsonify({"error": shark_data["error"]}), 500

        # 2. 用 Compass 自有 LLM 将结构化数据生成分析文章
        from compass.llm import DeepSeekLLM
        llm = DeepSeekLLM()
        analysis_json = json.dumps(shark_data, ensure_ascii=False, indent=2)[:2000]
        prompt = f"""基于以下股票分析数据，撰写一篇专业但易懂的投资分析文章。
要求：1.标题吸引人 2.总结关键信号 3.风险提示 4.简明建议
以markdown格式输出。

股票分析数据：
{analysis_json}"""
        result = llm.standard_request([
            {"role": "system", "content": "你是专业资深的股票分析师，擅长将数据转化为通俗易懂的投资分析文章。"},
            {"role": "user", "content": prompt},
        ])

        return jsonify({"analysis": result, "data_source": "shark", "shark_score": shark_data.get("score")})
    except Exception as e:
        logger.error("LLM analysis failed: %s", e)
        return jsonify({"error": str(e)}), 500


@bp.route("/api/strategy/buy_advice", methods=["POST"])
def buy_advice():
    data = request.json or {}
    stock_code = data.get("stock_code", "")
    end_date = data.get("end_date", "")

    if not stock_code:
        return jsonify({"error": "stock_code required"}), 400

    try:
        _ensure_legacy_path()
        from stockdata.main_analysis import summery_trade_json, buy_advice_v2

        analysis_json = summery_trade_json(stock_code, end_date)
        buy_count, sell_count, result_json = buy_advice_v2(analysis_json)
        return jsonify({
            "stock_code": stock_code,
            "date": end_date,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "analysis": result_json,
        })
    except Exception as e:
        logger.error("Strategy analysis failed: %s", e)
        return jsonify({"error": str(e)}), 500
