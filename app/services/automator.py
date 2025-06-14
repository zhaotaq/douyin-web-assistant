import asyncio
import threading
import time
import json
import os
import random
import tempfile
import shutil
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from .. import database as db
from datetime import datetime
from playwright.async_api import async_playwright

# --- Global Worker State ---
_worker_thread = None
_stop_event = None
_current_automator = None # 新增一个全局变量来持有当前的automator实例

def worker_thread_manager(action="start", app_context=None):
    """Manages the lifecycle of the background worker thread."""
    global _worker_thread, _stop_event, _current_automator

    if action == "start":
        if _worker_thread is None or not _worker_thread.is_alive():
            _stop_event = threading.Event()
            _worker_thread = threading.Thread(target=queue_worker, args=(app_context,), daemon=True)
            _worker_thread.start()
            print("后台工作线程已启动。")
    elif action == "stop":
        if _worker_thread and _worker_thread.is_alive():
            print("正在请求停止后台工作线程...")
            if _current_automator:
                # 调用automator的stop方法，它会设置内部的停止标志
                asyncio.run(_current_automator.stop())
            if _stop_event:
                _stop_event.set()
            _worker_thread.join(timeout=20) # 增加等待时间
            print("后台工作线程已停止。")
            _current_automator = None

def stop_worker():
    """Public function to signal the worker to stop."""
    global _current_automator, _stop_event
    print("接收到外部停止信号...")
    if _current_automator:
        # 使用 asyncio.run_coroutine_threadsafe 在另一个线程中安全地调用异步函数
        # 但更简单的方式是直接在automator上设置一个同步的标志
        # 这里我们选择在worker循环里检查
        print("正在调用 automator.stop()")
        asyncio.run(_current_automator.stop())
    if _stop_event:
        _stop_event.set()

def _log_to_db(task_id: int, message: str, append: bool = True):
    """Helper function to log messages to the database for a specific task."""
    try:
        # Get the current timestamp to prepend to the message
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        db.update_task_status(task_id, status="running", log=full_message, append=append)
        print(f"[任务 #{task_id}] {message}") # Also print to console
    except Exception as e:
        print(f"Error logging to database: {e}")

class Automator:
    """
    Encapsulates the automation logic for a single task using Playwright.
    An instance of this class will be created for each task processed by the worker.
    """
    def __init__(self, task_id, urls, debug=False):
        self.task_id = task_id
        self.urls = urls
        self.debug = debug
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.stop_requested = asyncio.Event()
        self.temp_cookie_file = None # 用于存储临时cookie文件

    async def run(self):
        """Main execution method for the automation task."""
        success = False
        self.current_account = None
        try:
            self._log("任务处理开始...")
            await self._initialize_playwright()
            self.current_account = await self._login()
            if not self.current_account:
                raise Exception("无法找到可用账号或登录失败。")

            for i, url in enumerate(self.urls):
                if self.stop_requested.is_set():
                    self._log("检测到停止请求，正在中断任务...")
                    break
                self._log(f"正在处理第 {i+1}/{len(self.urls)} 个URL: {url}")
                await self._process_url(url, self.current_account['id'])

            if not self.stop_requested.is_set():
                success = True

        except Exception as e:
            self._log(f"任务执行期间发生严重错误: {e}")
            success = False
        finally:
            await self._cleanup()
            if self.stop_requested.is_set():
                self._log("任务已被用户手动停止。")
                db.update_task_status(self.task_id, 'stopped', log="任务已被用户手动停止。", append=True)
            elif not success:
                self._log("任务因发生错误而失败。")
                db.update_task_status(self.task_id, 'failed', log=f"任务失败。", append=True)
            else:
                self._log("任务成功完成所有操作。")
                db.update_task_status(self.task_id, 'completed', log="任务成功完成。", append=True)

    async def stop(self):
        """Signals the automation task to stop."""
        self._log("接收到停止信号...")
        self.stop_requested.set()

    def _log(self, message):
        """Logs a message for the current task."""
        _log_to_db(self.task_id, message)

    async def _initialize_playwright(self):
        """Initializes the Playwright instance and launches a browser."""
        try:
            self._log("初始化 Playwright...")
            self.playwright = await async_playwright().start()
            self._log("启动浏览器...")
            self.browser = await self.playwright.chromium.launch(
                headless=not self.debug,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self._log("Playwright 初始化成功。")
        except Exception as e:
            self._log(f"Playwright 初始化失败: {e}")
            raise

    def _normalize_cookies(self, cookies: list) -> list:
        """
        Thoroughly normalizes cookies to be compatible with Playwright.
        - Renames 'expirationDate' to 'expires'.
        - Ensures all required fields (name, value, domain, path) are present.
        - Normalizes 'sameSite' attribute.
        """
        normalized = []
        for cookie in cookies:
            # 1. Rename expirationDate to expires
            if 'expirationDate' in cookie:
                cookie['expires'] = cookie.pop('expirationDate')

            # 2. Ensure essential keys exist
            required_keys = ['name', 'value', 'domain', 'path', 'expires']
            missing_keys = [key for key in required_keys if key not in cookie]
            if missing_keys:
                self._log(f"警告: 跳过一个无效的Cookie（缺少关键字段: {', '.join(missing_keys)}）: {cookie}")
                continue
            
            # Set default for path if it's empty
            if not cookie['path']:
                cookie['path'] = '/'

            # 3. Normalize sameSite attribute
            if 'sameSite' in cookie:
                samesite_val = str(cookie['sameSite']).lower()
                if samesite_val in ['no_restriction', 'unspecified', 'none']:
                    cookie['sameSite'] = 'None'
                elif samesite_val == 'lax':
                    cookie['sameSite'] = 'Lax'
                elif samesite_val == 'strict':
                    cookie['sameSite'] = 'Strict'
                else:
                    # If it's an unknown value, Playwright might reject it. Safer to remove.
                    del cookie['sameSite']

            # 4. Ensure expires is a number
            if not isinstance(cookie['expires'], (int, float)):
                try:
                    cookie['expires'] = float(cookie['expires'])
                except (ValueError, TypeError):
                    self._log(f"警告: 跳过一个无效的Cookie（'expires'字段不是有效数字）: {cookie}")
                    continue
            
            normalized.append(cookie)
        
        if not normalized and cookies:
            self._log("警告：所有原始Cookie在清理后均被视为无效。")
        
        return normalized

    async def _login(self):
        """Fetches an account and uses its cookies to log in."""
        self._log("正在尝试登录...")
        accounts = db.get_all_accounts()
        if not accounts:
            self._log("数据库中没有任何可用账号。")
            return None

        account = accounts[0] # 使用第一个可用账号
        self._log(f"选用账号: {account['username']}")

        try:
            # 1. 将从数据库取出的cookie字符串写入一个临时文件
            cookie_data = account['cookies'] # 直接使用从数据库获取的JSON字符串
            
            # 创建一个临时文件来保存cookie
            fd, self.temp_cookie_file = tempfile.mkstemp(suffix=".json", text=True)
            with os.fdopen(fd, 'w') as tmp:
                tmp.write(cookie_data)
            
            self._log(f"Cookie 已临时保存到: {self.temp_cookie_file}")

            # 2. 让Playwright直接从文件加载storage_state
            self.context = await self.browser.new_context(
                storage_state=self.temp_cookie_file,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            self.page = await self.context.new_page()
            
            self._log("正在验证登录状态...")
            await self.page.goto("https://www.douyin.com", timeout=30000)
            await self.page.wait_for_selector('header [data-e2e="user-avatar"]', timeout=15000)
            
            self._log(f"账号 {account['username']} 登录成功。")
            db.update_account_login_time(account['id'])
            return account
        except Exception as e:
            self._log(f"登录失败: {e}。Cookie可能已过期或格式不兼容。")
            db.update_account_status(account['id'], 'expired')
            return None

    async def _process_url(self, url, account_id):
        """
        Navigates to a user's homepage, finds all videos, and interacts with them.
        This logic is transplanted from the local 'auto_manager.py'.
        """
        try:
            self._log(f"导航到用户主页: {url}")
            await self.page.goto(url, timeout=60000, wait_until="networkidle")
            await asyncio.sleep(random.uniform(2, 4))

            # 移植过来的滚动加载逻辑
            self._log("开始滚动页面以加载视频列表...")
            video_urls = await self._scroll_and_collect_videos(url)
            self._log(f"在主页 {url} 上共发现 {len(video_urls)} 个视频。")

            interacted_count = 0
            for i, video_url in enumerate(video_urls):
                if self.stop_requested.is_set():
                    self._log("任务中断，停止处理此主页的剩余视频。")
                    break
                
                self._log(f"--- 开始处理视频 {i+1}/{len(video_urls)} ---")
                
                try:
                    # 检查是否已处理过
                    if db.has_interacted(account_id, video_url, 'like') or db.has_interacted(account_id, video_url, 'comment'):
                        self._log(f"视频 {video_url} 已互动过，跳过。")
                        continue

                    await self.page.goto(video_url, timeout=60000, wait_until="networkidle")
                    await asyncio.sleep(random.uniform(3, 5))
                    
                    # 移植过来的点赞和评论逻辑
                    liked = await self._handle_like()
                    if liked:
                        db.log_interaction(account_id, video_url, 'like')

                    commented = await self._handle_comment(account_id)
                    if commented:
                        db.log_interaction(account_id, video_url, 'comment')
                    
                    if liked or commented:
                        interacted_count += 1

                    self._log(f"--- 视频 {video_url} 处理完毕 ---")
                    await asyncio.sleep(random.uniform(5, 10)) # 模拟观看后的停留

                except Exception as e:
                    self._log(f"处理视频 {video_url} 时发生错误: {e}")
                    continue
            
            self._log(f"在主页 {url} 上成功互动 {interacted_count} 个新视频。")

        except Exception as e:
            self._log(f"处理主页 {url} 失败: {e}")
            raise # Re-raise the exception to be handled by the main run loop

    async def _scroll_and_collect_videos(self, url) -> list[str]:
        """Scrolls the page to load videos and collects their URLs."""
        video_links = set()
        scroll_attempts = 0
        no_new_videos_count = 0
        max_scrolls = 50  # 最大滚动次数

        while scroll_attempts < max_scrolls:
            if self.stop_requested.is_set(): break
            
            initial_count = len(video_links)
            
            # 执行JS获取当前页面所有视频链接
            page_videos = await self.page.eval_on_selector_all(
                '[data-e2e="user-post-item"] a',
                'nodes => nodes.map(n => n.href)'
            )
            video_links.update(page_videos)

            # 检查是否发现了新视频
            if len(video_links) > initial_count:
                no_new_videos_count = 0
            else:
                no_new_videos_count += 1

            # 如果连续3次滚动没有新视频，可能到底了
            if no_new_videos_count >= 3:
                self._log("滚动可能已到达页面底部。")
                break

            # 滚动页面
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            self._log(f"第 {scroll_attempts + 1} 次滚动，已发现 {len(video_links)} 个视频...")
            await asyncio.sleep(random.uniform(2, 4))
            scroll_attempts += 1
        
        return list(video_links)

    async def _handle_like(self) -> bool:
        """
        Checks if a video is already liked and likes it if not.
        Returns True if liked, False otherwise.
        """
        try:
            like_icon_selector = 'span.like-icon.active' # 已点赞的图标选择器
            
            # 使用JS检查是否存在已点赞的图标
            is_liked = await self.page.evaluate(f"!!document.querySelector('{like_icon_selector}')")

            if is_liked:
                self._log("检测到视频已点赞，跳过。")
                return False

            self._log("视频未点赞，准备执行点赞操作...")
            like_button_selector = 'div[data-e2e="video-player-container-like"]'
            await self.page.click(like_button_selector, timeout=10000)
            self._log("👍 点赞成功。")
            await asyncio.sleep(random.uniform(2, 4))
            return True

        except Exception as e:
            self._log(f"点赞操作失败: {e}")
            return False

    async def _handle_comment(self, account_id) -> bool:
        """
        Handles the commenting logic, including checking for duplicates.
        Returns True if commented, False otherwise.
        """
        try:
            # 1. 获取自己的头像，用于防重
            my_avatar_url = await self.page.evaluate('document.querySelector("header [data-e2e=\'user-avatar\'] img").src')
            if not my_avatar_url:
                self._log("无法获取当前用户头像，跳过评论。")
                return False

            # 2. 展开评论区并检查是否已评论
            comment_box_selector = 'div[data-e2e="video-player-container-comment"]'
            await self.page.click(comment_box_selector, timeout=10000)
            self._log("已展开评论区，准备检查重复评论...")
            await asyncio.sleep(random.uniform(2, 3))

            # 滚动并检查所有评论者的头像
            max_scrolls = 10
            is_commented = False
            for _ in range(max_scrolls):
                commenter_avatars = await self.page.eval_on_selector_all(
                    'div[data-e2e="comment-item"] a.Nu66P_ba img',
                    'nodes => nodes.map(n => n.src)'
                )
                if my_avatar_url in commenter_avatars:
                    self._log("检测到本账号已在此视频下评论，跳过。")
                    is_commented = True
                    break
                
                # 滚动评论区
                await self.page.evaluate('document.querySelector("div[data-e2e=\'comment-list-container\']").scrollTop += 500;')
                await asyncio.sleep(random.uniform(1, 2))

            if is_commented:
                return False

            # 3. 执行评论
            self._log("未发现重复评论，准备发表新评论。")
            comment_content = db.get_random_comment()
            if not comment_content:
                self._log("评论池为空，无法评论。")
                return False
            
            self._log(f'选用评论: "{comment_content}"')
            comment_input_selector = 'div[data-e2e="comment-text-input"]'
            await self.page.fill(comment_input_selector, comment_content)
            await asyncio.sleep(random.uniform(1, 2))
            
            # 点击发送
            send_button_selector = 'div[data-e2e="comment-submit-button"]'
            await self.page.click(send_button_selector)
            
            # 检查手机验证码
            try:
                await self.page.wait_for_selector("text=请完成手机验证", timeout=5000)
                self._log("⚠️ 检测到手机验证码！请在1分钟内手动处理。任务将暂停。")
                await asyncio.sleep(60)
                self._log("验证码等待时间结束，继续任务。")
            except Exception:
                pass  # 没有验证码，正常

            self._log("💬 评论成功。")
            await asyncio.sleep(random.uniform(3, 6))
            return True

        except Exception as e:
            self._log(f"评论操作失败: {e}")
            return False

    async def _cleanup(self):
        """Cleans up Playwright resources and temporary files."""
        self._log("开始清理资源...")
        if self.page: await self.page.close()
        if self.context: await self.context.close()
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()

        # 清理临时cookie文件
        if self.temp_cookie_file and os.path.exists(self.temp_cookie_file):
            try:
                os.remove(self.temp_cookie_file)
                self._log(f"已删除临时Cookie文件: {self.temp_cookie_file}")
            except OSError as e:
                self._log(f"删除临时Cookie文件失败: {e}")
        
        self._log("资源清理完毕。")

def queue_worker(app_context):
    """The main loop for the background worker thread."""
    global _stop_event, _current_automator
    with app_context:
        while not _stop_event.is_set():
            task = db.get_pending_task()
            if task:
                print(f"从队列中获取到新任务 #{task['id']}")
                db.update_task_status(task['id'], 'running', "任务已开始处理...", append=False)
                
                # 分割URL
                urls = [url.strip() for url in task['urls'].splitlines() if url.strip()]
                
                # 创建并运行Automator
                _current_automator = Automator(task_id=task['id'], urls=urls, debug=False)
                
                try:
                    # 在线程中运行asyncio事件循环
                    asyncio.run(_current_automator.run())
                except Exception as e:
                    print(f"在任务 #{task['id']} 的asyncio事件循环中发生错误: {e}")
                    _log_to_db(task['id'], f"任务执行器崩溃: {e}", append=True)
                    db.update_task_status(task['id'], 'failed')
                finally:
                    _current_automator = None  # 任务完成后清空

            else:
                # print("队列为空，等待新任务...") # 频繁打印，暂时注释
                time.sleep(5)
        print("工作线程检测到停止信号，正在退出...") 