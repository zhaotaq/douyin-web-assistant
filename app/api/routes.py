import os
import random
import json
import re
import time
from pathlib import Path
from flask import Blueprint, jsonify, request, current_app
from app.services import automator
from .. import database as db

# 创建一个名为 'api' 的蓝图
bp = Blueprint('api', __name__)

@bp.route('/tasks', methods=['POST'])
def create_task():
    """接收新任务并将其加入队列。"""
    data = request.get_json()
    if not data or 'urls' not in data or not isinstance(data['urls'], list) or not data['urls']:
        return jsonify({"code": 4001, "error": "请求体必须包含一个非空的 'urls' 列表。"}), 400
    
    debug_mode = data.get('debug', False)
    password = data.get('password', None)
    
    # 如果启用了调试模式，必须验证密码
    if debug_mode:
        ADMIN_PASSWORD = "admin123" # 应该与添加评论的密码一致
        if password != ADMIN_PASSWORD:
            return jsonify({"code": 4031, "error": "调试模式需要有效的管理员密码。"}), 403

    try:
        urls_str = "\\n".join(data['urls'])
        task_id = db.create_task(urls=urls_str)
        return jsonify({
            "code": 0,
            "message": "任务已成功加入队列",
            "data": {"task_id": task_id}
        }), 202
    except Exception as e:
        current_app.logger.error(f"Error adding task to queue: {e}")
        return jsonify({"code": 5001, "error": "将任务添加到队列时发生服务器错误。"}), 500

@bp.route('/status', methods=['GET'])
def get_system_status():
    """获取整个系统的当前状态，包括正在运行的任务和等待队列。"""
    try:
        status_data = db.get_system_status()
        return jsonify({
            "code": 0,
            "message": "Success",
            "data": status_data
        })
    except Exception as e:
        current_app.logger.error(f"Error getting system status: {e}")
        return jsonify({"code": 5002, "error": "获取系统状态时发生服务器错误。"}), 500

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
        db.add_account(username, cookie_list_to_save)
        return jsonify({"code": 0, "message": "Cookie已保存成功！感谢您的贡献！"}), 201

    except Exception as e:
        current_app.logger.error(f"Error saving cookie: {e}")
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
        accounts_from_db = db.get_all_accounts()
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

@bp.route('/add_comments', methods=['POST'])
def add_comments():
    """接收新评论并保存到数据库，需要管理员密码。"""
    data = request.get_json()
    if not data:
        return jsonify({"code": 4001, "error": "请求体不能为空"}), 400

    comments = data.get('comments')
    password = data.get('password')

    # 在这里硬编码一个简单的密码，实际项目中建议从环境变量或配置文件读取
    ADMIN_PASSWORD = "admin123"

    if password != ADMIN_PASSWORD:
        return jsonify({"code": 4031, "error": "密码错误，无权操作"}), 403

    if not comments or not isinstance(comments, list):
        return jsonify({"code": 4002, "error": "评论内容必须是一个非空列表"}), 400
    
    # 过滤掉空字符串
    sanitized_comments = [c.strip() for c in comments if c.strip()]
    if not sanitized_comments:
        return jsonify({"code": 4003, "error": "提交的评论内容均为空"}), 400

    try:
        added_count = db.add_comments_to_pool(sanitized_comments)
        return jsonify({
            "code": 0, 
            "message": f"操作成功！新增 {added_count} 条评论到评论库。",
            "data": {"added_count": added_count}
        })
    except Exception as e:
        current_app.logger.error(f"Error adding comments: {e}")
        return jsonify({"code": 5002, "error": "数据库操作失败"}), 500

@bp.route('/stop_task', methods=['POST'])
def stop_running_task():
    """向后台工作线程发送停止信号。"""
    try:
        automator.stop_worker()
        return jsonify({"code": 0, "message": "已发送停止信号。任务将在当前操作完成后安全退出。"}), 200
    except Exception as e:
        current_app.logger.error(f"Error sending stop signal: {e}")
        return jsonify({"code": 5003, "error": "发送停止信号时发生错误。"}), 500

@bp.route('/task/<int:task_id>', methods=['GET'])
def get_task_details(task_id):
    """获取特定任务的详细信息，主要用于检查最终状态。"""
    try:
        task = db.get_task_by_id(task_id)
        if task:
            return jsonify({"code": 0, "data": dict(task)})
        else:
            return jsonify({"code": 404, "error": "找不到指定ID的任务。"}), 404
    except Exception as e:
        current_app.logger.error(f"Error getting task details for {task_id}: {e}")
        return jsonify({"code": 500, "error": "获取任务详情时发生服务器错误。"}), 500 