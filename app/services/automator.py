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
import database as db
from datetime import datetime

# --- Global Worker State ---
_worker_thread = None
_stop_event = None

def worker_thread_manager(action="start", app_context=None):
    """Manages the lifecycle of the background worker thread."""
    global _worker_thread, _stop_event

    if action == "start":
        if _worker_thread is None or not _worker_thread.is_alive():
            _stop_event = threading.Event()
            _worker_thread = threading.Thread(target=queue_worker, args=(app_context,), daemon=True)
            _worker_thread.start()
            print("后台工作线程已启动。")
    elif action == "stop":
        if _worker_thread and _worker_thread.is_alive():
            _stop_event.set()
            _worker_thread.join(timeout=10) # Wait for thread to finish
            print("后台工作线程已停止。")

def stop_worker():
    """Public function to signal the worker to stop."""
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
    Encapsulates the automation logic for a single task.
    An instance of this class will be created for each task processed by the worker.
    """
    def __init__(self, task_id, urls, debug=False):
        self.task_id = task_id
        self.urls = urls
        self.debug = debug
        self.driver = None
        self.stop_requested = threading.Event()
        self.user_data_dir = tempfile.mkdtemp() # 为每个任务创建唯一的用户数据目录

    def run(self):
        """Main execution method for the automation task."""
        success = False
        try:
            self._log("任务处理开始...")
            self._initialize_driver()
            account = self._login()
            if not account:
                raise Exception("无法找到可用账号或登录失败。")

            for i, url in enumerate(self.urls):
                if self.stop_requested.is_set():
                    self._log("检测到停止请求，正在中断任务...")
                    break
                self._log(f"正在处理第 {i+1}/{len(self.urls)} 个URL: {url}")
                self._process_url(url, account['id'])
            
            if not self.stop_requested.is_set():
                success = True

        except Exception as e:
            self._log(f"任务执行期间发生严重错误: {e}")
            success = False
        finally:
            self._cleanup()
            if self.stop_requested.is_set():
                self._log("任务已被用户手动停止。")
                db.update_task_status(self.task_id, 'stopped', log="任务已被用户手动停止。", append=True)
            elif not success:
                self._log("任务因发生错误而失败。")
                db.update_task_status(self.task_id, 'failed', log="任务失败。", append=True)
            else:
                self._log("任务成功完成所有操作。")
                db.update_task_status(self.task_id, 'completed', log="任务成功完成。", append=True)
    
    def stop(self):
        """Signals the automation task to stop."""
        self._log("接收到停止信号...")
        self.stop_requested.set()
        # Also set the global event to stop the main worker loop from processing this instance further
        if _stop_event:
            _stop_event.set()

    def _log(self, message):
        """Logs a message for the current task."""
        _log_to_db(self.task_id, message)

    def _initialize_driver(self):
        """Initializes the Selenium WebDriver."""
        try:
            self._log("初始化浏览器驱动...")
            options = webdriver.ChromeOptions()
            if not self.debug:
                options.add_argument('--headless')
                options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument(f"--user-data-dir={self.user_data_dir}")
            options.add_argument("user-agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'")
            
            self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
            self.driver.set_page_load_timeout(30)
            self._log("浏览器驱动初始化成功。")
        except WebDriverException as e:
            self._log(f"浏览器驱动初始化失败: {e}")
            raise

    def _login(self):
        """Fetches an account and uses its cookies to log in."""
        self._log("正在尝试登录...")
        accounts = db.get_all_accounts()
        if not accounts:
            self._log("数据库中没有任何可用账号。")
            return None
        
        # For simplicity, we use the first active account.
        # A more robust solution might involve rotation or selection logic.
        account = accounts[0]
        self._log(f"选用账号: {account['username']}")
        
        try:
            cookies = json.loads(account['cookies'])
            self.driver.get("https://www.douyin.com")
            time.sleep(2)
            
            for cookie in cookies:
                # Selenium can be picky. We'll clean up the cookie before adding it.
                
                # 1. Skip cookies for irrelevant domains.
                if 'domain' in cookie and 'douyin.com' not in cookie['domain']:
                    continue

                # 2. Rename 'expirationDate' to 'expiry' if it exists.
                if 'expirationDate' in cookie:
                    cookie['expiry'] = int(cookie['expirationDate'])
                    del cookie['expirationDate']

                # 3. Normalize sameSite attribute
                if 'sameSite' in cookie:
                    samesite_value = cookie['sameSite'].lower()
                    if samesite_value in ['no_restriction', 'none']:
                        cookie['sameSite'] = 'None'
                    elif samesite_value == 'lax':
                        cookie['sameSite'] = 'Lax'
                    elif samesite_value == 'strict':
                        cookie['sameSite'] = 'Strict'
                    else:
                        # If the value is not recognized, remove it to be safe
                        del cookie['sameSite']

                # 4. Add cookie with error handling for individual cookies.
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    # Log as a warning and continue, as some cookies might be irrelevant
                    self._log(f"警告：添加Cookie '{cookie.get('name', 'N/A')}' 失败: {e}")
            
            self.driver.refresh()
            time.sleep(3)
            
            # Check for login success by looking for user avatar
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'header [data-e2e="user-avatar"]'))
            )
            self._log(f"账号 {account['username']} 登录成功。")
            db.update_account_login_time(account['id'])
            return account
        except TimeoutException:
            self._log("登录验证失败：用户头像未在规定时间内出现。Cookie可能已过期，请尝试更新。")
            try:
                # Save a screenshot for debugging purposes
                screenshot_path = os.path.abspath(f"login_failure_task_{self.task_id}.png")
                self.driver.save_screenshot(screenshot_path)
                self._log(f"已保存登录失败截图至: {screenshot_path}")
            except Exception as e:
                self._log(f"无法保存截图: {e}")
            
            db.update_account_status(account['id'], 'expired')
            return None
        except (json.JSONDecodeError, WebDriverException) as e:
            self._log(f"使用Cookie登录失败: {e}")
            db.update_account_status(account['id'], 'expired')
            return None

    def _process_url(self, url, account_id):
        """Navigates to a user's homepage, finds videos, and interacts with them."""
        try:
            self._log(f"导航到: {url}")
            self.driver.get(url)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-e2e="user-post-list"]'))
            )
            self._log("成功加载用户主页。")

            # Simple interaction: like the top 3 videos if not already liked
            videos = self.driver.find_elements(By.CSS_SELECTOR, '[data-e2e="user-post-item"]')
            self._log(f"发现 {len(videos)} 个视频，将尝试与前3个互动。")
            
            for video_element in videos[:3]:
                if self.stop_requested.is_set(): break
                
                try:
                    video_url = video_element.find_element(By.TAG_NAME, 'a').get_attribute('href')
                    if not db.has_interacted(account_id, video_url, 'like'):
                        self._log(f"准备点赞视频: {video_url}")
                        # In Douyin's web UI, hovering over the video thumbnail reveals the like button.
                        webdriver.ActionChains(self.driver).move_to_element(video_element).perform()
                        time.sleep(0.5)
                        
                        # The like button is inside the item, find it.
                        like_button = video_element.find_element(By.CSS_SELECTOR, '[data-e2e="video-card-like-count"]')
                        like_button.click()

                        db.log_interaction(account_id, video_url, 'like')
                        self._log(f"点赞成功。")
                        time.sleep(random.randint(3, 7)) # Simulate human behavior
                    else:
                        self._log(f"视频 {video_url} 已点赞过，跳过。")
                except (NoSuchElementException, TimeoutException) as e:
                    self._log(f"处理单个视频时出错: {e}")
                    continue # Move to the next video

        except TimeoutException:
            self._log("加载用户主页超时，可能URL无效或网络问题。")
        except Exception as e:
            self._log(f"处理URL {url} 时发生未知错误: {e}")

    def _cleanup(self):
        """Cleans up resources (like the WebDriver) after the task is done."""
        if self.driver:
            self.driver.quit()
            self._log("浏览器驱动已关闭。")
        
        # 清理为该任务创建的临时用户数据目录
        if hasattr(self, 'user_data_dir') and self.user_data_dir and os.path.exists(self.user_data_dir):
            shutil.rmtree(self.user_data_dir, ignore_errors=True)
            self._log("临时用户数据目录已清理。")

def queue_worker(app_context):
    """The main function for the background worker thread."""
    with app_context:
        while not _stop_event.is_set():
            task_data = db.find_next_pending_task()
            if task_data:
                print(f"发现待处理任务: #{task_data['id']}")
                # Pass append=False to overwrite old logs
                db.update_task_status(task_data['id'], 'running', log="任务开始处理...", append=False)
                
                try:
                    # Correctly parse the JSON object from the database
                    task_info = json.loads(task_data['urls_json'])
                    urls = task_info.get('urls', [])
                    debug_mode = task_info.get('debug', False)
                    
                    if not urls:
                        raise ValueError("任务数据中缺少'urls'列表。")

                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    error_message = f"任务失败：数据格式无效或不完整。错误: {e}"
                    _log_to_db(task_data['id'], error_message, append=False)
                    db.update_task_status(task_data['id'], 'failed')
                    continue

                automator_instance = Automator(task_data['id'], urls, debug=debug_mode)
                
                # Run the automation in a way that respects the stop event
                automator_instance.run()

                # After run, check if the global stop was triggered
                if _stop_event.is_set():
                    print("检测到全局停止信号，工作线程将退出。")
                    break
            else:
                # No pending tasks, wait for a bit before checking again
                time.sleep(5)
        print("工作线程循环已退出。") 