import logging
from flask import Blueprint, request, jsonify, session, redirect, url_for
from compass.data.database import Database

bp = Blueprint("admin", __name__)
logger = logging.getLogger("compass.admin")


def _is_admin():
    uid = session.get("uid")
    if not uid:
        return False
    try:
        with Database() as db:
            _, user = db.select_one("SELECT is_admin FROM user WHERE id = %s", (uid,))
            return user and user["is_admin"] == 1
    except Exception:
        return False


@bp.route("/api/admin/tasks", methods=["GET"])
def list_tasks():
    if not _is_admin():
        return jsonify({"error": "Forbidden"}), 403
    with Database() as db:
        _, tasks = db.select_many(
            "SELECT t.id, t.title, t.description, t.status, t.created_at, u.username as claimed_by_username "
            "FROM tasks t LEFT JOIN user u ON t.claimed_by = u.id "
            "ORDER BY t.created_at DESC"
        )
        return jsonify({"tasks": tasks})


@bp.route("/api/admin/tasks", methods=["POST"])
def create_task():
    if not _is_admin():
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    with Database() as db:
        db.execute(
            "INSERT INTO tasks (title, description, status) VALUES (%s, %s, 'pending')",
            (title, description)
        )
        return jsonify({"message": "Task created"})


@bp.route("/api/admin/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    if not _is_admin():
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    status = data.get("status", "")
    if status not in ("pending", "claimed", "done"):
        return jsonify({"error": "invalid status"}), 400
    uid = session.get("uid")
    with Database() as db:
        if status == "claimed":
            db.execute(
                "UPDATE tasks SET status='claimed', claimed_by=%s WHERE id=%s AND status='pending'",
                (uid, task_id)
            )
        else:
            db.execute("UPDATE tasks SET status=%s WHERE id=%s", (status, task_id))
        return jsonify({"message": "Task updated"})


@bp.route("/api/admin/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    if not _is_admin():
        return jsonify({"error": "Forbidden"}), 403
    with Database() as db:
        db.execute("DELETE FROM tasks WHERE id=%s", (task_id,))
        return jsonify({"message": "Task deleted"})


@bp.route("/api/admin/stats", methods=["GET"])
def stats_overview():
    if not _is_admin():
        return jsonify({"error": "Forbidden"}), 403
    with Database() as db:
        _, total_users = db.select_one("SELECT COUNT(*) as c FROM user", ())
        _, today_active = db.select_one(
            "SELECT COUNT(DISTINCT user_id) as c FROM user_behavior WHERE DATE(created_at)=CURDATE()", ()
        )
        _, total_analysis = db.select_one(
            "SELECT COUNT(*) as c FROM user_behavior WHERE action='analysis'", ()
        )
        _, total_search = db.select_one(
            "SELECT COUNT(*) as c FROM user_behavior WHERE action='search'", ()
        )
        return jsonify({
            "total_users": total_users["c"] if total_users else 0,
            "today_active": today_active["c"] if today_active else 0,
            "total_analysis": total_analysis["c"] if total_analysis else 0,
            "total_search": total_search["c"] if total_search else 0,
        })


@bp.route("/api/admin/stats/daily-active", methods=["GET"])
def daily_active():
    if not _is_admin():
        return jsonify({"error": "Forbidden"}), 403
    days = request.args.get("days", 7, type=int)
    with Database() as db:
        _, rows = db.select_many(
            "SELECT DATE(created_at) as date, COUNT(DISTINCT user_id) as count "
            "FROM user_behavior "
            "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) "
            "GROUP BY DATE(created_at) ORDER BY date",
            (days,)
        )
        return jsonify({"daily_active": rows})


@bp.route("/api/admin/stats/actions", methods=["GET"])
def action_stats():
    if not _is_admin():
        return jsonify({"error": "Forbidden"}), 403
    with Database() as db:
        _, rows = db.select_many(
            "SELECT action, COUNT(*) as count FROM user_behavior GROUP BY action ORDER BY count DESC",
            ()
        )
        return jsonify({"action_stats": rows})


@bp.route("/api/admin/stats/users", methods=["GET"])
def user_stats():
    if not _is_admin():
        return jsonify({"error": "Forbidden"}), 403
    with Database() as db:
        _, rows = db.select_many(
            "SELECT u.username, COUNT(b.id) as count, MAX(b.created_at) as last_active "
            "FROM user u LEFT JOIN user_behavior b ON u.id=b.user_id "
            "GROUP BY u.id ORDER BY count DESC LIMIT 50",
            ()
        )
        return jsonify({"user_actions": rows})


@bp.route("/api/admin/users", methods=["GET"])
def list_users():
    if not _is_admin():
        return jsonify({"error": "Forbidden"}), 403
    with Database() as db:
        _, users = db.select_many("SELECT id, username, is_admin FROM user", ())
        return jsonify({"users": users})


@bp.route("/admin/tasks")
def admin_tasks_page():
    if not _is_admin():
        return redirect(url_for("auth.login"))
    return redirect("/static/admin/admin_tasks.html")


@bp.route("/admin/stats")
def admin_stats_page():
    if not _is_admin():
        return redirect(url_for("auth.login"))
    return redirect("/static/admin/admin_stats.html")
