"""同步触发 API 端点 — POST /api/sync/dic-stock"""
import logging
import threading

from flask import Blueprint, jsonify, session

from compass.data.database import Database
from compass.sync.dic_stock_sync import sync_dic_stock

bp = Blueprint("sync", __name__)
logger = logging.getLogger("compass.sync")

# 模块级并发控制
_sync_lock = threading.Lock()
_sync_running = False
_last_result = None


def _is_admin():
    """管理员权限校验 — 复用 admin.py 中的模式"""
    uid = session.get("uid")
    if not uid:
        return False
    try:
        with Database() as db:
            _, user = db.select_one("SELECT is_admin FROM user WHERE id = %s", (uid,))
            return user and user["is_admin"] == 1
    except Exception:
        return False


@bp.route("/api/sync/dic-stock", methods=["POST"])
def trigger_sync():
    """管理员触发 dic_stock 同步（后台线程异步执行）。"""
    global _sync_running, _last_result

    if not _is_admin():
        return jsonify({"error": "Forbidden"}), 403

    if _sync_running:
        return jsonify({"error": "Sync already in progress"}), 409

    def _run():
        global _sync_running, _last_result
        try:
            _sync_running = True
            _last_result = sync_dic_stock()
        except Exception as e:
            logger.error("Sync failed: %s", e)
            _last_result = {"error": str(e)}
        finally:
            _sync_running = False

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return jsonify({"message": "Sync started"}), 202


@bp.route("/api/sync/dic-stock/status", methods=["GET"])
def sync_status():
    """返回最近一次同步摘要和进行中状态。"""
    return jsonify({
        "running": _sync_running,
        "last_result": _last_result,
    })
