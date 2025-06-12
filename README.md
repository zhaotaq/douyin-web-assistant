# 抖音Web助手 (Douyin Web Assistant)

这是一个基于Web的抖音自动化工具，旨在简化和自动化常见的抖音网页版操作，如批量点赞和评论。它通过一个简洁的Web界面和一套RESTful API来控制，将复杂的Selenium操作封装在后台服务中。

## ✨ 功能特性

- **Web用户界面**: 提供一个简单的SPA (`index.html`)，用于发起任务、查看状态和管理账户。
- **RESTful API**: 设计清晰的API端点，方便与其他程序集成。
- **后台任务**: 自动化任务在独立的后台线程中运行，不会阻塞API服务。
- **状态监控**: 可随时通过API查询当前自动化任务的运行状态（如 `运行中`, `已完成`, `失败`）。
- **多账户支持**: 通过在 `cookies/` 目录下放置不同的Cookie文件来轻松切换和管理多个账户。
- **智能操作**:
  - 自动点赞和评论指定用户主页下的视频。
  - 从 `comments_pool.txt` 文件中随机选择评论内容，模拟真人行为。
  - 对已处理过的视频进行记录，避免重复操作。
- **可扩展性**: 清晰的分层架构（API、服务、前端），易于未来扩展新功能。

## 🏛️ 项目架构

项目采用经典的三层架构，实现了前后端分离：

1.  **前端 (Browser)**: 一个静态的单页面应用 (`app/static/index.html`)，使用原生JavaScript和Fetch API与后端通信。
2.  **后端 (Flask API Server)**: 一个Python Flask应用，提供RESTful API来接收前端指令，并管理自动化任务的生命周期。
3.  **自动化服务 (Selenium)**: 核心的自动化逻辑，使用Selenium库来控制一个真实的浏览器实例，执行具体的网页操作。

## 📁 项目结构

```
douyin-web-assistant/
├── app/                        # 核心应用目录
│   ├── api/                    # API蓝图
│   │   └── routes.py           # API路由定义
│   ├── services/               # 业务逻辑
│   │   └── automator.py        # 封装Selenium自动化逻辑
│   ├── static/                 # 前端文件
│   │   ├── css/main.css
│   │   ├── js/main.js
│   │   └── index.html
│   └── __init__.py             # Flask应用工厂
├── cookies/                    # 存放用户Cookie文件
│   └── 你的账户名1.json
│   └── 你的账户名2.json
├── tests/                      # Pytest测试目录
├── comments_pool.txt           # 评论池文件
├── requirements.txt            # Python依赖
├── run.py                      # 应用启动脚本
└── README.md                   # 本文档
```

## 🚀 快速开始

### 1. 环境准备

- 安装 [Python 3.8+](https://www.python.org/downloads/)
- 安装 [Google Chrome](https://www.google.com/chrome/) 浏览器
- 安装 [ChromeDriver](https://googlechromelabs.github.io/chrome-for-testing/) 并确保其路径在系统的 `PATH` 环境变量中。**重要提示**: ChromeDriver的版本必须与你的Chrome浏览器版本完全匹配。

### 2. 安装

1.  **克隆仓库**
    ```bash
    git clone https://github.com/your-username/douyin-web-assistant.git
    cd douyin-web-assistant
    ```

2.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```

### 3. 配置

1.  **添加账户Cookie**
    - 在项目根目录下创建一个 `cookies` 文件夹。
    - 使用浏览器插件（如 [EditThisCookie](https://chromewebstore.google.com/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)）导出你登录抖音后的Cookie。
    - 将导出的Cookie保存为JSON格式的文件，并将其命名为 `你的账户名.json`（例如 `my_account.json`），然后放入 `cookies` 文件夹。
    - 文件名（不含`.json`后缀）将被视为账户名在前端展示。

2.  **配置评论内容**
    - 编辑根目录下的 `comments_pool.txt` 文件。
    - 每行添加一条你希望发布的评论。脚本会自动忽略空行和以 `#` 开头的行。

### 4. 运行

1.  **启动后端服务**
    ```bash
    python run.py
    ```
    服务将默认在 `http://127.0.0.1:5000` 上运行。

2.  **打开前端页面**
    - 在你的浏览器中，直接打开 `app/static/index.html` 文件。
    - 你也可以通过访问 `http://127.0.0.1:5000/static/index.html` 来加载页面。

    > **注意**: 浏览器可能会有安全限制，推荐通过访问Flask服务地址来加载页面，以避免潜在的CORS问题。

## 📋 API 接口说明

所有API都以 `/api` 为前缀。

#### `GET /api/status`
- **描述**: 获取当前自动化任务的状态。
- **响应**:
  ```json
  {
    "code": 0, "message": "Success",
    "data": {
      "status": "idle" | "running" | "completed" | "failed" | "stopped",
      "log": "最新的日志信息"
    }
  }
  ```

#### `GET /api/accounts`
- **描述**: 获取 `cookies/` 目录下所有可用的账户列表。
- **响应**:
  ```json
  {
    "code": 0, "message": "Success",
    "data": {
      "count": 2,
      "accounts": ["你的账户名1", "你的账户名2"]
    }
  }
  ```

#### `POST /api/run_task`
- **描述**: 启动一个新的自动化任务。
- **请求体**:
  ```json
  {
    "urls": ["https://www.douyin.com/user/...", "https://www.douyin.com/user/..."],
    "account": "你的账户名1"
  }
  ```
- **响应 (202 Accepted)**:
  ```json
  { "code": 0, "message": "Task accepted and started in the background." }
  ```

#### `POST /api/stop_task`
- **描述**: 请求停止当前正在运行的任务。
- **响应**:
  ```json
  { "code": 0, "message": "Stop signal sent. The task will terminate shortly." }
  ```

## 🤝 如何贡献

我们欢迎任何形式的贡献！请遵循标准的GitHub Flow：

1.  为你的功能或修复创建一个 [Issue](https://github.com/your-username/douyin-web-assistant/issues)。
2.  从 `develop` 分支创建一个新的特性分支 (`feature/<issue_no>-description`)。
3.  完成开发和测试后，提交一个 [Pull Request](https://github.com/your-username/douyin-web-assistant/pulls) 到 `develop` 分支。
4.  确保你的代码遵循项目规范，并通过所有测试。