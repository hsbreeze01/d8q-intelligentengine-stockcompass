import time
import logging
from functools import wraps
from flask import request, session, redirect, url_for, jsonify

logger = logging.getLogger("compass.auth")

PRIVATE_ROUTES = ["/favorite/", "/llm/", "/tracking/"]
SESSION_MAX_AGE = 86400


def session_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("uid") is None:
            if request.args.get("format") == "json":
                return jsonify({"success": False, "message": "Authentication required"}), 401
            return redirect(url_for("auth.login"))

        last_activity = session.get("last_activity")
        current_time = time.time()
        if last_activity is None or (current_time - last_activity) > SESSION_MAX_AGE:
            session.clear()
            if request.args.get("format") == "json":
                return jsonify({"success": False, "message": "Session expired"}), 401
            return redirect(url_for("auth.login"))

        session["last_activity"] = current_time
        return f(*args, **kwargs)
    return decorated


def check_private_routes():
    if not any(request.path.startswith(prefix) for prefix in PRIVATE_ROUTES):
        return None
    return session_required(lambda: None)()
