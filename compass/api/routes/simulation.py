from flask import Blueprint, render_template

bp = Blueprint("simulation", __name__)


@bp.route("/simulation", methods=["GET"])
def index():
    return render_template("simulation_decide.html")


@bp.route("/simulation/deal", methods=["GET"])
def deal():
    return render_template("simulation_deal.html")
