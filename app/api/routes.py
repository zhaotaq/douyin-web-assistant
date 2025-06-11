import os
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

    urls = data['urls']
    
    # 尝试在后台启动任务
    success = automator.start_automation_thread(urls)
    
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

@bp.route('/accounts', methods=['GET'])
def get_accounts():
    """
    获取所有可用的账户列表。
    账户列表是通过递归扫描 'cookies' 目录下的文件名得出的。
    """
    COOKIES_DIR = 'cookies'
    accounts = []
    try:
        # 使用 os.walk 进行递归遍历，找到所有子目录中的文件
        for root, dirs, files in os.walk(COOKIES_DIR):
            for filename in files:
                # 我们假设 cookie 文件以 .txt 或 .json 结尾
                if filename.endswith(('.txt', '.json')):
                    # 移除文件扩展名作为账户名
                    account_name = os.path.splitext(filename)[0]
                    # 根据旧文件格式，移除可能存在的 '_processed' 后缀
                    if account_name.endswith('_processed'):
                        account_name = account_name.replace('_processed', '')
                    accounts.append(account_name)

    except FileNotFoundError:
        # 如果 cookies 目录不存在，则日志中记录，并返回空列表
        print(f"警告: Cookie 目录 '{COOKIES_DIR}' 未找到。")
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