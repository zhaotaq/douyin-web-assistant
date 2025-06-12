import threading
import time
import json
import os
import random
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
        # 评论池
        self.comments_pool = self._load_comments()

    def _load_comments(self):
        """加载评论池文件"""
        project_root = Path(__file__).parent.parent.parent
        comments_file = project_root / "comments_pool.txt"
        if not comments_file.exists():
            self._update_log("警告: comments_pool.txt 文件不存在，将无法执行评论操作。")
            return []
        with open(comments_file, 'r', encoding='utf-8') as f:
            # 过滤掉空行和注释行
            comments = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        self._update_log(f"成功加载 {len(comments)} 条评论。")
        return comments

    def _get_random_comment(self) -> str:
        """从评论池中随机获取一条评论"""
        if not self.comments_pool:
            return ""
        return random.choice(self.comments_pool)
    
    def _update_log(self, message):
        """更新任务日志并打印到控制台"""
        print(message)
        task_state['log'] = message

    def _setup_driver(self):
        """初始化Chrome浏览器驱动"""
        self._update_log("正在初始化浏览器驱动...")
        options = webdriver.ChromeOptions()
        # 无头模式可以在此根据环境变量配置
        if os.environ.get('APP_MODE') == 'production':
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--disable-blink-features=AutomationControlled")
        self.driver = webdriver.Chrome(options=options)
        self._update_log("浏览器驱动初始化完成。")

    def _load_cookies(self):
        """根据 self.account 加载对应的cookie文件"""
        self._update_log(f"正在为账户 '{self.account}' 加载Cookie...")

        project_root = Path(__file__).parent.parent.parent
        # 规约修正: 直接从cookies目录下加载以账户名命名的文件
        cookie_file = project_root / "cookies" / f"{self.account}.json"
        
        if not cookie_file.exists():
            self._update_log(f"错误：Cookie文件不存在于: {cookie_file}")
            raise FileNotFoundError(f"未找到指定的Cookie文件！路径: {cookie_file}")

        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies_to_load = json.load(f)
        
        # 规约: Cookie格式现在是用户直接提交的，应该是标准的列表格式
        if not isinstance(cookies_to_load, list):
            raise TypeError(f"Cookie文件 '{self.account}.json' 的格式不正确，应为一个JSON数组。")

        # 需要先访问一下域名，才能设置cookie
        self.driver.get("https://www.douyin.com/")
        
        valid_cookies_added = 0
        for cookie in cookies_to_load:
            if 'name' not in cookie or 'value' not in cookie:
                continue
            if 'domain' in cookie and '.douyin.com' not in cookie['domain']:
                 continue
            
            try:
                if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                    del cookie['sameSite']
                self.driver.add_cookie(cookie)
                valid_cookies_added += 1
            except Exception as e:
                self._update_log(f"警告：添加Cookie时发生错误. 名称: {cookie.get('name')}, 错误: {e}")

        if valid_cookies_added == 0:
            raise Exception("未能加载任何有效的抖音域Cookie。")

        self._update_log(f"成功加载 {valid_cookies_added} 个有效Cookie。正在刷新...")
        self.driver.refresh()
        time.sleep(5)

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
                # 使用字典去重，保持顺序
                unique_video_urls = list(dict.fromkeys([el.get_attribute('href') for el in video_elements if el.get_attribute('href')]))

                self._update_log(f"在主页上发现了 {len(unique_video_urls)} 个视频。")

                for video_url in unique_video_urls:
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
            if self.stop_event.is_set(): break
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
            self._update_log(f"完成第 {i+1}/{scrolls} 次滚动。")

    def _process_video(self, video_url):
        """处理单个视频：点赞和评论"""
        self._update_log(f"--- 开始处理视频: {video_url} ---")
        self.driver.get(video_url)
        time.sleep(random.uniform(3, 5)) # 等待视频页面加载

        # --- 点赞 ---
        self._handle_like()
        
        # --- 评论 ---
        self._handle_comment()

        self._update_log(f"--- 视频处理完成: {video_url} ---\n")

    def _handle_like(self):
        """处理点赞逻辑"""
        try:
            # 使用更稳定的 data-e2e 属性来定位点赞按钮的容器
            like_container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-e2e='video-player-container'] [data-e2e='like-icon-container']"))
            )
            
            # 检查是否已点赞 (已点赞的按钮通常会有一个值为"true"的 'aria-pressed' 属性)
            like_button = like_container.find_element(By.TAG_NAME, "div")
            is_liked = like_button.get_attribute('aria-pressed') == 'true'
            
            if not is_liked:
                self._update_log("视频未点赞，准备执行点赞操作...")
                # 模拟鼠标悬停
                webdriver.ActionChains(self.driver).move_to_element(like_button).perform()
                time.sleep(random.uniform(0.5, 1))
                like_button.click()
                self._update_log("👍 点赞成功！")
                time.sleep(random.uniform(1, 2))
            else:
                self._update_log("✅ 视频已经点过赞，跳过。")

        except Exception as e:
            self._update_log(f"⚠️ 点赞操作失败: {e}")

    def _handle_comment(self):
        """处理评论逻辑"""
        if not self.comments_pool:
            self._update_log("💬 评论池为空，跳过评论。")
            return
        
        try:
            comment_text = self._get_random_comment()
            if not comment_text:
                self._update_log("未获取到评论内容，跳过。")
                return

            self._update_log(f"准备发表评论: '{comment_text}'")

            # 定位评论输入框
            comment_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-e2e='comment-input']"))
            )
            comment_input.click() # 点击以激活输入框
            time.sleep(random.uniform(1, 2))

            # 模拟真人打字
            for char in comment_text:
                comment_input.send_keys(char)
                time.sleep(random.uniform(0.1, 0.3))
            
            # 定位并点击发送按钮
            post_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div[data-e2e='comment-post-button']"))
            )
            post_button.click()
            self._update_log("💬 评论发表成功！")
            time.sleep(random.uniform(2, 3))

        except Exception as e:
            self._update_log(f"⚠️ 评论操作失败: {e}")


def get_current_status():
    """获取当前任务状态和日志, 并返回一个对JSON序列化安全的新字典。"""
    
    # 规约: 检查一个任务线程是否存在且已执行完毕
    if task_state.get('thread') and not task_state['thread'].is_alive() and task_state['status'] == 'running':
        task_state['log'] = "任务已执行完毕或意外终止。"
        task_state['status'] = task_state.get('final_status', 'completed')

    # 规约: 返回一个只包含纯数据的新字典，确保JSON序列化安全
    return {
        'status': task_state.get('status', 'idle'),
        'log': task_state.get('log', '系统准备就绪')
    }

def start_automation_thread(urls: list, account: str) -> bool:
    """在一个新线程中启动自动化任务，并返回是否成功启动"""
    if task_state.get('thread') and task_state['thread'].is_alive():
        task_state['log'] = "无法启动新任务：一个任务正在运行中。"
        return False

    task_state['stop_event'].clear()
    task_state['status'] = 'running'
    task_state['log'] = '任务已接收，正在初始化...'
    
    service = AutomationService(urls=urls, account=account, stop_event=task_state['stop_event'])
    
    task_state['thread'] = threading.Thread(target=service.run)
    task_state['thread'].start()
    return True

def stop_task() -> bool:
    """
    发送停止信号给当前正在运行的任务。
    """
    if not task_state.get('thread') or not task_state['thread'].is_alive():
        task_state['log'] = "当前无任务在运行。"
        return False
    
    task_state['stop_event'].set()
    task_state['log'] = "正在发送停止信号..."
    return True

def start_automation_task(urls: list, account: str):
    """
    (旧的模拟函数，将被替换)
    """
    service = AutomationService(urls, account, task_state['stop_event'])
    service.run() 