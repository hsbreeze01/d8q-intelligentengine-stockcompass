#!/usr/bin/python
# -*- coding: UTF-8 -*-

import time
import re
from collections import defaultdict, deque
from flask import request, jsonify, abort
from functools import wraps
import logging
import os
import sys

# 确保能找到security_config模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from security_config import (
        SECURITY_CONFIG, SCAN_PATTERNS, MALICIOUS_UA_PATTERNS,
        HONEYPOT_PATHS, WHITELIST_IPS, WHITELIST_PATHS,
        DANGEROUS_CHARS, SECURITY_HEADERS
    )
except ImportError as e:
    # 如果还是失败，提供默认配置
    print(f"Warning: Could not import security_config: {e}")
    print("Using default security configuration")
    
    SECURITY_CONFIG = {
        'RATE_LIMIT_REQUESTS': 30,
        'RATE_LIMIT_WINDOW': 60,
        'SUSPICIOUS_THRESHOLD': 5,
        'BAN_DURATION': 3600,
        'MAX_PATH_LENGTH': 200,
        'TEMP_BAN_DURATION': 300,
    }
    
    SCAN_PATTERNS = [
        r'\.php$', r'\.asp$', r'\.jsp$', r'\.cgi$',
        r'/admin', r'/wp-admin', r'/phpmyadmin',
        r'\.env$', r'\.git', r'\.\./',
    ]
    
    MALICIOUS_UA_PATTERNS = [
        r'sqlmap', r'nmap', r'nikto', r'scanner',
        r'python-requests/\d+\.\d+\.\d+$', r'^$',
    ]
    
    HONEYPOT_PATHS = ['/admin', '/wp-admin', '/phpmyadmin', '/.env']
    WHITELIST_IPS = ['127.0.0.1', '::1']
    WHITELIST_PATHS = ['/static/', '/favicon.ico']
    DANGEROUS_CHARS = ['../', '<script', 'union select', '%00']
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
    }

logger = logging.getLogger("security_logger")

class SecurityMiddleware:
    def __init__(self, app=None):
        self.app = app
        # IP访问记录 {ip: deque([timestamp, ...])}
        self.ip_requests = defaultdict(lambda: deque(maxlen=100))
        # IP黑名单 {ip: ban_until_timestamp}
        self.ip_blacklist = {}
        # 可疑路径计数 {ip: count}
        self.suspicious_path_count = defaultdict(int)
        
        # 使用配置文件中的参数
        self.config = SECURITY_CONFIG
        self.scan_patterns = SCAN_PATTERNS
        self.malicious_ua_patterns = MALICIOUS_UA_PATTERNS
        self.whitelist_ips = WHITELIST_IPS
        self.whitelist_paths = WHITELIST_PATHS
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        self.app = app
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def is_ip_banned(self, ip):
        """检查IP是否被封禁"""
        if ip in self.ip_blacklist:
            if time.time() < self.ip_blacklist[ip]:
                return True
            else:
                # 解除过期的封禁
                del self.ip_blacklist[ip]
        return False
    
    def ban_ip(self, ip, duration=None):
        """封禁IP"""
        if duration is None:
            duration = self.config['BAN_DURATION']
        
        ban_until = time.time() + duration
        self.ip_blacklist[ip] = ban_until
        logger.warning(f"IP {ip} has been banned until {time.ctime(ban_until)}")
    
    def is_rate_limited(self, ip):
        """检查是否超过速率限制"""
        now = time.time()
        window_start = now - self.config['RATE_LIMIT_WINDOW']
        
        # 清理过期的请求记录
        while self.ip_requests[ip] and self.ip_requests[ip][0] < window_start:
            self.ip_requests[ip].popleft()
        
        # 检查当前窗口内的请求数
        if len(self.ip_requests[ip]) >= self.config['RATE_LIMIT_REQUESTS']:
            return True
        
        # 记录当前请求
        self.ip_requests[ip].append(now)
        return False
    
    def is_suspicious_path(self, path):
        """检查是否为可疑路径"""
        # 检查路径长度
        if len(path) > self.config['MAX_PATH_LENGTH']:
            return True
        
        # 检查扫描模式
        for pattern in self.scan_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                return True
        
        return False
    
    def is_malicious_user_agent(self, user_agent):
        """检查是否为恶意User-Agent"""
        if not user_agent:
            return True
        
        for pattern in self.malicious_ua_patterns:
            if re.search(pattern, user_agent, re.IGNORECASE):
                return True
        
        return False
    
    def before_request(self):
        """请求前检查"""
        ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if ',' in ip:
            ip = ip.split(',')[0].strip()
        
        path = request.path
        user_agent = request.headers.get('User-Agent', '')
        
        # 检查白名单IP
        if ip in self.whitelist_ips:
            return
        
        # 检查白名单路径
        for whitelist_path in self.whitelist_paths:
            if path.startswith(whitelist_path):
                return
        
        # 检查IP是否被封禁
        if self.is_ip_banned(ip):
            logger.warning(f"Blocked banned IP: {ip} accessing {path}")
            abort(403)
        
        # 检查速率限制
        if self.is_rate_limited(ip):
            logger.warning(f"Rate limit exceeded for IP: {ip}")
            self.ban_ip(ip, self.config.get('TEMP_BAN_DURATION', 300))
            abort(429)
        
        # 检查蜜罐路径
        if path in HONEYPOT_PATHS:
            logger.error(f"Honeypot triggered by IP: {ip}, Path: {path}, UA: {user_agent}")
            self.ban_ip(ip)  # 立即封禁
            abort(404)
        
        # 检查可疑路径
        if self.is_suspicious_path(path):
            self.suspicious_path_count[ip] += 1
            logger.warning(f"Suspicious path access from {ip}: {path}")
            
            # 如果可疑访问次数过多，封禁IP
            if self.suspicious_path_count[ip] >= self.config['SUSPICIOUS_THRESHOLD']:
                self.ban_ip(ip)
                logger.error(f"IP {ip} banned for excessive suspicious path access")
                abort(403)
            
            # 对可疑路径返回404而不是403，避免信息泄露
            abort(404)
        
        # 检查恶意User-Agent
        if self.is_malicious_user_agent(user_agent):
            logger.warning(f"Malicious User-Agent from {ip}: {user_agent}")
            self.suspicious_path_count[ip] += 1
            
            if self.suspicious_path_count[ip] >= self.config['SUSPICIOUS_THRESHOLD']:
                self.ban_ip(ip)
                abort(403)
            
            abort(404)
    
    def after_request(self, response):
        """请求后处理"""
        # 添加安全头
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # 隐藏服务器信息
        response.headers.pop('Server', None)
        response.headers.pop('X-Powered-By', None)
        
        return response
    
    def get_security_stats(self):
        """获取安全统计信息"""
        now = time.time()
        active_bans = {ip: ban_time for ip, ban_time in self.ip_blacklist.items() if ban_time > now}
        
        return {
            'active_bans': len(active_bans),
            'banned_ips': list(active_bans.keys()),
            'suspicious_ips': dict(self.suspicious_path_count),
            'total_monitored_ips': len(self.ip_requests)
        }


def require_valid_path(f):
    """装饰器：验证路径合法性"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        path = request.path
        
        # 检查路径中是否包含危险字符
        for char in DANGEROUS_CHARS:
            if char in path:
                logger.warning(f"Dangerous character in path: {path}")
                abort(400)
        
        return f(*args, **kwargs)
    return decorated_function


def honeypot_trap(trap_paths):
    """蜜罐陷阱装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.path in trap_paths:
                ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
                if ',' in ip:
                    ip = ip.split(',')[0].strip()
                
                logger.error(f"Honeypot triggered by IP: {ip}, Path: {request.path}")
                
                # 记录详细信息
                logger.error(f"User-Agent: {request.headers.get('User-Agent', 'Unknown')}")
                logger.error(f"Referer: {request.headers.get('Referer', 'Unknown')}")
                
                # 可以选择封禁IP或返回假数据
                abort(404)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator