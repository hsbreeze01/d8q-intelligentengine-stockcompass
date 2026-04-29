from flask import Blueprint, request, session, jsonify, render_template

bp = Blueprint("security", __name__)


@bp.route("/security/status")
def status():
    if session.get("name") != "admin":
        return "Forbidden", 403
    return jsonify({"status": "ok", "message": "Security module active"})


@bp.route("/security/dashboard")
def dashboard():
    if session.get("name") != "admin":
        return "Forbidden", 403
    return render_template("security_dashboard.html")
