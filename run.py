from app import create_app

app = create_app()

if __name__ == '__main__':
    # Flask 开发服务器默认监听在 127.0.0.1:5000
    # debug=True 可以在代码修改后自动重载，方便开发
    app.run(debug=True) 