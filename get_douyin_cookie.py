import asyncio
import sys
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.append(str(Path(__file__).resolve().parent))

from app.database import add_account
from main import douyin_setup

def main():
    parser = argparse.ArgumentParser(description="获取抖音Cookie并保存到数据库。")
    parser.add_argument("username", help="要关联此Cookie的账户用户名。")
    args = parser.parse_args()
    
    username = args.username
    print(f"正在为账户 '{username}' 获取Cookie...")

    try:
        # 重构: douyin_setup 不再需要文件路径，它将直接返回 cookie 数据
        # 第二个参数 handle=True 保持不变，意味着它会打开浏览器让用户登录
        cookie_data = asyncio.run(douyin_setup(headless=False, path=None, handle=True))
        
        if cookie_data:
            # 将获取到的 cookie 保存到数据库
            add_account(username, cookie_data)
            print(f"[SUCCESS] 账户 '{username}' 的Cookie获取成功并已保存到数据库！")
        else:
            print("[ERROR]未能获取到Cookie，请重试。")
            
    except Exception as e:
        print(f"[ERROR] 发生严重错误: {str(e)}")

if __name__ == '__main__':
    main() 