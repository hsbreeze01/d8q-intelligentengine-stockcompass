import os
import sys

import logging
import logging.config

logging.config.fileConfig('logging.conf')

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
path = os.path.split(rootPath)[0]
print(curPath,rootPath,path)

sys.path.append(path) # 这句是为了导入_config
sys.path.append(rootPath)

from flask import Flask, request, render_template, session, redirect, jsonify
from flask import url_for
from DailyStockCheckTaskV2 import DailyStockCheckTaskV2
import schedule
import requests
import time
import threading
from buy.DBClient import DBClient
from buy.cache import dicStock
from page import page

from simulation_page import simulation_page
from buy.Config import taskConfig as config
from datetime import datetime, timedelta
from security_middleware import SecurityMiddleware, require_valid_path, honeypot_trap
from flask_compress import Compress
from stats_api import add_stats_routes

app = Flask(__name__)
Compress(app)  # 启用 Gzip 压缩
app.register_blueprint(page)
app.register_blueprint(simulation_page)

app.config['SECRET_KEY'] = 'stock_key_1'

# 初始化安全中间件
security = SecurityMiddleware(app)

logger = logging.getLogger("my_logger")

@app.before_request
def before_request_func():
    logger.debug('Before request')
    # 可以在这里进行一些通用的请求预处理操作，例如记录请求信息
    print(f'Request method: {request.method}, URL: {request.url}')
    print(request.endpoint)
    
    #非公共路由都需要校验
    private_routes = ['/favorite/','/llm/','/tracking/']  # 'static' 为静态资源

    if not any(request.path.startswith(prefix) for prefix in private_routes):
        return  # 放行

    #非注册和登录页，需要校验
    print(f'Request redirect: {request.method}, URL: {request.url}')
    #如果没有session，跳转到登录页
    if session.get('uid') is None:
        # Check if request wants JSON response
        if request.args.get('format') == 'json':
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        return redirect(url_for('login'))
    else:
        last_activity = session.get('last_activity')
        current_time = time.time()
        #如果超过1天没有操作，清除session，跳转到登录页
        if last_activity is None or (current_time - last_activity) > 86400:
            session.clear()
            if request.args.get('format') == 'json':
                return jsonify({'success': False, 'message': 'Authentication required'}), 401
            return redirect(url_for('login'))

        session['last_activity'] = current_time


@app.route('/login',methods=['POST','GET'])
@require_valid_path
def login():
    print(request.endpoint)

    response_type = request.form.get('format', 'html')

    if request.method == 'GET':
        if response_type == 'json':
            return jsonify({'message': 'Please use POST method for login'})
        return render_template('login.html')
    
    logger.debug("login ----- ")
    
    username = request.form['username']
    password = request.form['password']
    logger.debug("login -----%s",username)
    

    mc = DBClient()
    logger.debug("login ----1.1")

    count, user = mc.select_one("SELECT * FROM user WHERE username = %s ", (username,))
    logger.debug("login ----1.2")

    mc.close()

    logger.debug("login ----2")

    if user is None or user['password'] != password:
        msg = "Username or password is incorrect. Please try again."
        logger.debug("login ----3")

        if response_type == 'json':
            return jsonify({'success': False, 'message': msg}), 401
        return render_template('login.html',msg=msg)

    logger.debug("login ----4")

    
#     id        |bigint(20)  |NO  |PRI|                 |auto_incremen
# user_id   |int(11)     |NO  |   |                 |             
# login_time|timestamp   |NO  |   |CURRENT_TIMESTAMP|             
# ip        |varchar(255)|NO  |   |                 |             

    ip = request.remote_addr
    mc = DBClient()
    mc.execute("INSERT INTO login_log (user_id, login_time, ip) VALUES (%s, NOW(), %s)", (user['id'], ip))
    mc.commit()
    mc.close()
    logger.debug("login ----5")
    session['uid'] = user['id']
    session['name'] = username
    session['last_activity'] = time.time()

    if response_type == 'json':
        return jsonify({
            'success': True, 
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'username': username,
                'nickname': user.get('nickname', username)
            }
        })
    return redirect(url_for('index'))

@app.route('/login2', methods=['POST'])
def login2():
    logger.debug("Hello WX ，%s，%s",config.getWx()['appid'],config.getWx()['secret'])

    code = request.json.get('code')
    if not code:
        return jsonify({'success': False, 'message': '缺少 code 参数'}), 400

    # 向微信服务器换取 openid 和 access_token
    url = f'https://api.weixin.qq.com/sns/jscode2session?appid={config.getWx()['appid']}&secret={config.getWx()['secret']}&js_code={code}&grant_type=authorization_code'
    response = requests.get(url)
    data = response.json()
    #{'session_key': 'HUEF9DP6NOiuSGEyRnhegA==', 'openid': 'ohyHK5tc-SiK89zJPL8o156V32ys'}
    if 'openid' not in data:
        logger.error("openid not found in response data")
        return jsonify({'success': False, 'message': '获取 openid 失败', 'error': data}), 400

    openid = data.get('openid')

    #用户注册
    logger.debug("Hello WX ，%s",data)
    mc = DBClient()
    try:
        # Check if the user exists
        count, user = mc.select_one("SELECT * FROM user WHERE username = %s", (openid,))
        if user is None:
            # Create a new user if not exists
            mc.execute("INSERT INTO user (username, password, nickname) VALUES ( %s, %s, %s)", 
                       (openid, f"user_{openid}", f"微信用户_{openid}"))
            mc.commit()

    except Exception as e:
        logger.error("Error processing user: %s", e)
        return jsonify({'success': False, 'message': '用户处理失败', 'error': str(e)}), 500
    finally:
        mc.close()

    #登录
    mc = DBClient()
    logger.debug("login ----1.1")
    count, user = mc.select_one("SELECT * FROM user WHERE username = %s ", (openid,))
    logger.debug("login ----1.2")
    mc.close()

    #记录登录日志
    ip = request.remote_addr
    mc = DBClient()
    mc.execute("INSERT INTO login_log (user_id, login_time, ip) VALUES (%s, NOW(), %s)", (user['id'], ip))
    mc.commit()
    mc.close()

    #记录session
    session['uid'] = user['id']
    session['name'] = user['username']
    session['last_activity'] = time.time()

    # 这里可以进行用户信息的存储和处理
    return jsonify({'success': True, 'message': '登录成功', 'openid': user['username'], 'uid': user['id'], 'nickname': user['nickname']})


@app.route('/logout')
def logout():
    session.clear()
    return render_template('login.html')

@app.route('/register',methods=['POST','GET'])
@require_valid_path
def register():
# id        |bigint(20)  |NO  |PRI|  
# username  |varchar(255)|NO  |UNI|  
# password  |varchar(255)|NO  |   |  
# login_time|timestamp   |NO  |   |CU
# nickname  |varchar(50) |NO  |UNI|  
    # status = request.args.get('status', '0')
    response_type = request.form.get('format', 'html')

    if request.method == 'GET':
        if response_type == 'json':
            return jsonify({'message': 'Please use POST method for registration'})
        return render_template('register.html')
    
    username = request.form['username']
    password = request.form['password']
    nickname = request.form['nickname']

    mc = DBClient()
    count, user = mc.select_one("SELECT * FROM user WHERE username = %s", (username,))
    if user:
        mc.close()
        if response_type == 'json':
            return jsonify({'success': False, 'message': 'Username already exists.'}), 400
        return render_template('register.html', result = 'failed',msg = 'Username already exists.')

    count, nickname_user = mc.select_one("SELECT * FROM user WHERE nickname = %s", (nickname,))
    if nickname_user:
        mc.close()
        if response_type == 'json':
            return jsonify({'success': False, 'message': 'nickname already exists.'}), 400
        return render_template('register.html', result = 'failed',msg = 'nickname already exists.')

    mc.execute("INSERT INTO user (username, password, nickname) VALUES (%s, %s, %s)", (username, password, nickname))
    mc.commit()
    mc.close()

    if response_type == 'json':
        return jsonify({'success': True, 'message': 'Registration successful'})
    return render_template('register.html', result = 'success',msg = 'ok.')

@app.route('/favorite/add', methods=['POST','GET'])
def add_favorite():
    stock_code = request.args.get('stock_code', '0')
    user_id = session['uid']
    response_type = request.args.get('format', 'html')

    if stock_code not in dicStock.data['code'].values:
        if response_type == 'json':
            return jsonify({'success': False, 'error': 'Stock code does not exist'}), 400
        return render_template('error.html', error="Stock code does not exist.")
    
    try:
        mc = DBClient()
        count, favorite = mc.select_one("SELECT * FROM user_stock WHERE user_id = %s AND stock_code = %s", (user_id, stock_code))
        
        if count == 0:
            mc.execute("INSERT INTO user_stock (user_id, stock_code) VALUES (%s, %s)", (user_id, stock_code))
            mc.commit()
            
        if response_type == 'json':
            return jsonify({'success': True, 'message': 'Stock added to favorites'})
    except Exception as e:
        logger.error("Error adding favorite: %s", e)
        if response_type == 'json':
            return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        mc.close()

    return redirect(url_for('index'))

@app.route('/favorite/delete', methods=['POST'])
def delete_favorite():
    stock_code = request.form.get('stock_code')
    user_id = session['uid']
    response_type = request.form.get('format', 'html')
   
    try:
        mc = DBClient()
        mc.execute("DELETE FROM user_stock WHERE user_id = %s AND stock_code = %s", (user_id, stock_code))
        mc.commit()
        if response_type == 'json':
            return jsonify({'success': True, 'message': 'Stock removed from favorites'})
    except Exception as e:
        logger.error("Error deleting favorite: %s", e)
        if response_type == 'json':
            return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        mc.close()

    return redirect(url_for('list_favorites'))

@app.route('/favorite/list', methods=['GET'])
def list_favorites():
    user_id = session.get('uid')
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    response_type = request.args.get('format', 'html')
    
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
        next_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
    except ValueError as ve:
        logger.error(ve)
        if response_type == 'json':
            return jsonify({'error': 'Invalid date format'}), 400
        return render_template('error.html', message="Invalid date format.")

    #查找收藏
    try:
        mc = DBClient()
        sql = f'''
            SELECT 
                a.stock_code,
                b.stock_name,
                b.industry,
                b.last_update_time,
                b.stock_data_daily_update_time,
                COALESCE(c.open, 0) AS open,
                COALESCE(c.close, 0) AS close,
                COALESCE(c.high, 0) AS high,
                COALESCE(c.low, 0) AS low,
                COALESCE(c.volume, 0) AS volume,
                COALESCE(c.turnover, 0) AS turnover,
                COALESCE(c.amplitude, 0) AS amplitude,
                COALESCE(c.change_percentage, 0) AS change_percentage,
                COALESCE(c.change_amount, 0) AS change_amount,
                COALESCE(c.turnover_rate, 0) AS turnover_rate
            FROM 
                user_stock a
                LEFT JOIN dic_stock b ON a.stock_code = b.code
                LEFT JOIN stock_data_daily c ON a.stock_code = c.stock_code AND c.date = '{date}'
            WHERE 
                a.user_id = {user_id};
                '''
        count, favorites = mc.select_many(sql)
    except Exception as e:
        logger.error("Error retrieving favorites: %s", e)
        if response_type == 'json':
            return jsonify({'error': 'Error retrieving favorites'}), 500
        return render_template('favorites.html', stocks=[], error="Error retrieving favorites.")
    finally:
        mc.close()
    
    if count == 0:
        if response_type == 'json':
            return jsonify({'stocks': [], 'message': '您还未添加任何自选'})
        return render_template('favorites.html', stocks=[], error="您还未添加任何自选")
    
    #拼接股票概念数据
    for favorite in favorites:
        stock_code = favorite['stock_code']
        # stock_info = dicStock.data[dicStock.data['code'] == stock_code][['concept']].to_dict('records')
        concepts = dicStock.data[dicStock.data['code'] == stock_code]['concepts'].values[0]
        favorite['concepts'] = concepts

    #根据股票代码合并推荐次数
    stock_codes = [favorite['stock_code'] for favorite in favorites]
    try:
        mc = DBClient()
        stock_codes_str = ','.join([f"'{code}'" for code in stock_codes])
        sql = f"SELECT a.stock_code, count(*) as total FROM stock_analysis a, dic_stock b WHERE a.buy > 0 AND a.stock_code IN ({stock_codes_str}) AND a.record_time = '{date}'  AND a.stock_code = b.code group by a.stock_code ORDER BY b.industry, b.stock_name "
        count, recommended_stocks = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        if response_type == 'json':
            return jsonify({'error': 'Error fetching recommended stocks'}), 500
        return render_template('error.html', message="Error fetching recommended stocks.")
    finally:
        mc.close()

    for favorite in favorites:
        stock_code = favorite['stock_code']
        recommended_stock = next((count for count in recommended_stocks if count['stock_code'] == stock_code), None)
        if recommended_stock:
            favorite['recommended_count'] = recommended_stock['total']
        else:
            favorite['recommended_count'] = 0 #最近1天推荐次数

    #统计推荐次数
    try:
        mc = DBClient()
        # 根据 股票，概念，行业 统计推荐次数
        sql = f"select type, category_name, count(*) as total from stock_analysis_stat where date = '{date}' group by type,category_name"
        count, stat_counts = mc.select_many(sql)
        mc.commit()
    except Exception as ex:
        logger.error(ex)
        mc.rollback()
        if response_type == 'json':
            return jsonify({'error': 'Error fetching industry counts'}), 500
        return render_template('error.html', message="Error fetching industry counts.")
    finally:
        mc.close()

    if response_type == 'json':
        return jsonify({
            'stocks': favorites,
            'stats': stat_counts,
            'prev_date': prev_date,
            'next_date': next_date,
            'date': date
        })
    return render_template('favorites.html', stocks=favorites , stats = stat_counts,prev_date = prev_date,next_date = next_date, date = date)

# 添加蜜罐陷阱路由
@app.route('/admin')
@app.route('/wp-admin')
@app.route('/phpmyadmin')
@app.route('/config.php')
@app.route('/.env')
@app.route('/backup')
@honeypot_trap(['/admin', '/wp-admin', '/phpmyadmin', '/config.php', '/.env', '/backup'])
def honeypot():
    """蜜罐陷阱 - 记录恶意访问"""
    return "Not Found", 404

# 安全状态监控路由
@app.route('/security/status')
@require_valid_path
def security_status():
    """安全状态查看（仅限管理员）"""
    # 简单的管理员验证
    if session.get('name') != 'admin':  # 根据你的管理员逻辑调整
        return "Forbidden", 403
    
    stats = security.get_security_stats()
    return jsonify(stats)

@app.route('/security/dashboard')
@require_valid_path
def security_dashboard():
    """安全监控面板"""
    # 简单的管理员验证
    if session.get('name') != 'admin':
        return "Forbidden", 403
    
    return render_template('security_dashboard.html')

@app.route('/')
@require_valid_path
def index():
    logger.debug("uid %s", session.get('uid'))
    logger.debug("name %s", session.get('name'))
    
    stock_code = request.args.get('code')
    response_type = request.args.get('format', 'html')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 50, type=int)

    if page_size > 100:
        page_size = 100
    elif page_size < 5:
        page_size = 5

    name = session.get('name', 'Guest')

    filtered_stocks = dicStock.data
    if stock_code:
        filtered_stocks = filtered_stocks[filtered_stocks['code'].str.contains(stock_code) | filtered_stocks['stock_name'].str.contains(stock_code)]

    total_records = len(filtered_stocks)
    total_pages = (total_records + page_size - 1) // page_size

    # Handle invalid page numbers
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages

    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    stocks = filtered_stocks.iloc[start_index:end_index]

    stocks_list = []
    for index, row in stocks.iterrows():
        stock = {
            'code': row['code'],
            'stock_name': row['stock_name'],
            'stock_prefix': row['stock_prefix'],
            'latest_price': row['latest_price'],
            'change_60days': row['change_60days'],
            'change_ytd': row['change_ytd'],
            'last_update_time': row['last_update_time'],
            'stock_data_daily_update_time': row['stock_data_daily_update_time'].strftime('%Y-%m-%d %H:%M')
        }
        stocks_list.append(stock)

    if response_type == 'json':
        return jsonify({
            'name': name,
            'stocks': stocks_list,
            'page': page,
            'total_pages': total_pages,
            'total_records': total_records
        })
    return render_template('index.html', name=name, stocks=stocks_list, page=page, total_pages=total_pages, total_records=total_records)


def run_schedule():
    logger.debug("启动股票策略version1.0")
    t = DailyStockCheckTaskV2()
    t.action()
    dicStock.setNeedReload()

    # t.check()

    #定时执行    
    schedule.every().day.at("17:00").do(t.action)
    # schedule.every().day.at("16:54").do(t.check)


    while True:
        schedule.run_pending()
        time.sleep(60)

def is_greater_than_seven(num: int) -> bool:
    """
    Check if input number is greater than 7
    Args:
        num: Input number to check
    Returns:
        bool: True if number is greater than 7, False otherwise
    """
    return num > 7


def ab() ->bool:
    print('1')


if __name__ == '__main__':
    #设置mysql 的RR 为RC
    mc = DBClient()
    mc.execute('SET GLOBAL tx_isolation = "READ-COMMITTED";') 
    mc.commit()
    mc.close()

    # Start the scheduling in a new thread
    schedule_thread = threading.Thread(target=run_schedule)
    schedule_thread.start()

    logger.debug("Hello, Flask!")

    if config.getEnv() == 'dev':
        from werkzeug.serving import make_ssl_devcert
        cert_path = os.path.abspath(os.path.dirname(__file__))
        make_ssl_devcert(cert_path + '/cert', host='yicar.online')
        app.run(host='0.0.0.0', port=443, ssl_context=(cert_path+'/cert.crt', cert_path+'/cert.key'))
    else:
        app.run(host='0.0.0.0', port=config.getHost()['port'],debug=True, use_reloader=False)

    # app.run(host='0.0.0.0', port=443, ssl_context=(cert_path+'/cert.crt', cert_path+'/cert.key'))
    # app.run(host='0.0.0.0', port=config.getHost()['port'],debug=True, use_reloader=False)

    logger.debug("Hello, Flask 2!")
