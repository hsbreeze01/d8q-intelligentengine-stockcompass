import logging
from flask import Blueprint, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

bp = Blueprint('notify', __name__)
logger = logging.getLogger('compass.notify')

# SMTP config from env
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.qq.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_RECEIVER = os.getenv('SMTP_RECEIVER', '')

@bp.route('/api/notify/email', methods=['POST'])
def send_email():
    """发送邮件"""
    data = request.json
    subject = data.get('subject', 'StockCompass 通知')
    content = data.get('content', '')
    receiver = data.get('receiver', SMTP_RECEIVER)
    
    if not SMTP_USER or not SMTP_PASSWORD:
        return jsonify({'success': False, 'error': 'SMTP未配置'}), 400
    
    if not content:
        return jsonify({'success': False, 'error': '邮件内容为空'}), 400
    
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = receiver
        msg['Subject'] = subject
        
        msg.attach(MIMEText(content, 'html', 'utf-8'))
        
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, receiver, msg.as_string())
        
        return jsonify({'success': True, 'message': '邮件发送成功'})
    except Exception as e:
        logger.error(f'Email send failed: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/notify/email/test', methods=['GET'])
def test_email():
    """测试邮件发送"""
    if not SMTP_USER or not SMTP_PASSWORD:
        return jsonify({'success': False, 'configured': False, 'error': 'SMTP未配置'})
    
    return jsonify({
        'success': True, 
        'configured': True,
        'smtp_server': SMTP_SERVER,
        'smtp_user': SMTP_USER[:3] + '***' if SMTP_USER else ''
    })
