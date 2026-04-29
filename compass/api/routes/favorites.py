import logging
from datetime import datetime, timedelta

from flask import Blueprint, request, session, redirect, url_for, jsonify, render_template

from compass.data.database import Database

bp = Blueprint("favorites", __name__)
logger = logging.getLogger("compass.favorites")


@bp.route("/favorite/add", methods=["POST", "GET"])
def add():
    stock_code = request.args.get("stock_code", "0")
    user_id = session["uid"]
    response_type = request.args.get("format", "html")

    with Database() as db:
        count, stock = db.select_one("SELECT code FROM dic_stock WHERE code = %s", (stock_code,))
        if not stock:
            if response_type == "json":
                return jsonify({"success": False, "error": "Stock code does not exist"}), 400
            return render_template("error.html", error="Stock code does not exist.")

        count, fav = db.select_one(
            "SELECT * FROM user_stock WHERE user_id = %s AND stock_code = %s", (user_id, stock_code)
        )
        if count == 0:
            db.execute(
                "INSERT INTO user_stock (user_id, stock_code) VALUES (%s, %s)", (user_id, stock_code)
            )

    if response_type == "json":
        return jsonify({"success": True, "message": "Stock added to favorites"})
    return redirect(url_for("pages.index"))


@bp.route("/favorite/delete", methods=["POST"])
def delete():
    stock_code = request.form.get("stock_code")
    user_id = session["uid"]
    response_type = request.form.get("format", "html")

    with Database() as db:
        db.execute("DELETE FROM user_stock WHERE user_id = %s AND stock_code = %s", (user_id, stock_code))

    if response_type == "json":
        return jsonify({"success": True, "message": "Stock removed from favorites"})
    return redirect(url_for("favorites.list"))


@bp.route("/favorite/list", methods=["GET"])
def list():
    user_id = session.get("uid")
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    response_type = request.args.get("format", "html")

    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        prev_date = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
        next_date = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        if response_type == "json":
            return jsonify({"error": "Invalid date format"}), 400
        return render_template("error.html", message="Invalid date format.")

    with Database() as db:
        sql = (
            "SELECT a.stock_code, b.stock_name, b.industry, b.last_update_time, b.stock_data_daily_update_time, "
            "COALESCE(c.open, 0) AS open, COALESCE(c.close, 0) AS close, COALESCE(c.high, 0) AS high, "
            "COALESCE(c.low, 0) AS low, COALESCE(c.volume, 0) AS volume, COALESCE(c.turnover, 0) AS turnover, "
            "COALESCE(c.amplitude, 0) AS amplitude, COALESCE(c.change_percentage, 0) AS change_percentage, "
            "COALESCE(c.change_amount, 0) AS change_amount, COALESCE(c.turnover_rate, 0) AS turnover_rate "
            "FROM user_stock a "
            "LEFT JOIN dic_stock b ON a.stock_code = b.code "
            "LEFT JOIN stock_data_daily c ON a.stock_code = c.stock_code AND c.date = %s "
            "WHERE a.user_id = %s"
        )
        count, favorites = db.select_many(sql, (date, user_id))

    if count == 0:
        if response_type == "json":
            return jsonify({"stocks": [], "message": "No favorites yet"})
        return render_template("favorites.html", stocks=[], error="No favorites yet")

    if response_type == "json":
        return jsonify({
            "stocks": favorites,
            "prev_date": prev_date,
            "next_date": next_date,
            "date": date,
        })
    return render_template("favorites.html", stocks=favorites, prev_date=prev_date, next_date=next_date, date=date)
