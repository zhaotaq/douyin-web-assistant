import os
import json
import glob
from app.database import init_db, add_content_to_pool, add_account, get_account, log_interaction

def migrate_content_pools():
    """迁移 homepage_urls.txt 和 comments_pool.txt 到数据库。"""
    print("开始迁移内容池...")
    # 迁移主页链接
    try:
        with open('homepage_urls.txt', 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:
                    add_content_to_pool('homepage_url', url)
        print("迁移 homepage_urls.txt 成功。")
    except FileNotFoundError:
        print("homepage_urls.txt 未找到，跳过。")

    # 迁移评论
    try:
        with open('comments_pool.txt', 'r', encoding='utf-8') as f:
            for line in f:
                comment = line.strip()
                if comment:
                    add_content_to_pool('comment', comment)
        print("迁移 comments_pool.txt 成功。")
    except FileNotFoundError:
        print("comments_pool.txt 未找到，跳过。")
    print("内容池迁移完成。")

def migrate_accounts():
    """从JSON文件迁移账户到数据库。"""
    print("\n开始迁移账户...")
    account_files = glob.glob('cookies/douyin_uploader/accounts/*.json')
    if not account_files:
        print("未找到任何账户JSON文件。")
        return
        
    for file_path in account_files:
        filename = os.path.basename(file_path)
        # 提取用户名，兼容 "凹特慢_backup_20250606_141247.json" 和 "凹特慢.json" 两种格式
        username = filename.split('.json')[0]
        if '_backup_' in username:
            username = username.split('_backup_')[0]

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                cookies_dict = json.load(f)
                add_account(username, cookies_dict)
                print(f"成功迁移账户: {username}")
        except json.JSONDecodeError:
            print(f"警告：文件 {filename} 不是有效的JSON格式，跳过。")
        except Exception as e:
            print(f"迁移账户 {username} 时出错: {e}")
    print("账户迁移完成。")

def migrate_interaction_logs():
    """迁移 processed_videos/*.txt 到数据库。"""
    print("\n开始迁移互动日志...")
    log_files = glob.glob('processed_videos/*.txt')
    if not log_files:
        print("未找到任何互动日志文件。")
        return

    for file_path in log_files:
        filename = os.path.basename(file_path)
        # 从 "西游冒险记_processed.txt" 提取 "西游冒险记"
        username = filename.split('_processed.txt')[0]
        
        account = get_account(username)
        if not account:
            print(f"警告：在数据库中未找到日志对应的账户 '{username}'，跳过文件 {filename}")
            continue

        account_id = account['id']
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                processed_count = 0
                for line in f:
                    video_url = line.strip()
                    if video_url:
                        # 假设所有旧的互动都是 'like'
                        log_interaction(account_id, video_url, 'like')
                        processed_count += 1
            print(f"为账户 '{username}' 迁移了 {processed_count} 条互动日志。")
        except Exception as e:
            print(f"处理文件 {filename} 时出错: {e}")
    print("互动日志迁移完成。")


if __name__ == '__main__':
    print("--- 开始数据迁移脚本 ---")
    
    # 1. 初始化数据库，确保表已创建
    print("步骤 1: 初始化数据库...")
    init_db()
    
    # 2. 迁移内容池
    print("\n步骤 2: 迁移内容池...")
    migrate_content_pools()
    
    # 3. 迁移账户
    print("\n步骤 3: 迁移账户...")
    migrate_accounts()
    
    # 4. 迁移互动日志
    print("\n步骤 4: 迁移互动日志...")
    migrate_interaction_logs()
    
    print("\n--- 数据迁移脚本执行完毕 ---")
    print("请检查上面的输出确认所有数据都已正确迁移。")
    print("确认无误后，您可以安全地删除 'cookies', 'processed_videos', 'homepage_urls.txt', 'comments_pool.txt' 等旧的数据文件和目录。") 