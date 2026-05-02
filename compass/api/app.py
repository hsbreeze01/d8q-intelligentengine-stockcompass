import os
import sys
import threading
import time
import logging

from flask import Flask
from flask_compress import Compress

from compass.config import get_config
from compass.utils.logger import setup_logging
from compass.middleware.security import SecurityMiddleware
from compass.middleware.auth import check_private_routes

logger = logging.getLogger("compass.api")


def create_app(env=None):
    cfg = get_config(env)
    setup_logging()

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates"),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static"),
    )
    app.config["SECRET_KEY"] = cfg.SECRET_KEY
    app.config["DEBUG"] = cfg.DEBUG

    Compress(app)
    SecurityMiddleware(app)

    _register_blueprints(app)
    _register_request_hooks(app)
    _start_scheduler(app, cfg)

    logger.info("StockCompass app created (env=%s, debug=%s)", os.environ.get("FLASK_ENV", "development"), cfg.DEBUG)
    return app


def _register_blueprints(app):
    from compass.api.routes.pages import bp as pages_bp
    from compass.api.routes.auth import bp as auth_bp
    from compass.api.routes.favorites import bp as favorites_bp
    from compass.api.routes.analysis import bp as analysis_bp
    from compass.api.routes.simulation import bp as simulation_bp
    from compass.api.routes.security import bp as security_bp
    from compass.api.routes.backtest import bp as backtest_bp
    from compass.api.routes.subscription import bp as subscription_bp
    from compass.api.routes.market_data import bp as market_data_bp
    from compass.api.routes.report import bp as report_bp
    from compass.api.routes.policy import bp as policy_bp
    from compass.api.routes.notify import bp as notify_bp
    from compass.api.routes.prompts import bp as prompts_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(favorites_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(simulation_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(backtest_bp)
    app.register_blueprint(subscription_bp)
    app.register_blueprint(market_data_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(policy_bp)
    app.register_blueprint(notify_bp)
    app.register_blueprint(prompts_bp)


def _register_request_hooks(app):
    @app.before_request
    def before_request():
        from flask import request

        logger.debug("Request: %s %s", request.method, request.url)
        result = check_private_routes()
        if result is not None:
            return result


def _start_scheduler(app, cfg):
    import schedule

    def run_schedule():
        from compass.scheduler.tasks import DailyAnalysisTask

        logger.info("Scheduler started, daily run at %02d:%02d", cfg.SCHEDULE_HOUR, cfg.SCHEDULE_MINUTE)
        task = DailyAnalysisTask()
        schedule.every().day.at(f"{cfg.SCHEDULE_HOUR:02d}:{cfg.SCHEDULE_MINUTE:02d}").do(task.run)

        while True:
            schedule.run_pending()
            time.sleep(60)

    if not app.config.get("TESTING"):
        t = threading.Thread(target=run_schedule, daemon=True)
        t.start()
