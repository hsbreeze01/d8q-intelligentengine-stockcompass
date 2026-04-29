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
    data = request.json or {}
    stock_code = data.get("stock_code", "")
    end_date = data.get("end_date", "")

    if not stock_code:
        return jsonify({"error": "stock_code required"}), 400

    try:
        from compass.llm import DoubaoLLM
        llm = DoubaoLLM()
        message = f"股票代码: {stock_code}, 分析日期: {end_date or 'today'}"
        result = llm.stock_message(message)
        return jsonify({"analysis": result})
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
