import sqlite3
import json
from datetime import datetime

DB_PATH = 'database.db'

def get_db_connection():
    """获取数据库连接，并启用外键约束。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 让查询结果可以像字典一样访问
    conn.execute("PRAGMA foreign_keys = ON;") # 确保外键约束被强制执行
    return conn

def init_db():
    """
    初始化数据库，创建所有需要的表。
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_pools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pool_type TEXT NOT NULL,
            content TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        );
    """)
    conn.commit()
    conn.close()

def get_all_accounts():
    """从数据库获取所有账户信息。"""
    conn = get_db_connection()
    accounts = conn.execute('SELECT * FROM accounts').fetchall()
    conn.close()
    return accounts

def get_random_comment():
    """从内容池中随机获取一条评论。"""
    conn = get_db_connection()
    comment = conn.execute(
        "SELECT content FROM content_pools WHERE pool_type = 'comment' AND is_active = TRUE ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    conn.close()
    # 如果池为空，返回一个默认值
    return comment['content'] if comment else "太棒了！"

def add_comments_to_pool(comments: list[str]):
    """批量向内容池添加新评论，忽略已存在的评论。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    added_count = 0
    for comment in comments:
        # 使用 INSERT OR IGNORE 来避免因唯一性约束失败而报错
        cursor.execute(
            "INSERT OR IGNORE INTO content_pools (pool_type, content) VALUES (?, ?)",
            ('comment', comment)
        )
        # cursor.rowcount会返回受影响的行数 (1 for insert, 0 for ignore)
        added_count += cursor.rowcount
    conn.commit()
    conn.close()
    return added_count 