import os
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
    """
    # 规约要求: 检查请求体
    data = request.get_json()
    if not data or 'urls' not in data or not data['urls']:
        # 规约要求: 400 Bad Request
        return jsonify({"code": 4001, "error": "Request body is invalid or 'urls' is empty."}), 400

    if 'account' not in data or not data['account']:
        return jsonify({"code": 4002, "error": "'account' is missing from request."}), 400

    urls = data['urls']
    account = data['account']
    
    # 尝试在后台启动任务
    success = automator.start_automation_thread(urls, account)
    
    if success:
        # 规约要求: 202 Accepted
        return jsonify({"code": 0, "message": "Task accepted and started in the background."}), 202
    else:
        # 规约要求: 409 Conflict
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

@bp.route('/login', methods=['POST'])
def login_and_get_cookie():
    """
    启动一个流程来获取新的cookie。
    """
    data = request.get_json()
    if not data or 'account_name' not in data or not data['account_name']:
        return jsonify({"code": 4003, "error": "Request body is invalid or 'account_name' is empty."}), 400

    account_name = data['account_name']
    
    # 检查账户名是否包含无效字符，避免安全问题
    if any(char in account_name for char in r'/\:*?"<>|'):
        return jsonify({"code": 4004, "error": "Account name contains invalid characters."}), 400

    success = automator.start_cookie_generation_thread(account_name)
    
    if success:
        return jsonify({
            "code": 0, 
            "message": "Cookie generation process started. Please login in the new browser window."
        }), 202
    else:
        # 理论上这里很难失败，除非线程创建失败
        return jsonify({"code": 5001, "error": "Failed to start cookie generation process."}), 500

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