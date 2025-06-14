import os
from app import create_app
from app.database import init_db
from app.services import automator

# 在运行应用前，先确保数据库已初始化
print("Initializing database...")
init_db()
print("Database check complete.")

# --- 应用模式配置 ---
# 设置为 'production'，应用将默认以无头模式运行。
# 要在开发时看到浏览器窗口，请将此行改为 APP_MODE = 'development'
APP_MODE = 'production'
os.environ['APP_MODE'] = APP_MODE
print(f"Application is running in '{APP_MODE}' mode.")

# --- WebDriver配置 ---
# 为webdriver-manager设置国内镜像源，以解决网络问题
WDM_CHROMEDRIVER_URL = 'https://registry.npmmirror.com/-/binary/chromedriver'
os.environ['WDM_CHROMEDRIVER_URL'] = WDM_CHROMEDRIVER_URL
print(f"WebDriver download mirror set to: {os.environ['WDM_CHROMEDRIVER_URL']}")


app = create_app()

if __name__ == '__main__':
    # 仅在开发模式下开启Flask的Debug模式
    is_debug_mode = (APP_MODE == 'development')
    
    # use_reloader=False 是必须的，因为重载器会创建两个进程，导致工作线程运行两次
    app.run(debug=is_debug_mode, use_reloader=False, host='0.0.0.0', port=5000)

    # Flask 开发服务器默认监听在 127.0.0.1:5000
    # debug=True 可以在代码修改后自动重载，方便开发 