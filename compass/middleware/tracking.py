import logging
from flask import request, session
from compass.data.database import Database

logger = logging.getLogger("compass.tracking")


def track_action(action, target=None, details=None):
    uid = session.get("uid")
    if not uid:
        return
    try:
        with Database() as db:
            db.execute(
                "INSERT INTO user_behavior (user_id, action, target, details, ip) VALUES (%s, %s, %s, %s, %s)",
                (uid, action, target, details, request.remote_addr)
            )
    except Exception as e:
        logger.error("Failed to track action: %s", e)


def track_analysis(stock_code):
    track_action("analysis", target=stock_code)


def track_search(stock_code):
    track_action("search", target=stock_code)


def track_favorite(action, stock_code):
    track_action("favorite_" + action, target=stock_code)


def track_page_view():
    if request.path.startswith("/static/") or request.path.startswith("/api/"):
        return
    track_action("page_view", target=request.path)
