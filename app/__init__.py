from flask import Flask, send_from_directory
from flask_cors import CORS

def create_app():
    """
    应用工厂函数, 用于创建和配置Flask应用实例。
    """
    app = Flask(__name__)

    # 规约要求: 为所有 /api/ 开头的路径启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 注册 API 蓝图
    # 我们很快就会在 app/api/routes.py 中创建它
    from .api.routes import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.route('/')
    def serve_index():
        """
        服务于前端应用的入口点 index.html。
        """
        return send_from_directory(app.static_folder, 'index.html')

    return app 