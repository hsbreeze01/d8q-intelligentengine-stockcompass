import os
import sys
import logging
import json
import urllib.request

from flask import Blueprint, request, jsonify, session

bp = Blueprint("analysis", __name__)
logger = logging.getLogger("compass.analysis")

# Prompt 管理器
COMPASS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, COMPASS_ROOT)
from prompt_loader import PromptManager
_pm = PromptManager(os.path.join(COMPASS_ROOT, 'prompts'))


def _ensure_legacy_path():
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    for p in [base, os.path.dirname(base)]:
        if p not in sys.path:
            sys.path.insert(0, p)


@bp.route("/llm/analyze", methods=["POST"])
def llm_analyze():
    """股票 LLM 分析文章生成（调 Shark 拿数据 + 自有 LLM 生成文章）"""
    data = request.json or {}
    stock_code = data.get("stock_code", "")
    scope = data.get("scope", "all")

    if not stock_code:
        return jsonify({"error": "stock_code required"}), 400

    try:
        # 1. 从 Shark 获取结构化分析数据
        # [MIGRATION-StockShark→Compass] 此端点可能在 StockShark 内部使用 LLM 做综合分析
        # Task 3.2: 在 Compass 实现等价双 LLM 分析后，替换为 Compass 自有分析
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

        # 2. 从 prompt 配置加载模板
        analysis_json = json.dumps(shark_data, ensure_ascii=False, indent=2)[:2000]
        prompt = _pm.get_template("stock_article", analysis_data=analysis_json)
        system = _pm.get_system("stock_article")

        # 3. 用 Compass 自有 LLM 生成分析文章
        from compass.llm import DeepSeekLLM
        llm = DeepSeekLLM()
        result = llm.standard_request([
            {"role": "system", "content": system},
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
