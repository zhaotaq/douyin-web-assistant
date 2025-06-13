import sqlite3
import json
from datetime import datetime

DB_PATH = 'database.db'

def get_db_connection():
    """获取数据库连接，并启用外键约束。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """
    初始化数据库，创建所有需要的表。
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # accounts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            cookies TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login_at TIMESTAMP
        );
    """)
    print("表 'accounts' 创建成功或已存在。")

    # videos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            title TEXT,
            publish_time TIMESTAMP,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0,
            last_updated_at TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        );
    """)
    print("表 'videos' 创建成功或已存在。")

    # interaction_log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interaction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            video_url TEXT NOT NULL,
            action_type TEXT NOT NULL,
            action_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, video_url, action_type),
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        );
    """)
    print("表 'interaction_log' 创建成功或已存在。")

    # content_pools
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_pools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pool_type TEXT NOT NULL,
            content TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            UNIQUE(pool_type, content)
        );
    """)
    print("表 'content_pools' 创建成功或已存在。")

    # task_queue
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL DEFAULT 'pending',
            urls_json TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            log TEXT
        );
    """)
    print("表 'task_queue' 创建成功或已存在。")

    conn.commit()
    conn.close()

def add_account(username: str, cookies: list):
    cookies_str = json.dumps(cookies)
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO accounts (username, cookies) VALUES (?, ?)",
        (username, cookies_str)
    )
    conn.commit()
    conn.close()

def get_all_accounts():
    """从数据库获取所有账户信息。"""
    conn = get_db_connection()
    accounts = conn.execute('SELECT * FROM accounts').fetchall()
    conn.close()
    return accounts

def get_account_by_username(username: str):
    """通过用户名从数据库获取单个账户信息。"""
    conn = get_db_connection()
    account = conn.execute(
        'SELECT * FROM accounts WHERE username = ?', (username,)
    ).fetchone()
    conn.close()
    return account

def update_account_login_time(account_id: int):
    """更新指定账号的最后登录时间。"""
    conn = get_db_connection()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE accounts SET last_login_at = ? WHERE id = ?",
        (current_time, account_id)
    )
    conn.commit()
    conn.close()

def update_account_status(account_id: int, status: str):
    """更新指定账号的状态。"""
    conn = get_db_connection()
    conn.execute(
        "UPDATE accounts SET status = ? WHERE id = ?",
        (status, account_id)
    )
    conn.commit()
    conn.close()

def get_random_comment():
    """从内容池中随机获取一条评论。"""
    conn = get_db_connection()
    comment = conn.execute(
        "SELECT content FROM content_pools WHERE pool_type = 'comment' AND is_active = TRUE ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    conn.close()
    return comment['content'] if comment else "太棒了！"

def add_comments_to_pool(comments: list[str]):
    """批量向内容池添加新评论，忽略已存在的评论。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    added_count = 0
    for comment in comments:
        cursor.execute(
            "INSERT OR IGNORE INTO content_pools (pool_type, content) VALUES (?, ?)",
            ('comment', comment)
        )
        added_count += cursor.rowcount
    conn.commit()
    conn.close()
    return added_count

# --- Task Queue Functions ---

def add_task_to_queue(urls: list[str], debug: bool = False) -> int:
    """将新任务添加到队列中，并将URL和debug标志包装在JSON中。"""
    task_data = {"urls": urls, "debug": debug}
    urls_json = json.dumps(task_data)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO task_queue (urls_json) VALUES (?)",
        (urls_json,)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def find_next_pending_task():
    """查找并返回队列中最早的一个待处理任务。"""
    conn = get_db_connection()
    task = conn.execute(
        "SELECT * FROM task_queue WHERE status = 'pending' ORDER BY submitted_at ASC LIMIT 1"
    ).fetchone()
    conn.close()
    return task

def get_task_by_id(task_id: int):
    """通过ID获取单个任务的完整信息。"""
    conn = get_db_connection()
    task = conn.execute(
        "SELECT * FROM task_queue WHERE id = ?",
        (task_id,)
    ).fetchone()
    conn.close()
    return task

def update_task_status(task_id: int, status: str, log: str = "", append: bool = False):
    """更新任务的状态、时间和日志。"""
    conn = get_db_connection()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if status == 'running':
        if append:
            # 追加日志，不更新时间和状态
            conn.execute("UPDATE task_queue SET log = log || ? WHERE id = ?", ('\n' + log, task_id))
        else:
            # 设置状态为running，并重写日志
            conn.execute("UPDATE task_queue SET status = ?, started_at = ?, log = ? WHERE id = ?", (status, current_time, log, task_id))
    elif status in ['completed', 'failed', 'stopped']:
        # 终结任务状态，并重写日志
        conn.execute("UPDATE task_queue SET status = ?, completed_at = ?, log = ? WHERE id = ?", (status, current_time, log, task_id))

    conn.commit()
    conn.close()

def get_system_status():
    """获取系统的当前状态，包括正在运行的任务和等待队列。"""
    conn = get_db_connection()
    
    current_task = conn.execute("SELECT id, status, log FROM task_queue WHERE status = 'running'").fetchone()
    
    queue = conn.execute(
        "SELECT id, status FROM task_queue WHERE status = 'pending' ORDER BY submitted_at ASC"
    ).fetchall()
    
    conn.close()
    
    return {
        "current_task": dict(current_task) if current_task else None,
        "queue": [dict(row) for row in queue]
    }

def has_interacted(account_id: int, video_url: str, action_type: str) -> bool:
    """检查数据库中是否已存在特定的互动记录。"""
    conn = get_db_connection()
    result = conn.execute(
        "SELECT 1 FROM interaction_log WHERE account_id = ? AND video_url = ? AND action_type = ?",
        (account_id, video_url, action_type)
    ).fetchone()
    conn.close()
    return result is not None

def log_interaction(account_id: int, video_url: str, action_type: str):
    """向数据库中插入一条新的互动记录，如果已存在则忽略。"""
    conn = get_db_connection()
    conn.execute(
        "INSERT OR IGNORE INTO interaction_log (account_id, video_url, action_type) VALUES (?, ?, ?)",
        (account_id, video_url, action_type)
    )
    conn.commit()
    conn.close() 