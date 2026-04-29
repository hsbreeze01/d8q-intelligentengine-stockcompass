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
    def __init__(self, app=None):
        self.rate_limits = defaultdict(list)
        self.suspicious_ips = defaultdict(int)
        self.banned_ips = {}
        self.config = {
            "RATE_LIMIT_REQUESTS": 60,
            "RATE_LIMIT_WINDOW": 60,
            "SUSPICIOUS_THRESHOLD": 5,
            "BAN_DURATION": 3600,
            "MAX_PATH_LENGTH": 200,
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

        if ip in self.banned_ips:
            if now < self.banned_ips[ip]:
                return jsonify({"error": "Access denied"}), 403
            del self.banned_ips[ip]

        self.rate_limits[ip] = [t for t in self.rate_limits[ip] if now - t < self.config["RATE_LIMIT_WINDOW"]]
        self.rate_limits[ip].append(now)

        if len(self.rate_limits[ip]) > self.config["RATE_LIMIT_REQUESTS"]:
            self.banned_ips[ip] = now + 300
            logger.warning("Rate limit ban: %s", ip)
            return jsonify({"error": "Too many requests"}), 429

        path = request.path
        if len(path) > self.config["MAX_PATH_LENGTH"]:
            return jsonify({"error": "Path too long"}), 414

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
