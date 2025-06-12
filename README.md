# 抖音Web助手 (Douyin Web Assistant) v2.0

![UI Screenshot](app/static/img/screenshot.png) <!-- 您需要自己添加一张UI截图 -->

**抖音Web助手**是一款现代化的Web应用程序，旨在自动化常见的抖音网页操作，如批量点赞和评论。项目采用前后端分离架构，通过一个简洁直观的Web界面和一套RESTful API来控制后台的Selenium自动化任务。

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-2.x-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](https://opensource.org/licenses/MIT)
[![GitHub Repo](https://img.shields.io/badge/github-repo-blue)](https://github.com/zhaotaq/douyin-web-assistant)

---

## ✨ 核心功能

*   **现代化Web界面**: 提供一个干净、响应式的单页应用(SPA)，用于提交Cookie、发起任务和实时监控。
*   **数据库驱动**: 采用 **SQLite** 作为统一数据后端，持久化存储用户账户、Cookie及操作日志，告别繁琐的本地文件管理。
*   **RESTful API**: 设计清晰的API端点，严格遵循JSON格式进行数据交换，易于集成和二次开发。
*   **后台异步任务**: 自动化任务在独立的后台线程中运行，确保API服务无阻塞，可处理耗时操作。
*   **实时状态监控**: 可随时通过API查询自动化任务的运行状态 (`运行中`, `已完成`, `失败`, `待命`) 和实时日志。
*   **共享池机制**: 用户通过提交Cookie加入共享池，池中拥有可用账户时，任务功能自动解锁，鼓励协作。
*   **智能操作与风控**:
    *   从内容池中随机选取评论，模拟真人行为。
    *   通过数据库记录已处理过的视频，避免重复操作，降低账户风险。
    *   内置详细的Cookie获取教程，引导用户安全操作。

## 🏛️ 项目架构

项目采用经典的三层架构，实现了彻底的前后端分离：

1.  **前端 (Browser)**: 一个静态的单页面应用 (`app/static/index.html`)，使用原生JavaScript (ES6+)和`fetch` API与后端通信。
2.  **后端 (Flask API Server)**: 一个Python Flask应用，提供RESTful API来接收前端指令，并通过CORS支持跨域请求。它负责管理后台任务的生命周期。
3.  **数据与服务层 (SQLite & Services)**:
    *   **数据库**: 使用SQLite (`database.db`) 存储所有持久化数据。
    *   **服务层**: 封装了核心业务逻辑，包括数据库交互 (`database.py`) 和通过Selenium控制浏览器的自动化核心 (`automator.py`)。

## 📁 项目结构

```
douyin-web-assistant/
├── app/                      # 核心应用目录
│   ├── api/                  # API蓝图
│   │   └── routes.py         # API路由定义
│   ├── services/             # 业务逻辑
│   │   └── automator.py      # 封装Selenium自动化逻辑
│   ├── static/               # 前端文件 (CSS, JS, Images)
│   │   ├── css/main.css
│   │   ├── js/main.js
│   │   └── index.html
│   └── __init__.py           # Flask应用工厂
├── database.db               # SQLite数据库文件
├── run_db_init.py            # 数据库初始化脚本
├── database.py               # 数据库交互模块
├── requirements.txt          # Python依赖
├── run.py                    # 应用启动脚本
└── README.md                 # 本文档
```

## 🚀 快速开始

### 1. 环境准备

*   安装 [Python 3.8+](https://www.python.org/downloads/)
*   安装 [Google Chrome](https://www.google.com/chrome/) 浏览器
*   安装与Chrome版本完全匹配的 [ChromeDriver](https://googlechromelabs.github.io/chrome-for-testing/)，并将其路径添加到系统 `PATH` 环境变量中。

### 2. 安装与配置

1.  **克隆仓库**
    ```bash
    git clone https://github.com/zhaotaq/douyin-web-assistant.git
    cd douyin-web-assistant
    ```

2.  **安装依赖**
    ```bash
    pip install -r requirements.txt
    ```

3.  **初始化数据库**
    首次运行时，需要创建数据库表结构。
    ```bash
    python run_db_init.py
    ```
    这将在项目根目录生成一个 `database.db` 文件。

### 3. 运行

1.  **启动后端服务**
    ```bash
    python run.py
    ```
    服务将默认在 `http://127.0.0.1:5000` 上运行。

2.  **访问前端页面**
    在浏览器中打开 **`http://127.0.0.1:5000`** 即可访问Web应用。

## 📋 API 接口说明 (v2.0)

所有API都以 `/api` 为前缀，并遵循统一的JSON响应格式。

*   **成功**: `{"code": 0, "message": "Success", "data": {...}}`
*   **失败**: `{"code": <error_code>, "error": "<error_message>"}`

---

#### `GET /api/accounts`

*   **描述**: 获取共享池中所有可用账户的数量。
*   **响应**:
    ```json
    {
      "code": 0, "message": "Success",
      "data": { "count": 5 }
    }
    ```

---

#### `POST /api/save_cookie`

*   **描述**: 接收用户提交的Cookie，并存入数据库。
*   **请求体**:
    ```json
    {
      "cookieData": "[{...}]"
    }
    ```

---

#### `GET /api/status`

*   **描述**: 获取当前自动化任务的状态和最新日志。
*   **响应**:
    ```json
    {
      "code": 0, "message": "Success",
      "data": {
        "status": "idle" | "running" | "completed" | "failed" | "stopped",
        "log": "最新的日志信息..."
      }
    }
    ```

---

#### `POST /api/run_task`

*   **描述**: 启动一个新的自动化任务。
*   **请求体**:
    ```json
    {
      "urls": ["https://www.douyin.com/user/..."]
    }
    ```
*   **响应 (202 Accepted)**: `{"code": 0, "message": "Task accepted."}`

---

#### `POST /api/stop_task`

*   **描述**: 请求停止当前正在运行的任务。
*   **响应**: `{"code": 0, "message": "Stop signal sent."}`

## 🤝 如何贡献

我们欢迎任何形式的贡献！请遵循标准的GitHub Flow：

1.  为您的功能或修复在[Issues](https://github.com/zhaotaq/douyin-web-assistant/issues)中创建一个问题。
2.  从 `main` 分支创建一个新的特性分支 (`feature/<issue_no>-description`)。
3.  完成开发和测试后，提交一个Pull Request到 `main` 分支。
4.  确保您的代码遵循项目规范，并通过所有测试。

## 📄 License

该项目根据 [MIT License](LICENSE) 授权。