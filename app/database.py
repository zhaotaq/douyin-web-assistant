import sqlite3
import json
import os

# 确定数据库文件的路径
# 使用 os.path.abspath 和 os.path.dirname 来构建一个绝对路径
# 这样无论从哪里运行脚本，都能找到正确的位置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'database.db')

def get_db_connection():
    """获取并返回一个数据库连接对象。
    
    该连接配置为使用 sqlite3.Row 作为 row_factory，
    这使得查询结果可以像字典一样通过列名访问，非常方便。
    
    Returns:
        sqlite3.Connection: 数据库连接对象。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    初始化数据库。
    
    连接到数据库并执行预定义的SQL语句来创建所有必需的表。
    如果表已经存在，'CREATE TABLE IF NOT EXISTS' 会防止错误的发生。
    这个函数是幂等的，可以安全地多次运行。
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- 创建 accounts 表 ---
    # 存储用户账号信息，替代原有的 cookies JSON 文件
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        cookies TEXT NOT NULL, -- 存储JSON格式的cookie字符串
        status TEXT DEFAULT 'active', -- 账号状态: active, expired, banned
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login_at TIMESTAMP
    );
    ''')
    print("表 'accounts' 创建成功或已存在。")

    # --- 创建 videos 表 ---
    # 存储每个账号发布的视频数据
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        title TEXT,
        publish_time TIMESTAMP,
        status TEXT DEFAULT 'unpublished', -- 视频状态: unpublished, published, failed
        douyin_video_id TEXT, -- 抖音返回的视频ID
        views INTEGER DEFAULT 0,
        likes INTEGER DEFAULT 0,
        comments INTEGER DEFAULT 0,
        shares INTEGER DEFAULT 0,
        last_updated_at TIMESTAMP,
        FOREIGN KEY (account_id) REFERENCES accounts (id)
    );
    ''')
    print("表 'videos' 创建成功或已存在。")

    # --- 创建 interaction_log 表 ---
    # 记录所有互动日志，替代 processed_videos/*.txt 文件
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS interaction_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        video_url TEXT NOT NULL, -- 被操作的视频URL
        action_type TEXT NOT NULL, -- 'like', 'comment', 'follow'
        action_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(account_id, video_url, action_type),
        FOREIGN KEY (account_id) REFERENCES accounts (id)
    );
    ''')
    print("表 'interaction_log' 创建成功或已存在。")

    # --- 创建 content_pools 表 ---
    # 存储评论和主页链接，替代 comments_pool.txt 和 homepage_urls.txt
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS content_pools (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pool_type TEXT NOT NULL, -- 'comment' 或 'homepage_url'
        content TEXT NOT NULL UNIQUE, -- 内容应唯一
        is_active BOOLEAN DEFAULT TRUE
    );
    ''')
    print("表 'content_pools' 创建成功或已存在。")

    conn.commit()
    conn.close()

# --- Account Functions ---

def add_account(username, cookies_dict):
    """添加一个新账户或更新现有账户的cookies。"""
    conn = get_db_connection()
    cookies_str = json.dumps(cookies_dict)
    try:
        conn.execute(
            "INSERT INTO accounts (username, cookies) VALUES (?, ?)",
            (username, cookies_str)
        )
    except sqlite3.IntegrityError:
        # 如果用户名已存在（UNIQUE约束失败），则更新cookies
        conn.execute(
            "UPDATE accounts SET cookies = ?, last_login_at = CURRENT_TIMESTAMP WHERE username = ?",
            (cookies_str, username)
        )
    conn.commit()
    conn.close()

def get_account(username):
    """根据用户名获取单个账户信息。"""
    conn = get_db_connection()
    account = conn.execute("SELECT * FROM accounts WHERE username = ?", (username,)).fetchone()
    conn.close()
    return account

def get_all_accounts():
    """获取所有账户的列表。"""
    conn = get_db_connection()
    accounts = conn.execute("SELECT id, username, status, last_login_at FROM accounts").fetchall()
    conn.close()
    return accounts

# --- Video Functions ---

def add_or_update_video(account_id, video_data):
    """根据文件路径添加或更新视频数据。"""
    # video_data 是一个包含 title, file_path 等信息的字典
    conn = get_db_connection()
    # 以后可以扩展这个函数以更新更多字段
    conn.execute(
        """
        INSERT INTO videos (account_id, file_path, title, status, last_updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(account_id, file_path) DO UPDATE SET
            title = excluded.title,
            status = excluded.status,
            last_updated_at = CURRENT_TIMESTAMP;
        """,
        (account_id, video_data['file_path'], video_data.get('title'), video_data.get('status', 'unpublished'))
    )
    conn.commit()
    conn.close()

def get_videos_by_account(account_id):
    """根据账户ID获取其所有视频。"""
    conn = get_db_connection()
    videos = conn.execute("SELECT * FROM videos WHERE account_id = ?", (account_id,)).fetchall()
    conn.close()
    return videos

# --- Interaction Log Functions ---

def log_interaction(account_id, video_url, action_type):
    """记录一次互动行为（点赞、评论、关注）。"""
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO interaction_log (account_id, video_url, action_type) VALUES (?, ?, ?)",
            (account_id, video_url, action_type)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # UNIQUE约束失败，意味着已经互动过，忽略即可
        pass
    finally:
        conn.close()

def has_interacted(account_id, video_url, action_type):
    """检查是否已经对特定视频执行过特定类型的互动。"""
    conn = get_db_connection()
    result = conn.execute(
        "SELECT 1 FROM interaction_log WHERE account_id = ? AND video_url = ? AND action_type = ?",
        (account_id, video_url, action_type)
    ).fetchone()
    conn.close()
    return result is not None

# --- Content Pool Functions ---

def add_content_to_pool(pool_type, content):
    """向内容池添加新内容。"""
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO content_pools (pool_type, content) VALUES (?, ?)",
            (pool_type, content)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # 内容已存在，忽略
        pass
    finally:
        conn.close()

def get_random_content(pool_type):
    """从指定类型的内容池中随机获取一条内容。"""
    conn = get_db_connection()
    content = conn.execute(
        "SELECT content FROM content_pools WHERE pool_type = ? AND is_active = TRUE ORDER BY RANDOM() LIMIT 1",
        (pool_type,)
    ).fetchone()
    conn.close()
    return content['content'] if content else None

def get_all_content_by_type(pool_type):
    """获取指定类型的所有内容"""
    conn = get_db_connection()
    content_list = conn.execute(
        "SELECT content FROM content_pools WHERE pool_type = ?",
        (pool_type,)
    ).fetchall()
    conn.close()
    return [item['content'] for item in content_list]

# 接下来将在这里添加数据操作函数... 