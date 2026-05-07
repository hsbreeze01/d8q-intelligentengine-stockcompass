"""每日推荐股票 API 路由"""
import logging
from flask import Blueprint, request, jsonify, session

bp = Blueprint("recommendation", __name__)
logger = logging.getLogger("compass.recommendation")


def _is_admin():
    """检查当前用户是否为管理员"""
    uid = session.get("uid")
    if not uid:
        return False
    try:
        from compass.data.database import Database
        with Database() as db:
            _, user = db.select_one("SELECT is_admin FROM user WHERE id = %s", (uid,))
            return user and user["is_admin"] == 1
    except Exception:
        return False


@bp.route("/api/recommendation/daily", methods=["GET"])
def get_daily_recommendation():
    """获取每日推荐股票列表。

    Query Params:
        date   (str): 日期 YYYY-MM-DD，默认当天
        limit  (int): 返回数量，默认 20
        offset (int): 偏移量，默认 0
    """
    date = request.args.get("date")
    try:
        limit = int(request.args.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    try:
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0

    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    try:
        from compass.services.recommendation import RecommendationService
        svc = RecommendationService()
        result = svc.get_daily(date=date, limit=limit, offset=offset)
        return jsonify(result), 200
    except Exception as e:
        logger.error("获取每日推荐失败: %s", e)
        return jsonify({"error": str(e)}), 500


@bp.route("/api/recommendation/generate", methods=["POST"])
def generate_recommendation():
    """手动触发推荐计算（管理员权限）。"""
    if not _is_admin():
        return jsonify({"error": "Forbidden"}), 403

    data = request.json or {}
    target_date = data.get("date")

    try:
        from compass.services.recommendation import RecommendationService
        svc = RecommendationService()
        result = svc.generate_daily(target_date=target_date)
        return jsonify(result), 200
    except Exception as e:
        logger.error("推荐计算失败: %s", e)
        return jsonify({"error": str(e)}), 500


@bp.route("/api/recommendation/performance", methods=["GET"])
def get_recommendation_performance():
    """推荐效果回溯。

    Query Params:
        date (str): 推荐日期 YYYY-MM-DD（必填）
    """
    date = request.args.get("date")
    if not date:
        return jsonify({"error": "date parameter required"}), 400

    try:
        from compass.services.recommendation import RecommendationService
        svc = RecommendationService()
        result = svc.get_performance(date)
        return jsonify(result), 200
    except Exception as e:
        logger.error("推荐效果回溯失败: %s", e)
        return jsonify({"error": str(e)}), 500
