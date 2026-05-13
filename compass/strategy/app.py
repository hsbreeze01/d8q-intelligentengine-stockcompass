"""策略组引擎 — FastAPI 应用创建 + 生命周期"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from compass.strategy.db import init_tables

logger = logging.getLogger("compass.strategy.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表 + 加载调度"""
    # 启动
    logger.info("策略组引擎启动中...")
    try:
        init_tables()
        logger.info("数据库表初始化完成")
    except Exception as exc:
        logger.error("建表失败: %s", exc)

    # 加载定时调度
    try:
        from compass.strategy.scheduler import start_scheduler
        start_scheduler()
        logger.info("定时调度器已启动")
    except Exception as exc:
        logger.error("调度器启动失败: %s", exc)

    yield

    # 关闭
    try:
        from compass.strategy.scheduler import shutdown_scheduler
        shutdown_scheduler()
        logger.info("调度器已关闭")
    except Exception:
        pass
    logger.info("策略组引擎已关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 实例"""
    _configure_logging()

    app = FastAPI(
        title="Strategy Group Engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 健康检查
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "strategy-engine"}

    # 统一错误处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("未处理异常 %s %s: %s", request.method, request.url, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )

    # 注册路由
    from compass.strategy.routes.strategy_groups import router as sg_router
    from compass.strategy.routes.signals import router as sig_router
    from compass.strategy.routes.events import router as evt_router

    app.include_router(sg_router, prefix="/api/strategy", tags=["strategy-groups"])
    app.include_router(sig_router, prefix="/api", tags=["signals"])
    app.include_router(evt_router, prefix="/api", tags=["events"])

    # 行业同步路由
    from compass.strategy.routes.industry_sync import router as ind_router
    app.include_router(ind_router, prefix="/api", tags=["industry-sync"])

    return app


def _configure_logging():
    """配置日志"""
    logging.getLogger("compass.strategy").setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")
    )
    logging.getLogger("compass.strategy").addHandler(handler)


app = create_app()
