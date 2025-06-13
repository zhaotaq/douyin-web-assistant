from flask import Flask, send_from_directory
from flask_cors import CORS
import atexit
from .api import routes as api_routes
from app.services import automator

def create_app():
    """
    应用工厂函数, 用于创建和配置Flask应用实例。
    """
    # 恢复为标准的Flask应用创建方式，它会自动处理static文件夹
    app = Flask(__name__) 

    # 注册蓝图并添加 /api 前缀
    app.register_blueprint(api_routes.bp, url_prefix='/api')

    # 为所有/api/开头的路径启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # --- Worker Thread Management ---
    # Start the background worker thread when the app starts
    automator.worker_thread_manager(action="start", app_context=app.app_context())
    
    # Ensure the worker thread is stopped when the app exits
    atexit.register(lambda: automator.worker_thread_manager(action="stop"))

    @app.route('/')
    def serve_index():
        """
        服务于前端应用的入口点 index.html。
        """
        # Flask会从 'static' 文件夹中寻找 index.html
        return send_from_directory(app.static_folder, 'index.html')

    # 移除错误的静态文件路由，让Flask接管

    return app 