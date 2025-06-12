import os
import random
import json
import re
import time
from pathlib import Path
from flask import Blueprint, jsonify, request
from app.services import automator
from app.database import get_all_accounts, add_account

# 创建一个名为 'api' 的蓝图
bp = Blueprint('api', __name__)

@bp.route('/status', methods=['GET'])
def get_status():
    """
    获取自动化任务的当前状态。
    状态由 automator 服务提供。
    """
    status_data = automator.get_current_status()
    response_data = {
        "code": 0,
        "message": "Success",
        "data": status_data
    }
    return jsonify(response_data)

@bp.route('/run_task', methods=['POST'])
def run_task():
    """
    启动一个新的自动化任务。
    该接口将自动从数据库中随机选择一个可用账户来执行任务。
    """
    data = request.get_json()
    if not data or 'urls' not in data or not data['urls']:
        return jsonify({"code": 4001, "error": "Request body is invalid or 'urls' is empty."}), 400

    # 重构: 从数据库获取账户列表
    try:
        accounts = get_all_accounts()
        # 仅选择状态为 'active' 的账户
        active_accounts = [acc for acc in accounts if acc['status'] == 'active']

        if not active_accounts:
            return jsonify({"code": 4011, "error": "当前没有任何可用的活动账户来执行任务。"}), 400
            
        # 从活动账户中随机选择一个
        selected_account_row = random.choice(active_accounts)
        account_username = selected_account_row['username']
        
    except Exception as e:
        print(f"Error during account selection from DB: {e}")
        return jsonify({"code": 5003, "error": "在从数据库选择账户时发生内部错误。"}), 500

    urls = data['urls']
    
    # automator.start_automation_thread 后续也需要重构，但目前接口参数（用户名）保持不变
    success = automator.start_automation_thread(urls, account_username)
    
    if success:
        return jsonify({
            "code": 0, 
            "message": f"Task accepted for account '{account_username}' and started in the background."
        }), 202
    else:
        return jsonify({"code": 4009, "error": "A task is already running."}), 409

@bp.route('/stop_task', methods=['POST'])
def stop_task():
    """
    停止当前正在运行的自动化任务。
    """
    success = automator.stop_task()
    if success:
        return jsonify({"code": 0, "message": "Stop signal sent. The task will terminate shortly."})
    else:
        return jsonify({"code": 4010, "error": "No task is currently running."}), 400

@bp.route('/save_cookie', methods=['POST'])
def save_cookie():
    """
    接收用户提交的Cookie数据，自动生成用户名，并将其保存到数据库。
    """
    data = request.get_json()
    # 1. 验证请求体 - 现在只需要 'cookieData'
    if not data or 'cookieData' not in data:
        return jsonify({"code": 4001, "error": "请求体必须包含 'cookieData'。"}), 400

    cookie_data_str = data['cookieData']

    # 2. 验证数据
    if not isinstance(cookie_data_str, str) or not cookie_data_str.strip():
        return jsonify({"code": 4004, "error": "Cookie数据 'cookieData' 不能为空。"}), 400

    # 3. 自动生成用户名
    username = f"user_{int(time.time() * 1000)}"

    # 4. 解析Cookie JSON
    try:
        parsed_data = json.loads(cookie_data_str)
        
        cookie_list_to_save = []
        if isinstance(parsed_data, list):
            cookie_list_to_save = parsed_data
        elif isinstance(parsed_data, dict) and 'cookies' in parsed_data and isinstance(parsed_data['cookies'], list):
            # 支持从 "Cookie-Editor" 插件导出的完整JSON
            cookie_list_to_save = parsed_data['cookies']
        else:
            return jsonify({"code": 4005, "error": "无法识别Cookie数据格式。请确保它是一个JSON数组，或包含'cookies'键的JSON对象。"}), 400

    except json.JSONDecodeError:
        return jsonify({"code": 4006, "error": "Cookie数据格式不是有效的JSON。"}), 400

    # 5. 保存到数据库
    try:
        add_account(username, cookie_list_to_save)
        return jsonify({"code": 0, "message": "Cookie已保存成功！感谢您的贡献！"}), 201

    except Exception as e:
        print(f"Error saving cookie to DB: {e}")
        # 更具体的错误反馈
        if "UNIQUE constraint failed" in str(e):
             return jsonify({"code": 4009, "error": f"用户名 '{username}' 已存在，请稍后再试或联系管理员。"}), 409
        return jsonify({"code": 5001, "error": "保存Cookie到数据库时发生服务器内部错误。"}), 500

@bp.route('/accounts', methods=['GET'])
def get_accounts():
    """
    从数据库获取所有可用的账户列表。
    """
    try:
        accounts_from_db = get_all_accounts()
        # 提取用户名, 保持API响应格式一致
        account_names = [acc['username'] for acc in accounts_from_db]

    except Exception as e:
        print(f"Error getting accounts from DB: {e}")
        return jsonify({
            "code": 5004,
            "error": "从数据库获取账户列表时发生错误。",
            "data": {"count": 0, "accounts": []}
        }), 500
    
    # 去重并排序，保证列表干净且顺序稳定
    unique_accounts = sorted(list(set(account_names)))
    
    response_data = {
        "code": 0,
        "message": "Success",
        "data": {
            "count": len(unique_accounts),
            "accounts": unique_accounts
        }
    }
    return jsonify(response_data) 