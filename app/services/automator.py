import threading
import time

# 这是一个简单的内存状态管理器，用于在Web请求之间共享任务状态。
# 在生产环境中，可能会使用更健壮的方案，如Redis或数据库。
task_state = {
    'status': 'idle',  # 'idle', 'running', 'completed', 'failed', 'stopped'
    'log': '系统准备就绪',
    'thread': None,    # 用于持有后台线程的引用
    'stop_event': threading.Event() # 用于通知后台线程停止
}

def get_current_status():
    """获取当前任务状态和日志"""
    return {
        "status": task_state['status'],
        "log": task_state['log']
    }

def start_automation_task(urls: list):
    """
    (伪)自动化任务的执行函数。
    它会更新状态，并模拟一个长时间运行的任务。
    """
    task_state['status'] = 'running'
    try:
        for i, url in enumerate(urls):
            # 检查停止信号
            if task_state['stop_event'].is_set():
                task_state['status'] = 'stopped'
                task_state['log'] = '任务已被用户手动停止'
                return

            log_message = f"正在处理第 {i+1}/{len(urls)} 个URL: {url}"
            print(log_message) # 在服务器控制台打印日志
            task_state['log'] = log_message
            time.sleep(5) # 模拟处理每个URL需要5秒

        task_state['status'] = 'completed'
        task_state['log'] = '所有URL已处理完毕'
    except Exception as e:
        task_state['status'] = 'failed'
        task_state['log'] = f"任务执行失败: {e}"
    finally:
        # 任务结束后，重置停止信号和线程引用
        task_state['stop_event'].clear()
        task_state['thread'] = None

def start_automation_thread(urls: list):
    """在后台线程中启动自动化任务"""
    if task_state.get('thread') and task_state['thread'].is_alive():
        return False # 如果已有任务在运行，则启动失败

    # 在启动新任务前重置状态
    task_state['stop_event'].clear()
    task_state['status'] = 'running'
    task_state['log'] = '任务已开始...'

    # 创建并启动后台线程
    thread = threading.Thread(target=start_automation_task, args=(urls,))
    task_state['thread'] = thread
    thread.start()
    return True # 启动成功

def stop_task():
    """
    发送停止信号给当前正在运行的任务。
    """
    if task_state.get('thread') and task_state['thread'].is_alive():
        task_state['stop_event'].set()
        return True # 停止信号已发送
    return False # 没有正在运行的任务 