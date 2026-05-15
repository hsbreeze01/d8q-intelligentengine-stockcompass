"""策略组引擎 — Flask Blueprint 注册 + 生命周期初始化"""
import logging

logger = logging.getLogger("compass.strategy.app")


def register_blueprints(app):
    """将策略组引擎的 5 个 Blueprint 注册到 Flask 应用"""
    from compass.strategy.routes.strategy_groups import bp as sg_bp
    from compass.strategy.routes.signals import bp as sig_bp
    from compass.strategy.routes.events import bp as evt_bp
    from compass.strategy.routes.industry_sync import bp as ind_bp
    from compass.strategy.routes.strategy_subscription import bp as sub_bp

    app.register_blueprint(sg_bp)
    app.register_blueprint(sig_bp)
    app.register_blueprint(evt_bp)
    app.register_blueprint(ind_bp)
    app.register_blueprint(sub_bp)

    logger.info("策略组引擎 5 个 Blueprint 已注册")


def init_strategy_engine():
    """初始化策略组引擎：建表 + 启动调度器"""
    try:
        from compass.strategy.db import init_tables
        init_tables()
        logger.info("策略组数据库表初始化完成")
    except Exception as exc:
        logger.error("建表失败: %s", exc)

    try:
        from compass.strategy.scheduler import start_scheduler
        start_scheduler()
        logger.info("策略组定时调度器已启动")
    except Exception as exc:
        logger.error("调度器启动失败: %s", exc)

    try:
        from compass.strategy.db import cleanup_stale_runs
        cleanup_stale_runs()
        logger.info("策略组 stale running 记录清理完成")
    except Exception as exc:
        logger.warning("清理 stale running 记录失败: %s", exc)
