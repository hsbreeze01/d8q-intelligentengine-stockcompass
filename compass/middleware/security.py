import time
import re
import logging
from collections import defaultdict
from flask import request, jsonify

logger = logging.getLogger("compass.security")

SCAN_PATTERNS = [
    r"\.php$", r"\.asp$", r"\.jsp$", r"\.cgi$",
    r"/admin", r"/wp-admin", r"/phpmyadmin",
    r"\.env$", r"\.git", r"\.\./",
]

HONEYPOT_PATHS = ["/admin", "/wp-admin", "/phpmyadmin", "/config.php", "/.env", "/backup"]

MALICIOUS_UA_PATTERNS = [
    r"sqlmap", r"nmap", r"nikto", r"scanner",
    r"python-requests/\d+\.\d+\.\d+$", r"^$",
]

DANGEROUS_CHARS = ["../", "<script", "union select", "%00"]

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
}


class SecurityMiddleware:
    # 47 本机 + 内网信任主机。111.228.13.110 是 d8q-simulator 交易执行终端:
    # collector(21:05 取信号) 与 executor(09:35 结构巡检) 依赖本服务, 一旦被
    # 限速封禁就直接打断次日开盘下单(2026-10-08 事故: 分析任务全量回放触发
    # 200/60s 限流, 111 被封 300s)。它属自有内网机器, 与 47 同等信任。
    WHITELIST_IPS = {"127.0.0.1", "localhost", "47.99.57.152", "111.228.13.110"}

    def __init__(self, app=None):
        self.rate_limits = defaultdict(list)
        self.suspicious_ips = defaultdict(int)
        self.suspicious_seen = {}
        self.banned_ips = {}
        self.config = {
            "RATE_LIMIT_REQUESTS": 200,
            "RATE_LIMIT_WINDOW": 60,
            "SUSPICIOUS_THRESHOLD": 10,
            "SUSPICIOUS_WINDOW": 300,
            "BAN_DURATION": 60,
            "RATE_LIMIT_BAN_DURATION": 300,
            "MAX_PATH_LENGTH": 500,
        }
        if app:
            self.init_app(app)

    def init_app(self, app):
        app.before_request(self._before_request)
        app.after_request(self._after_request)

    def get_client_ip(self):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.remote_addr or "127.0.0.1"

    def _before_request(self):
        ip = self.get_client_ip()
        now = time.time()

        # 内网/本机请求直接放行
        if ip in self.WHITELIST_IPS or request.remote_addr in self.WHITELIST_IPS:
            return None

        if ip in self.banned_ips:
            if now < self.banned_ips[ip]:
                return jsonify({"error": "Access denied"}), 403
            del self.banned_ips[ip]

        self.rate_limits[ip] = [t for t in self.rate_limits[ip] if now - t < self.config["RATE_LIMIT_WINDOW"]]
        self.rate_limits[ip].append(now)

        if len(self.rate_limits[ip]) > self.config["RATE_LIMIT_REQUESTS"]:
            self.banned_ips[ip] = now + self.config["RATE_LIMIT_BAN_DURATION"]
            logger.warning("Rate limit ban: %s", ip)
            return jsonify({"error": "Too many requests"}), 429

        path = request.path
        if len(path) > self.config["MAX_PATH_LENGTH"]:
            return jsonify({"error": "Path too long"}), 414

        # suspicious 分数按窗口衰减: 原实现只累加不清零, 一旦越过阈值便永久
        # 累积(封禁到期后下一请求立即再次触发) —— 正常客户端也会被永久锁死。
        last = self.suspicious_seen.get(ip)
        if last is not None and now - last > self.config["SUSPICIOUS_WINDOW"]:
            self.suspicious_ips[ip] = 0
        self.suspicious_seen[ip] = now

        for pattern in SCAN_PATTERNS:
            if re.search(pattern, path):
                self.suspicious_ips[ip] += 1
                break

        for pattern in DANGEROUS_CHARS:
            if pattern in path:
                self.suspicious_ips[ip] += 3
                break

        ua = request.headers.get("User-Agent", "")
        for pattern in MALICIOUS_UA_PATTERNS:
            if re.search(pattern, ua):
                self.suspicious_ips[ip] += 2
                break

        if self.suspicious_ips[ip] >= self.config["SUSPICIOUS_THRESHOLD"]:
            self.banned_ips[ip] = now + self.config["BAN_DURATION"]
            logger.warning("Suspicious activity ban: %s (score=%d)", ip, self.suspicious_ips[ip])
            return jsonify({"error": "Access denied"}), 403

    def _after_request(self, response):
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

    def get_stats(self):
        return {
            "banned_ips": len(self.banned_ips),
            "suspicious_ips": dict(self.suspicious_ips),
            "active_rate_limits": len(self.rate_limits),
        }
