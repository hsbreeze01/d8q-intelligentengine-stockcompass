"""SecurityMiddleware 限速/可疑分衰减回归(2026-10-08 事故) —— 走真实 Flask 请求链路。

事故: d8q-simulator(111) 是 compass 下游交易终端, 分析任务全量回放触发
200/60s 限流被封 300s, 打断 collector 取信号与 executor 结构巡检。修复:
1) 白名单加入自有内网交易终端 111.228.13.110;
2) suspicious 分数按 SUSPICIOUS_WINDOW 衰减 —— 原实现只累加不清零, 越过阈值后
   即使封禁到期也会被下一请求立即重新触发(永久锁死)。
"""
import time

from flask import Flask

from compass.middleware.security import SecurityMiddleware

SCAN_PATH = "/.env"          # 命中 SCAN_PATTERNS 的 \.env$
OK_PATH = "/chanlun/signals/600001"
CLIENT_IP = "203.0.113.9"   # TEST-NET-3, 非白名单


def _app():
    app = Flask(__name__)
    mw = SecurityMiddleware(app)

    @app.route("/<path:p>")
    def _echo(p):
        return "ok"

    return app, mw


def _get(app, path, ip, mw=None):
    with app.test_request_context(path, environ_base={"REMOTE_ADDR": ip},
                                  headers={"User-Agent": "d8q-evaluator/1.0"}):
        resp = mw._before_request()
        if resp is not None:
            return resp[1]
        return 200


def test_trading_terminal_111_is_whitelisted():
    app, mw = _app()
    assert "111.228.13.110" in SecurityMiddleware.WHITELIST_IPS
    # 白名单主机即使连打超限请求也不被封
    for _ in range(300):
        assert _get(app, OK_PATH, "111.228.13.110", mw) == 200


def test_non_whitelisted_flood_gets_banned():
    app, mw = _app()
    mw.config["RATE_LIMIT_REQUESTS"] = 5
    codes = [_get(app, OK_PATH, CLIENT_IP, mw) for _ in range(8)]
    assert 429 in codes, "超限那一刻应返回 429"
    assert codes[-1] == 403, "封禁生效后的后续请求应返回 403"
    assert CLIENT_IP in mw.banned_ips


def test_suspicious_score_decays_so_client_is_not_permanently_locked():
    """回归: 原实现只累加不清零 -> 一次误触后该 IP 永久 403。"""
    app, mw = _app()
    for _ in range(12):  # 每请求 +1(命中 \.env$ 扫描模式)
        _get(app, SCAN_PATH, CLIENT_IP, mw)
    assert mw.suspicious_ips.get(CLIENT_IP, 0) >= 10, "应已越过可疑阈值"
    # 模拟窗口过期 + 封禁到期
    mw.suspicious_seen[CLIENT_IP] = time.time() - (mw.config["SUSPICIOUS_WINDOW"] + 5)
    mw.banned_ips.pop(CLIENT_IP, None)
    # 下一请求: 分数应被清零, 且不再 403
    assert _get(app, OK_PATH, CLIENT_IP, mw) == 200
    assert mw.suspicious_ips[CLIENT_IP] == 0


def test_ban_expires_after_rate_limit_ban_duration():
    app, mw = _app()
    mw.config["RATE_LIMIT_REQUESTS"] = 2
    for _ in range(4):
        _get(app, OK_PATH, CLIENT_IP, mw)
    assert CLIENT_IP in mw.banned_ips
    # 封禁到期且限速窗口滑出后 -> 放行
    mw.banned_ips[CLIENT_IP] = time.time() - 1
    mw.rate_limits[CLIENT_IP] = []
    assert _get(app, OK_PATH, CLIENT_IP, mw) == 200