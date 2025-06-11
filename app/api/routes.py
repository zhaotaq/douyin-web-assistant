import os
import random
import json
import re
import time
from pathlib import Path
from flask import Blueprint, jsonify, request
from app.services import automator

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
    该接口将自动从可用的账户池中随机选择一个账户来执行任务。
    """
    data = request.get_json()
    if not data or 'urls' not in data or not data['urls']:
        return jsonify({"code": 4001, "error": "Request body is invalid or 'urls' is empty."}), 400

    # 规约: 不再从请求中获取账户，而是在后台获取账户列表
    try:
        project_root = Path(__file__).parent.parent.parent
        ACCOUNTS_DIR = project_root / 'cookies' / 'douyin_uploader' / 'accounts'
        
        if not os.path.isdir(ACCOUNTS_DIR):
            return jsonify({"code": 5002, "error": "服务器端账户目录配置错误。"}), 500

        valid_accounts = [
            os.path.splitext(f)[0] for f in os.listdir(ACCOUNTS_DIR) 
            if os.path.isfile(os.path.join(ACCOUNTS_DIR, f)) and f.endswith('.json')
        ]

        if not valid_accounts:
            return jsonify({"code": 4011, "error": "当前没有任何可用账户来执行任务。"}), 400
            
        # 规约: 随机选择一个账户
        account = random.choice(valid_accounts)
        
    except Exception as e:
        print(f"Error during account selection: {e}")
        return jsonify({"code": 5003, "error": "在选择账户时发生内部错误。"}), 500

    urls = data['urls']
    
    success = automator.start_automation_thread(urls, account)
    
    if success:
        # 规约: 在返回信息中可以包含本次随机选用的账户名，但这仅用于日志，前端不需要展示
        return jsonify({
            "code": 0, 
            "message": f"Task accepted for account '{account}' and started in the background."
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
        # 可以自定义一个错误码，表示没有任务在运行
        return jsonify({"code": 4010, "error": "No task is currently running."}), 400

@bp.route('/save_cookie', methods=['POST'])
def save_cookie():
    """
    接收用户提交的Cookie数据，并以时间戳为名保存为文件。
    """
    data = request.get_json()
    # 1. 验证请求体
    if not data or 'cookieData' not in data:
        return jsonify({"code": 4001, "error": "请求体必须包含 'cookieData'。"}), 400

    cookie_data_str = data['cookieData']

    # 2. 验证Cookie数据
    if not isinstance(cookie_data_str, str) or not cookie_data_str.strip():
        return jsonify({"code": 4004, "error": "Cookie数据 'cookieData' 不能为空。"}), 400

    # 3. 生成文件名
    # 使用毫秒级时间戳确保文件名唯一
    safe_account_name = str(int(time.time() * 1000))
    
    try:
        # 尝试解析JSON
        parsed_data = json.loads(cookie_data_str)
        
        # 兼容两种格式：直接是Cookie数组，或者是包含 'cookies' 键的JSON对象
        cookie_list_to_save = []
        if isinstance(parsed_data, list):
            cookie_list_to_save = parsed_data
        elif isinstance(parsed_data, dict) and 'cookies' in parsed_data and isinstance(parsed_data['cookies'], list):
            cookie_list_to_save = parsed_data['cookies']
        else:
            return jsonify({"code": 4005, "error": "无法识别Cookie数据格式。请确保它是一个JSON数组，或包含'cookies'键的JSON对象。"}), 400

    except json.JSONDecodeError:
        return jsonify({"code": 4006, "error": "Cookie数据格式不是有效的JSON。"}), 400

    # 4. 保存文件
    try:
        project_root = Path(__file__).parent.parent.parent
        cookie_dir = project_root / "cookies" / "douyin_uploader" / "accounts"
        cookie_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = cookie_dir / f"{safe_account_name}.json"

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(cookie_list_to_save, f, indent=4)
        
        return jsonify({"code": 0, "message": "Cookie for account '{safe_account_name}' saved successfully."}), 201

    except Exception as e:
        print(f"Error saving cookie file: {e}")
        return jsonify({"code": 5001, "error": "保存Cookie文件时发生服务器内部错误。"}), 500

@bp.route('/accounts', methods=['GET'])
def get_accounts():
    """
    获取所有可用的账户列表。
    账户列表是通过扫描 'cookies/douyin_uploader/accounts' 目录下的文件名得出的。
    """
    project_root = Path(__file__).parent.parent.parent
    # 规约: 将路径修改为精确的账户Cookie存放目录
    ACCOUNTS_DIR = project_root / 'cookies' / 'douyin_uploader' / 'accounts'
    
    accounts = []
    try:
        if not os.path.isdir(ACCOUNTS_DIR):
             print(f"警告: 账户Cookie目录 '{ACCOUNTS_DIR}' 不是一个有效的目录。")
             return jsonify({
                "code": 0,
                "message": "Success (directory not found)",
                "data": {"count": 0, "accounts": []}
            })

        # 规约: 不再使用递归的os.walk, 而是直接遍历目标目录
        for filename in os.listdir(ACCOUNTS_DIR):
            # 规约: 确保我们只处理文件, 并且文件以.json结尾
            full_path = os.path.join(ACCOUNTS_DIR, filename)
            if os.path.isfile(full_path) and filename.endswith('.json'):
                account_name = os.path.splitext(filename)[0]
                accounts.append(account_name)

    except FileNotFoundError:
        print(f"警告: 账户Cookie目录 '{ACCOUNTS_DIR}' 未找到。")
        pass
    
    # 去重并排序，保证列表干净且顺序稳定
    unique_accounts = sorted(list(set(accounts)))
    
    response_data = {
        "code": 0,
        "message": "Success",
        "data": {
            "count": len(unique_accounts),
            "accounts": unique_accounts
        }
    }
    return jsonify(response_data) 