import threading
import time
import json
import os
from pathlib import Path # 导入Pathlib
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc

# 这是一个简单的内存状态管理器，用于在Web请求之间共享任务状态。
# 在生产环境中，可能会使用更健壮的方案，如Redis或数据库。
task_state = {
    'status': 'idle',  # 'idle', 'running', 'completed', 'failed', 'stopped'
    'log': '系统准备就绪',
    'thread': None,    # 用于持有后台线程的引用
    'stop_event': threading.Event() # 用于通知后台线程停止
}

class AutomationService:
    """封装了所有Selenium自动化操作的核心服务类"""

    def __init__(self, urls, account, stop_event):
        self.urls = urls
        self.account = account # 保存账户名
        self.stop_event = stop_event
        self.driver = None
        self.processed_videos = set() # 存放在本次任务中处理过的视频ID

    def _update_log(self, message):
        """更新任务日志并打印到控制台"""
        print(message)
        task_state['log'] = message

    def _setup_driver(self):
        """初始化Chrome浏览器驱动"""
        self._update_log("正在初始化浏览器驱动...")
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless') # 暂时禁用无头模式，方便调试
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--disable-blink-features=AutomationControlled") # 防止被检测
        service = ChromeService(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self._update_log("浏览器驱动初始化完成。")

    def _setup_undetected_driver(self):
        """初始化一个增强的、更难被检测到的浏览器驱动，专门用于登录。"""
        self._update_log("正在初始化增强型浏览器驱动...")
        options = uc.ChromeOptions()
        # options.add_argument('--headless') # 获取cookie时不能用无头模式
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        # 不需要手动添加反检测参数，uc库会自动处理
        self.driver = uc.Chrome(options=options)
        self._update_log("增强型浏览器驱动初始化完成。")

    def _load_cookies(self):
        """根据 self.account 加载对应的cookie文件"""
        self._update_log(f"正在为账户 '{self.account}' 加载Cookie以登录...")

        # 使用pathlib构建一个从当前文件位置出发的绝对路径，这比相对路径更可靠
        project_root = Path(__file__).parent.parent.parent
        # 使用传入的账户名动态构建文件名，并确保扩展名为 .json
        cookie_file = project_root / "cookies" / "douyin_uploader" / "accounts" / f"{self.account}.json"
        
        if not cookie_file.exists():
            self._update_log(f"错误：尝试加载Cookie失败，文件不存在于: {cookie_file}")
            raise FileNotFoundError(f"未找到指定的Cookie文件！路径: {cookie_file}")

        with open(cookie_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 兼容两种常见的Cookie格式：直接是列表，或包含在 'cookies' 键中的字典
        cookies_to_load = []
        if isinstance(data, list):
            cookies_to_load = data
        elif isinstance(data, dict) and 'cookies' in data and isinstance(data.get('cookies'), list):
            cookies_to_load = data['cookies']
        else:
            raise TypeError(f"无法识别Cookie文件 '{self.account}.json' 的格式。")

        # 需要先访问一下域名，才能设置cookie
        self.driver.get("https://www.douyin.com/")
        
        valid_cookies_added = 0
        for cookie in cookies_to_load:
            # 1. 验证cookie基本结构
            if 'name' not in cookie or 'value' not in cookie:
                self._update_log(f"警告：跳过一个缺少 'name' 或 'value' 的无效Cookie。")
                continue

            # 2. 主动过滤非抖音域的cookie，这是更稳健的做法
            if 'domain' in cookie and '.douyin.com' not in cookie['domain']:
                 self._update_log(f"警告：跳过一个域不匹配的Cookie. 名称: {cookie.get('name')}, 域: {cookie.get('domain')}")
                 continue
            
            try:
                # 3. 尝试添加cookie，并保留最终的异常捕获作为保险
                # Samesite属性在旧版selenium中可能不存在，或者有不兼容的值
                if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                    del cookie['sameSite']
                self.driver.add_cookie(cookie)
                valid_cookies_added += 1
            except Exception as e:
                self._update_log(f"警告：添加Cookie时发生意外错误. 名称: {cookie.get('name')}, 错误: {e}")

        if valid_cookies_added == 0:
            self._update_log("错误：未能加载任何有效的抖音域Cookie。请检查Cookie文件是否正确或已过期。")
            raise Exception("未能加载任何有效的抖音域Cookie。")

        self._update_log(f"成功加载 {valid_cookies_added} 个有效Cookie。正在刷新页面以应用登录状态...")
        self.driver.refresh() # 刷新页面，让服务器根据新设置的cookie返回登录后的状态
        time.sleep(5) # 等待页面刷新加载

    def run(self):
        """执行自动化任务的主函数"""
        try:
            self._setup_driver()
            self._load_cookies()

            for i, url in enumerate(self.urls):
                if self.stop_event.is_set():
                    self._update_log("任务被用户手动停止。")
                    task_state['status'] = 'stopped'
                    return

                self._update_log(f"正在处理第 {i+1}/{len(self.urls)} 个主页: {url}")
                self.driver.get(url)
                time.sleep(5) # 等待页面加载

                # 模拟向下滚动以加载更多视频
                self._scroll_page()

                # 找到所有视频链接
                video_elements = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/video/"]')
                video_urls = [el.get_attribute('href') for el in video_elements if el.get_attribute('href')]

                self._update_log(f"在主页上发现了 {len(video_urls)} 个视频。")

                for video_url in video_urls:
                    if self.stop_event.is_set():
                        break
                    
                    video_id = video_url.split("/")[-1]
                    if video_id not in self.processed_videos:
                        self._process_video(video_url)
                        self.processed_videos.add(video_id)
                    else:
                        self._update_log(f"视频 {video_id} 已处理过，跳过。")
            
            if not self.stop_event.is_set():
                 task_state['status'] = 'completed'
                 self._update_log("所有任务已成功完成！")

        except Exception as e:
            self._update_log(f"任务执行失败: {e}")
            task_state['status'] = 'failed'
        finally:
            if self.driver:
                self.driver.quit()
            # 任务结束后，重置停止信号和线程引用
            task_state['stop_event'].clear()
            task_state['thread'] = None

    def _scroll_page(self):
        """模拟滚动页面以加载视频"""
        self._update_log("正在向下滚动页面以加载更多视频...")
        scroll_pause_time = 2
        scrolls = 3  # 滚动3次
        for i in range(scrolls):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
            if self.stop_event.is_set(): break

    def _process_video(self, video_url):
        """处理单个视频：点赞和评论"""
        self._update_log(f"正在处理视频: {video_url}")
        self.driver.get(video_url)
        time.sleep(5) # 等待视频页面加载

        # --- 点赞 ---
        try:
            # 使用更稳定的 data-e2e 属性来定位点赞按钮的容器
            like_container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-e2e='video-player-container'] [data-e2e='like-icon']"))
            )
            
            # 检查是否已点赞 (通常已点赞的元素会有一个特定的class或aria-label)
            # 这里我们用一个简化的方式，通过SVG的路径来判断。一个更健壮的方法是检查 'aria-label' 属性
            is_liked = 'Ptzq3' in like_container.get_attribute('innerHTML') # 假设 'Ptzq3' 是红色爱心的某个特征
            
            if not is_liked:
                 # 确保元素是可点击的
                like_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-e2e='video-player-container'] [data-e2e='like-icon']"))
                )
                like_button.click()
                self._update_log("点赞成功！")
                time.sleep(1)
            else:
                self._update_log("视频已经点过赞，跳过。")

        except Exception as e:
            self._update_log(f"点赞失败: {e}")
        
        # --- 评论 ---
        # 实际评论逻辑比较复杂，需要处理登录、输入、点击等，这里暂时只做日志记录
        self._update_log("评论功能待实现。")
        time.sleep(2)


def generate_cookie_file(account_name: str):
    """
    启动一个浏览器会话，让用户手动登录，然后抓取并保存cookie。
    """
    # 这里我们创建一个临时的service实例，因为它只用于本次操作
    temp_service = AutomationService(urls=[], account=account_name, stop_event=threading.Event())
    driver = None
    try:
        temp_service._update_log(f"为账户 '{account_name}' 开始获取Cookie...")
        # 使用新的、更稳定的驱动
        temp_service._setup_undetected_driver()
        driver = temp_service.driver
        
        driver.get("https://creator.douyin.com/")
        
        temp_service._update_log("浏览器已打开，请在创作者中心页面扫描二维码登录。程序将自动检测登录状态...")
        
        # 等待用户登录成功，最长等待5分钟。通过检测URL是否跳转到创作者后台主页来判断，这比检测元素更可靠。
        wait = WebDriverWait(driver, 300, 1) # 等待300秒，每秒检查一次
        wait.until(EC.url_contains("/creator-micro/"))
        
        temp_service._update_log("成功检测到登录！正在保存Cookie...")
        
        # 获取Cookie
        cookies = driver.get_cookies()
        
        # 保存Cookie
        project_root = Path(__file__).parent.parent.parent
        cookie_dir = project_root / "cookies" / "douyin_uploader" / "accounts"
        cookie_dir.mkdir(parents=True, exist_ok=True) # 确保目录存在
        cookie_file = cookie_dir / f"{account_name}.json"

        with open(cookie_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=4)
            
        temp_service._update_log(f"Cookie已成功保存到: {cookie_file}")

    except Exception as e:
        temp_service._update_log(f"获取Cookie失败: {e}")
    finally:
        if driver:
            driver.quit()
        temp_service._update_log("获取Cookie流程结束。")


def get_current_status():
    """获取当前任务状态和日志"""
    return {"status": task_state['status'], "log": task_state['log']}

def start_automation_task(urls: list, account: str):
    """
    (旧的模拟函数，将被替换)
    """
    service = AutomationService(urls, account, task_state['stop_event'])
    service.run()

def start_automation_thread(urls: list, account: str):
    """在后台线程中启动自动化任务"""
    if task_state.get('thread') and task_state['thread'].is_alive():
        return False # 如果已有任务在运行，则启动失败

    # 在启动新任务前重置状态
    task_state['stop_event'].clear()
    task_state['status'] = 'running'
    task_state['log'] = '任务已开始...'

    # 创建并启动后台线程
    thread = threading.Thread(target=start_automation_task, args=(urls, account))
    task_state['thread'] = thread
    thread.start()
    return True # 启动成功

def start_cookie_generation_thread(account_name: str):
    """在后台线程中启动Cookie生成流程，避免阻塞API"""
    # 这个流程是独立的，不应该被现有的任务状态管理所干扰
    thread = threading.Thread(target=generate_cookie_file, args=(account_name,))
    thread.start()
    return True

def stop_task():
    """
    发送停止信号给当前正在运行的任务。
    """
    if task_state.get('thread') and task_state['thread'].is_alive():
        task_state['stop_event'].set()
        return True # 停止信号已发送
    return False # 没有正在运行的任务 