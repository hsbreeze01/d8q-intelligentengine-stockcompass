import logging
from datetime import datetime, timedelta

import pandas as pd
from flask import Blueprint, request, render_template, session, jsonify

from compass.data.database import Database

bp = Blueprint("pages", __name__)
logger = logging.getLogger("compass.pages")


def _get_dic_stock():
    try:
        with Database() as db:
            count, rows = db.select_many("SELECT * FROM dic_stock WHERE latest_price > 0 AND status = 0 ORDER BY code")
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        logger.error("Failed to load dic_stock: %s", e)
        return pd.DataFrame()


@bp.route("/")
def index():
    stock_code = request.args.get("code")
    response_type = request.args.get("format", "html")
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 50, type=int)
    page_size = min(max(page_size, 5), 100)

    name = session.get("name", "Guest")
    df = _get_dic_stock()

    if stock_code and not df.empty:
        mask = df["code"].str.contains(stock_code) | df["stock_name"].str.contains(stock_code)
        df = df[mask]

    total_records = len(df)
    total_pages = max((total_records + page_size - 1) // page_size, 1)
    page = max(1, min(page, total_pages))

    start = (page - 1) * page_size
    stocks = df.iloc[start:start + page_size]

    stocks_list = []
    for _, row in stocks.iterrows():
        update_time = row.get("stock_data_daily_update_time")
        stocks_list.append({
            "code": row["code"],
            "stock_name": row["stock_name"],
            "stock_prefix": row["stock_prefix"],
            "latest_price": row["latest_price"],
            "change_60days": row["change_60days"],
            "change_ytd": row["change_ytd"],
            "last_update_time": row["last_update_time"],
            "stock_data_daily_update_time": update_time.strftime("%Y-%m-%d %H:%M") if update_time else "",
        })

    if response_type == "json":
        return jsonify({
            "name": name,
            "stocks": stocks_list,
            "page": page,
            "total_pages": total_pages,
            "total_records": total_records,
        })
    return render_template("index.html", name=name, stocks=stocks_list, page=page, total_pages=total_pages, total_records=total_records)


@bp.route("/recommended/<date>", methods=["GET"])
def recommended_stocks(date):
    fmt = request.args.get("format", "html")
    if date == "today":
        date = datetime.now().strftime("%Y-%m-%d")

    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        prev_date = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
        next_date = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        if fmt == "json":
            return jsonify({"error": "Invalid date format"}), 400
        return render_template("error.html", message="Invalid date format.")

    with Database() as db:
        sql = (
            "SELECT a.stock_code, b.stock_name, b.industry, a.buy, a.record_time, "
            "c.open, c.close, c.high, c.low, c.volume, c.turnover, c.amplitude, "
            "c.change_percentage, c.change_amount, c.turnover_rate "
            "FROM stock_analysis a, dic_stock b, stock_data_daily c "
            "WHERE a.buy > 0 AND a.stock_code = b.code AND a.stock_code = c.stock_code "
            "AND a.record_time = %s AND a.record_time = c.date ORDER BY b.industry, b.stock_name"
        )
        count, recommended = db.select_many(sql, (date,))

    if fmt == "json":
        return jsonify({"recommended_stocks": recommended, "date": date, "prev_date": prev_date, "next_date": next_date})
    return render_template("recommended_stocks.html", recommended_stocks=recommended, date=date, prev_date=prev_date, next_date=next_date)

@bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@bp.route("/report")
def report():
    return render_template("report.html")

@bp.route("/policy")
def policy():
    return render_template("policy.html")

