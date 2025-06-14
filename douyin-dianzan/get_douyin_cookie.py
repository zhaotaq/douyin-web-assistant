import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.append(str(Path(__file__).parent))

from conf import BASE_DIR
from main import douyin_setup

if __name__ == '__main__':
    try:
        # 确保目录存在
        cookies_dir = BASE_DIR / "cookies" / "douyin_uploader"
        cookies_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置账号文件路径
        account_file = cookies_dir / "account.json"
        print(f"[DEBUG] Cookie文件将保存到: {account_file}")
        
        # 运行设置
        cookie_setup = asyncio.run(douyin_setup(str(account_file), handle=True))
        
        if cookie_setup:
            print("[SUCCESS] Cookie获取成功！")
        else:
            print("[ERROR] Cookie获取失败！")
    except Exception as e:
        print(f"[ERROR] 发生错误: {str(e)}") 