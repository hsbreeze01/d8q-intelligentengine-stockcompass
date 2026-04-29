#!/usr/bin/python
# -*- coding: UTF-8 -*-

"""
安全配置文件
"""

# 基础安全配置
SECURITY_CONFIG = {
    # 速率限制
    'RATE_LIMIT_REQUESTS': 30,      # 每分钟最大请求数
    'RATE_LIMIT_WINDOW': 60,        # 时间窗口（秒）
    
    # 可疑行为检测
    'SUSPICIOUS_THRESHOLD': 5,       # 可疑路径访问阈值
    'BAN_DURATION': 3600,           # 封禁时长（秒）
    'MAX_PATH_LENGTH': 200,         # 最大路径长度
    
    # 临时封禁设置
    'TEMP_BAN_DURATION': 300,       # 临时封禁时长（秒）
    
    # 日志设置
    'LOG_SUSPICIOUS_ACTIVITY': True,
    'LOG_BLOCKED_REQUESTS': True,
}

# 常见扫描路径模式（正则表达式）
SCAN_PATTERNS = [
    # 文件扩展名
    r'\.php$', r'\.asp$', r'\.aspx$', r'\.jsp$', r'\.cgi$',
    
    # 管理面板
    r'/admin', r'/wp-admin', r'/administrator', r'/manager',
    r'/phpmyadmin', r'/mysql', r'/pma',
    
    # 配置和备份文件
    r'/config', r'/backup', r'/test', r'/debug',
    r'\.env$', r'\.git', r'\.svn', r'\.htaccess',
    r'\.sql$', r'\.bak$', r'\.old$', r'\.tmp$', r'\.log$',
    
    # API和文档
    r'/api/v\d+', r'/swagger', r'/docs', r'/documentation',
    
    # 常见文件
    r'/robots\.txt', r'/sitemap\.xml', r'/favicon\.ico',
    
    # 上传和shell
    r'/shell', r'/webshell', r'/upload', r'/uploads',
    
    # 目录遍历
    r'\.\./', r'%2e%2e%2f', r'%2e%2e%5c',
    
    # 注入尝试
    r'union.*select', r'script.*alert', r'javascript:',
    
    # 常见漏洞路径
    r'/cgi-bin', r'/fckeditor', r'/editor',
]

# 恶意User-Agent模式
MALICIOUS_UA_PATTERNS = [
    # 扫描工具
    r'sqlmap', r'nmap', r'nikto', r'dirb', r'dirbuster',
    r'gobuster', r'wfuzz', r'burp', r'scanner', r'masscan',
    r'zap', r'w3af', r'skipfish', r'arachni',
    
    # 简单的脚本请求
    r'python-requests/\d+\.\d+\.\d+$',
    r'curl/\d+\.\d+\.\d+$',
    r'wget/\d+\.\d+\.\d+$',
    
    # 空或可疑的User-Agent
    r'^$',  # 空User-Agent
    r'^\s*$',  # 只有空白字符
    r'^Mozilla$',  # 过于简单的Mozilla
]

# 蜜罐路径 - 这些路径会触发立即封禁
HONEYPOT_PATHS = [
    '/admin',
    '/wp-admin',
    '/wp-login.php',
    '/phpmyadmin',
    '/pma',
    '/mysql',
    '/config.php',
    '/configuration.php',
    '/.env',
    '/.git/config',
    '/backup.sql',
    '/database.sql',
    '/shell.php',
    '/webshell.php',
    '/c99.php',
    '/r57.php',
]

# 白名单IP（不受限制的IP地址）
WHITELIST_IPS = [
    '127.0.0.1',
    '::1',
    # 添加你的管理IP
    # '192.168.1.100',
]

# 白名单路径（不进行安全检查的路径）
WHITELIST_PATHS = [
    '/static/',
    '/favicon.ico',
    '/robots.txt',
    '/sitemap.xml',
]

# 危险字符列表
DANGEROUS_CHARS = [
    '../', '..\\', '%2e%2e%2f', '%2e%2e%5c',
    '<script', '</script>', 'javascript:',
    'union select', 'drop table', 'delete from',
    '%00', '\x00',  # 空字节
    '<', '>', '"', "'", '&lt;', '&gt;',
]

# 安全响应头
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';",
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
}

# 错误页面配置
ERROR_PAGES = {
    403: "Access Forbidden",
    404: "Page Not Found", 
    429: "Too Many Requests",
    500: "Internal Server Error",
}