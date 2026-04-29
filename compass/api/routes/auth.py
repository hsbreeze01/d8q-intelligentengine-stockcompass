import time
import logging

import requests
from flask import Blueprint, request, render_template, session, redirect, url_for, jsonify

from compass.data.database import Database
from compass.config import get_config

bp = Blueprint("auth", __name__)
logger = logging.getLogger("compass.auth")


@bp.route("/login", methods=["POST", "GET"])
def login():
    response_type = request.form.get("format", "html")

    if request.method == "GET":
        if response_type == "json":
            return jsonify({"message": "Please use POST method for login"})
        return render_template("login.html")

    username = request.form["username"]
    password = request.form["password"]

    with Database() as db:
        count, user = db.select_one("SELECT * FROM user WHERE username = %s", (username,))

    if user is None or user["password"] != password:
        msg = "Username or password is incorrect."
        if response_type == "json":
            return jsonify({"success": False, "message": msg}), 401
        return render_template("login.html", msg=msg)

    ip = request.remote_addr
    with Database() as db:
        db.execute("INSERT INTO login_log (user_id, login_time, ip) VALUES (%s, NOW(), %s)", (user["id"], ip))

    session["uid"] = user["id"]
    session["name"] = username
    session["last_activity"] = time.time()

    if response_type == "json":
        return jsonify({
            "success": True,
            "message": "Login successful",
            "user": {"id": user["id"], "username": username, "nickname": user.get("nickname", username)},
        })
    return redirect(url_for("pages.index"))


@bp.route("/login2", methods=["POST"])
def login2():
    cfg = get_config()
    code = request.json.get("code")
    if not code:
        return jsonify({"success": False, "message": "missing code parameter"}), 400

    url = (
        f"https://api.weixin.qq.com/sns/jscode2session"
        f"?appid={cfg.WX_APPID}&secret={cfg.WX_SECRET}&js_code={code}&grant_type=authorization_code"
    )
    resp = requests.get(url)
    data = resp.json()

    if "openid" not in data:
        logger.error("openid not found: %s", data)
        return jsonify({"success": False, "message": "Failed to get openid"}), 400

    openid = data["openid"]

    with Database() as db:
        count, user = db.select_one("SELECT * FROM user WHERE username = %s", (openid,))
        if user is None:
            db.execute(
                "INSERT INTO user (username, password, nickname) VALUES (%s, %s, %s)",
                (openid, f"user_{openid}", f"微信用户_{openid}"),
            )

    with Database() as db:
        count, user = db.select_one("SELECT * FROM user WHERE username = %s", (openid,))
        ip = request.remote_addr
        db.execute("INSERT INTO login_log (user_id, login_time, ip) VALUES (%s, NOW(), %s)", (user["id"], ip))

    session["uid"] = user["id"]
    session["name"] = user["username"]
    session["last_activity"] = time.time()

    return jsonify({
        "success": True,
        "message": "Login successful",
        "openid": user["username"],
        "uid": user["id"],
        "nickname": user["nickname"],
    })


@bp.route("/logout")
def logout():
    session.clear()
    return render_template("login.html")


@bp.route("/register", methods=["POST", "GET"])
def register():
    response_type = request.form.get("format", "html")

    if request.method == "GET":
        if response_type == "json":
            return jsonify({"message": "Please use POST method for registration"})
        return render_template("register.html")

    username = request.form["username"]
    password = request.form["password"]
    nickname = request.form["nickname"]

    with Database() as db:
        count, user = db.select_one("SELECT * FROM user WHERE username = %s", (username,))
        if user:
            if response_type == "json":
                return jsonify({"success": False, "message": "Username already exists."}), 400
            return render_template("register.html", result="failed", msg="Username already exists.")

        count, nickname_user = db.select_one("SELECT * FROM user WHERE nickname = %s", (nickname,))
        if nickname_user:
            if response_type == "json":
                return jsonify({"success": False, "message": "Nickname already exists."}), 400
            return render_template("register.html", result="failed", msg="Nickname already exists.")

        db.execute(
            "INSERT INTO user (username, password, nickname) VALUES (%s, %s, %s)",
            (username, password, nickname),
        )

    if response_type == "json":
        return jsonify({"success": True, "message": "Registration successful"})
    return render_template("register.html", result="success", msg="ok.")
