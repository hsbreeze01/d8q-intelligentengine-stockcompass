"""策略组引擎启动脚本"""
import uvicorn


def main():
    uvicorn.run(
        "compass.strategy.app:app",
        host="0.0.0.0",
        port=8090,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
