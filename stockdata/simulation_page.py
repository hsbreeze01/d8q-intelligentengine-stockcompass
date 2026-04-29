from flask import Flask, request, render_template, session, redirect, jsonify
from flask import Blueprint
from buy.DBClient import DBClient
import json
from decimal import Decimal
from buy.cache.DicStockFactory import dicStock
from main_simulation import *
from datetime import datetime

simulation_page = Blueprint('simulation_page', __name__)

@simulation_page.route('/simulation/list/<code>', methods=['GET'])
def simulation_list_page(code):
    print("uid", session.get('uid'))
    uid = session.get('uid')

    result = simulation_list(code,1)
    
    return render_template('simulation_decide.html', code=code, data=result)

#检查交易完成的情况
@simulation_page.route('/simulation/deal/<code>', methods=['POST','GET'])
def simulation_deal_page(code):
    uid = session.get('uid')
    status = request.args.get('status', '0')

    # simulation_gen(code,uid)
    # simulation_buy(code,uid)
    # simulation_sell(code,uid)

    code, deals, total_profit = simulation_deal(code,1,status)

    
    return render_template('simulation_deal.html', code=code, data=deals, total_profit=total_profit)


# 用户股票跟踪功能实现

# 1. 查询 - 显示用户跟踪的股票列表
@simulation_page.route('/tracking/list', methods=['GET'])
def tracking_list():
    uid = session.get('uid')
    format_type = request.args.get('format', 'html')
    
    try:
        mc = DBClient()
        sql = "select a.*,b.stock_name from user_stock_tracking a, dic_stock b where a.stock_code = b.code and a.user_id = %s ORDER BY a.buy_date"
        count, result = mc.select_many(sql, (uid,))
        mc.close()
        
        if format_type == 'json':
            return jsonify({
                'success': True,
                'data': result,
                'count': count
            })
        else:
            return render_template('tracking_list.html', data=result, count=count)
    except Exception as ex:
        if format_type == 'json':
            return jsonify({
                'success': False,
                'message': str(ex)
            }), 500
        else:
            return render_template('tracking_list.html', error=str(ex))

# 2. 添加 - 添加新的股票跟踪记录
@simulation_page.route('/tracking/add', methods=['POST'])
def tracking_add():
    uid = session.get('uid')
    format_type = request.args.get('format', 'html')
    
    try:
        # 获取表单数据
        if request.is_json:
            data = request.get_json()
            stock_code = data.get('stock_code')
            buy_price = data.get('buy_price')
            buy_amount = data.get('buy_amount')
            buy_date = data.get('buy_date')
            stop_loss_pct = data.get('stop_loss_pct')
            current_price = data.get('current_price', buy_price)  # 默认当前价格等于买入价格
        else:
            stock_code = request.form.get('stock_code')
            buy_price = request.form.get('buy_price')
            buy_amount = request.form.get('buy_amount')
            buy_date = request.form.get('buy_date')
            stop_loss_pct = request.form.get('stop_loss_pct')
            current_price = request.form.get('current_price', buy_price)  # 默认当前价格等于买入价格
        
        # 检查必填项
        if not stock_code:
            raise ValueError("Stock code is required")
        if not buy_price:
            raise ValueError("Buy price is required")
        if not buy_amount:
            raise ValueError("Buy amount is required") 
        if not buy_date:
            raise ValueError("Buy date is required")
        if not stop_loss_pct:
            raise ValueError("Stop loss percentage is required")
        
        if not dicStock.isExist(stock_code):
            raise ValueError("股票代码不存在")
        
        # Validate numeric values
        try:
            float(buy_price)
            float(buy_amount) 
            float(stop_loss_pct)
        except ValueError:
            raise ValueError("Price, amount and stop loss must be valid numbers")
        
        if not dicStock.isExist(stock_code):
            raise ValueError("Stock code is not exist")

        # Validate value ranges
        if float(buy_price) <= 0 and float(buy_price) > 10000:
            raise ValueError("Buy price must be greater than 0")
        if float(buy_amount) <= 0 and float(buy_amount) > 100000000:
            raise ValueError("Buy amount must be greater than 0")
        if float(stop_loss_pct) <= 0 or float(stop_loss_pct) >= 100:
            raise ValueError("Stop loss percentage must be between 0 and 100")

        # Validate date format
        try:
            today = datetime.now().date()
            input_date = datetime.strptime(buy_date, '%Y-%m-%d').date()
            if input_date > today:
                raise ValueError("日期不能超过今天")
        except ValueError:
            raise ValueError("无效的日期格式. 请使用 YYYY-MM-DD")

        # Check if current_price is empty, set it to buy_price if it is
        if not current_price or current_price == '':
            current_price = buy_price
        # 计算止损价格
        stop_loss_price = float(buy_price) * (1 - float(stop_loss_pct) / 100)
        
        # 插入数据库
        mc = DBClient()
        sql = """INSERT INTO user_stock_tracking 
                (user_id, stock_code, buy_price, buy_amount, buy_date, stop_loss_pct, current_price, stop_loss_price) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        mc.execute(sql, (uid, stock_code, buy_price, buy_amount, buy_date, stop_loss_pct, current_price, stop_loss_price))
        mc.commit()
        mc.close()
        
        if format_type == 'json':
            return jsonify({
                'success': True,
                'message': '添加成功'
            })
        else:
            return redirect('/tracking/list')
    except Exception as ex:
        if format_type == 'json':
            return jsonify({
                'success': False,
                'message': str(ex)
            }), 500
        else:
            return render_template('tracking_add.html', error=str(ex))

# 3. 更新 - 更新股票跟踪记录
@simulation_page.route('/tracking/update/<int:tracking_id>', methods=['POST'])
def tracking_update(tracking_id):
    uid = session.get('uid')
    format_type = request.args.get('format', 'html')
    
    try:
        # 获取表单数据
        if request.is_json:
            data = request.get_json()
            buy_price = data.get('buy_price')
            buy_amount = data.get('buy_amount')
            buy_date = data.get('buy_date')
            stop_loss_pct = data.get('stop_loss_pct')
            current_price = data.get('current_price')
        else:
            buy_price = request.form.get('buy_price')
            buy_amount = request.form.get('buy_amount')
            buy_date = request.form.get('buy_date')
            stop_loss_pct = request.form.get('stop_loss_pct')
            current_price = request.form.get('current_price')
        
        # 检查必填项
        if not buy_price:
            raise ValueError("Buy price is required")
        if not buy_amount:
            raise ValueError("Buy amount is required") 
        if not buy_date:
            raise ValueError("Buy date is required")
        if not stop_loss_pct:
            raise ValueError("Stop loss percentage is required")

        # Validate numeric values
        try:
            float(buy_price)
            float(buy_amount) 
            float(stop_loss_pct)
        except ValueError:
            raise ValueError("Price, amount and stop loss must be valid numbers")
        
        if not dicStock.isExist(stock_code):
            raise ValueError("股票代码不存在")

        # Validate value ranges
        if float(buy_price) <= 0 and float(buy_price) > 10000:
            raise ValueError("Buy price must be greater than 0")
        if float(buy_amount) <= 0 and float(buy_amount) > 100000000:
            raise ValueError("Buy amount must be greater than 0")
        if float(stop_loss_pct) <= 0 or float(stop_loss_pct) >= 100:
            raise ValueError("Stop loss percentage must be between 0 and 100")

        # Validate date format
        try:
            today = datetime.now().date()
            input_date = datetime.strptime(buy_date, '%Y-%m-%d').date()
            if input_date > today:
                raise ValueError("日期不能超过今天")
        except ValueError:
            raise ValueError("无效的日期格式. 请使用 YYYY-MM-DD")

        if not current_price or current_price == '':
            current_price = buy_price
            
        # 计算止损价格
        stop_loss_price = float(buy_price) * (1 - float(stop_loss_pct) / 100)
        
        # 更新数据库
        mc = DBClient()
        # 首先检查记录是否存在且属于当前用户
        sql = "SELECT * FROM user_stock_tracking WHERE id = %s AND user_id = %s"
        count, record = mc.select_one(sql, (tracking_id, uid))
        
        if count == 0:
            mc.close()
            if format_type == 'json':
                return jsonify({
                    'success': False,
                    'message': '记录不存在或无权限修改'
                }), 403
            else:
                return render_template('tracking_update.html', error='记录不存在或无权限修改')
        
        # 更新记录
        sql = """UPDATE user_stock_tracking 
                SET buy_price = %s, buy_amount = %s, buy_date = %s, 
                    stop_loss_pct = %s, current_price = %s, stop_loss_price = %s 
                WHERE id = %s AND user_id = %s"""
        mc.execute(sql, (buy_price, buy_amount, buy_date, stop_loss_pct, 
                         current_price, stop_loss_price, tracking_id, uid))
        mc.commit()
        mc.close()
        
        if format_type == 'json':
            return jsonify({
                'success': True,
                'message': '更新成功'
            })
        else:
            return redirect('/tracking/list')
    except Exception as ex:
        if format_type == 'json':
            return jsonify({
                'success': False,
                'message': str(ex)
            }), 500
        else:
            return render_template('tracking_update.html', error=str(ex))

# 4. 删除 - 删除股票跟踪记录
@simulation_page.route('/tracking/delete/<int:tracking_id>', methods=['POST', 'GET'])
def tracking_delete(tracking_id):
    uid = session.get('uid')
    format_type = request.args.get('format', 'html')
    
    try:
        mc = DBClient()
        # 首先检查记录是否存在且属于当前用户
        sql = "SELECT * FROM user_stock_tracking WHERE id = %s AND user_id = %s"
        count, record = mc.select_one(sql, (tracking_id, uid))
        
        if count == 0:
            mc.close()
            if format_type == 'json':
                return jsonify({
                    'success': False,
                    'message': '记录不存在或无权限删除'
                }), 403
            else:
                return render_template('tracking_list.html', error='记录不存在或无权限删除')
        
        # 删除记录
        sql = "DELETE FROM user_stock_tracking WHERE id = %s AND user_id = %s"
        mc.execute(sql, (tracking_id, uid))
        mc.commit()
        mc.close()
        
        if format_type == 'json':
            return jsonify({
                'success': True,
                'message': '删除成功'
            })
        else:
            return redirect('/tracking/list')
    except Exception as ex:
        if format_type == 'json':
            return jsonify({
                'success': False,
                'message': str(ex)
            }), 500
        else:
            return render_template('tracking_list.html', error=str(ex))

# 5. 获取单个记录详情
@simulation_page.route('/tracking/detail/<int:tracking_id>', methods=['GET'])
def tracking_detail(tracking_id):
    uid = session.get('uid')
    format_type = request.args.get('format', 'html')
    
    try:
        mc = DBClient()
        sql = "select a.*,b.stock_name from user_stock_tracking a, dic_stock b where a.id = %s AND a.user_id = %s and a.stock_code = b.code"
        count, record = mc.select_one(sql, (tracking_id, uid))
        mc.close()
        
        if count == 0:
            if format_type == 'json':
                return jsonify({
                    'success': False,
                    'message': '记录不存在或无权限查看'
                }), 403
            else:
                return render_template('tracking_detail.html', error='记录不存在或无权限查看')
        
        if format_type == 'json':
            return jsonify({
                'success': True,
                'data': record
            })
        else:
            return render_template('tracking_detail.html', data=record)
    except Exception as ex:
        if format_type == 'json':
            return jsonify({
                'success': False,
                'message': str(ex)
            }), 500
        else:
            return render_template('tracking_detail.html', error=str(ex))



