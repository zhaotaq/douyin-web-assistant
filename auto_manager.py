import asyncio
import json
import random
import time
import subprocess
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set, Dict, Any
import os
import threading

from account_manager import AccountManager
from playwright.async_api import async_playwright

# 音频播放相关导入
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("⚠️ pygame未安装，音频功能将被禁用。安装命令: pip install pygame")

class AudioManager:
    """音频管理器"""
    def __init__(self, sound_dir: Path):
        self.sound_dir = sound_dir
        self.enabled = PYGAME_AVAILABLE
        
        if self.enabled:
            try:
                pygame.mixer.init()
                print("🔊 音频系统初始化成功")
            except Exception as e:
                print(f"⚠️ 音频系统初始化失败: {e}")
                self.enabled = False
        
        # 音频文件路径
        self.sounds = {
            'end': self.sound_dir / "end sound.mp3",
            'phone': self.sound_dir / "phone sound.mp3", 
            'error': self.sound_dir / "error sound.mp3"
        }
        
        # 检查音频文件是否存在
        for sound_type, sound_path in self.sounds.items():
            if not sound_path.exists():
                print(f"⚠️ 音频文件不存在: {sound_path}")
                self.enabled = False
    
    def play_sound(self, sound_type: str):
        """播放指定类型的音频"""
        if not self.enabled:
            return
        
        if sound_type not in self.sounds:
            print(f"⚠️ 未知的音频类型: {sound_type}")
            return
        
        sound_path = self.sounds[sound_type]
        if not sound_path.exists():
            print(f"⚠️ 音频文件不存在: {sound_path}")
            return
        
        try:
            # 在新线程中播放音频，避免阻塞主程序
            def play_audio():
                try:
                    pygame.mixer.music.load(str(sound_path))
                    pygame.mixer.music.play()
                    
                    # 等待播放完成
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                except Exception as e:
                    print(f"⚠️ 播放音频失败: {e}")
            
            audio_thread = threading.Thread(target=play_audio, daemon=True)
            audio_thread.start()
            
            # 音频类型对应的emoji和描述
            sound_descriptions = {
                'end': '🎵 任务完成提醒',
                'phone': '📱 手机验证码提醒', 
                'error': '🚨 错误提醒'
            }
            
            print(f"🔊 播放音频: {sound_descriptions.get(sound_type, sound_type)}")
            
        except Exception as e:
            print(f"⚠️ 播放音频失败: {e}")
    
    def play_end_sound(self):
        """播放任务结束音频"""
        self.play_sound('end')
    
    def play_phone_sound(self):
        """播放手机验证码音频"""
        self.play_sound('phone')
    
    def play_error_sound(self):
        """播放错误音频"""
        self.play_sound('error')

class AutoManager:
    def __init__(self):
        self.account_manager = AccountManager()
        # 使用脚本所在目录作为基准目录，确保无论从哪里运行都能找到文件
        self.base_dir = Path(__file__).parent
        self.homepage_urls_file = self.base_dir / "homepage_urls.txt"
        self.processed_videos_dir = self.base_dir / "processed_videos"  # 改为目录
        self.comments_file = self.base_dir / "comments_pool.txt"
        self.stats_file = self.base_dir / "statistics.json"  # 统计数据文件
        self.logs_dir = self.base_dir / "logs"  # 日志目录
        
        print(f"🔍 程序基准目录: {self.base_dir.absolute()}")
        
        # 初始化音频管理器
        sound_dir = self.base_dir / "sound"
        self.audio_manager = AudioManager(sound_dir)
        
        # 确保文件存在
        self._ensure_files_exist()
        
    def _ensure_files_exist(self):
        """确保必要的文件存在"""
        if not self.homepage_urls_file.exists():
            self.homepage_urls_file.write_text("# 抖音用户主页地址库\n# 每行一个链接\n", encoding="utf-8")
        
        # 创建已处理视频目录
        self.processed_videos_dir.mkdir(exist_ok=True)
        
        # 创建日志目录
        self.logs_dir.mkdir(exist_ok=True)
            
        if not self.comments_file.exists():
            self.comments_file.write_text("太棒了！\n支持一下！\n好视频！\n点赞支持！\n", encoding="utf-8")
        
        # 初始化统计文件
        if not self.stats_file.exists():
            self._init_statistics()
    
    def _init_statistics(self):
        """初始化统计数据"""
        stats = {
            "total_processed_videos": 0,
            "total_likes": 0,
            "total_comments": 0,
            "daily_stats": {},
            "account_stats": {},
            "error_stats": {},
            "performance_stats": {
                "avg_processing_time": 0,
                "success_rate": 0
            },
            "last_updated": datetime.now().isoformat()
        }
        with open(self.stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    
    def update_statistics(self, account_name: str, processed_count: int, likes: int, comments: int, errors: int = 0):
        """更新统计数据"""
        try:
            # 读取现有统计
            with open(self.stats_file, "r", encoding="utf-8") as f:
                stats = json.load(f)
            
            today = datetime.now().strftime("%Y-%m-%d")
            
            # 更新总体统计
            stats["total_processed_videos"] += processed_count
            stats["total_likes"] += likes
            stats["total_comments"] += comments
            
            # 更新每日统计
            if today not in stats["daily_stats"]:
                stats["daily_stats"][today] = {
                    "processed": 0, "likes": 0, "comments": 0, "errors": 0
                }
            stats["daily_stats"][today]["processed"] += processed_count
            stats["daily_stats"][today]["likes"] += likes
            stats["daily_stats"][today]["comments"] += comments
            stats["daily_stats"][today]["errors"] += errors
            
            # 更新账户统计
            if account_name not in stats["account_stats"]:
                stats["account_stats"][account_name] = {
                    "processed": 0, "likes": 0, "comments": 0, "errors": 0, "last_active": ""
                }
            stats["account_stats"][account_name]["processed"] += processed_count
            stats["account_stats"][account_name]["likes"] += likes
            stats["account_stats"][account_name]["comments"] += comments
            stats["account_stats"][account_name]["errors"] += errors
            stats["account_stats"][account_name]["last_active"] = datetime.now().isoformat()
            
            # 计算成功率
            total_attempts = stats["total_processed_videos"] + sum(day["errors"] for day in stats["daily_stats"].values())
            if total_attempts > 0:
                stats["performance_stats"]["success_rate"] = (stats["total_processed_videos"] / total_attempts) * 100
            
            stats["last_updated"] = datetime.now().isoformat()
            
            # 保存统计
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"⚠️ 更新统计数据失败: {e}")
    
    def get_statistics_report(self) -> str:
        """生成统计报告"""
        try:
            with open(self.stats_file, "r", encoding="utf-8") as f:
                stats = json.load(f)
            
            report = []
            report.append("📊 === 数据统计报告 ===")
            report.append(f"📈 总处理视频: {stats['total_processed_videos']}")
            report.append(f"👍 总点赞数: {stats['total_likes']}")
            report.append(f"💬 总评论数: {stats['total_comments']}")
            report.append(f"✅ 成功率: {stats['performance_stats']['success_rate']:.1f}%")
            
            # 最近7天统计
            report.append("\n📅 最近7天统计:")
            recent_days = []
            for i in range(7):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                if date in stats["daily_stats"]:
                    day_stats = stats["daily_stats"][date]
                    recent_days.append(f"  {date}: 处理{day_stats['processed']}个, 点赞{day_stats['likes']}个, 评论{day_stats['comments']}个")
            
            if recent_days:
                report.extend(recent_days)
            else:
                report.append("  暂无数据")
            
            # 账户统计
            report.append("\n👤 账户统计:")
            for account, account_stats in stats["account_stats"].items():
                last_active = datetime.fromisoformat(account_stats["last_active"]).strftime("%m-%d %H:%M") if account_stats["last_active"] else "从未"
                report.append(f"  {account}: 处理{account_stats['processed']}个, 最后活跃: {last_active}")
            
            return "\n".join(report)
            
        except Exception as e:
            return f"❌ 生成统计报告失败: {e}"
    
    def log_operation(self, level: str, message: str, account: str = None):
        """记录操作日志"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] [{level}] {f'[{account}] ' if account else ''}{message}\n"
            
            # 写入日志文件
            log_file = self.logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
                
        except Exception as e:
            print(f"⚠️ 写入日志失败: {e}")
    
    def force_cleanup_chromium_processes(self):
        """强制清理所有Chromium进程 - 增强版"""
        try:
            print("🧹 正在清理残留的Chromium进程...")
            
            cleaned_count = 0
            zombie_count = 0
            
            # 第一轮：优雅终止Playwright相关进程
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status']):
                try:
                    # 检查是否是Chromium相关进程
                    if 'chromium' in proc.info['name'].lower() or 'chrome' in proc.info['name'].lower():
                        # 检查是否是Playwright启动的进程或相关子进程
                        cmdline = ' '.join(proc.info['cmdline'] or [])
                        if any(keyword in cmdline.lower() for keyword in ['playwright', 'headless', 'automation', '--remote-debugging-port']):
                            print(f"  🎯 发现Playwright相关进程: {proc.info['name']} (PID: {proc.info['pid']})")
                            proc.terminate()
                            cleaned_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # 等待进程优雅退出
            if cleaned_count > 0:
                print(f"  ⏳ 等待 {cleaned_count} 个进程优雅退出...")
                time.sleep(2)
            
            # 第二轮：强制杀死仍然存在的进程
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status']):
                try:
                    if 'chromium' in proc.info['name'].lower() or 'chrome' in proc.info['name'].lower():
                        cmdline = ' '.join(proc.info['cmdline'] or [])
                        if any(keyword in cmdline.lower() for keyword in ['playwright', 'headless', 'automation', '--remote-debugging-port']):
                            print(f"  💀 强制杀死顽固进程: {proc.info['name']} (PID: {proc.info['pid']})")
                            proc.kill()
                            proc.wait(timeout=3)
                            zombie_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    pass
            
            # 第三轮：清理僵尸进程
            try:
                for proc in psutil.process_iter(['pid', 'name', 'status']):
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        if 'chromium' in proc.info['name'].lower() or 'chrome' in proc.info['name'].lower():
                            print(f"  🧟 清理僵尸进程: {proc.info['name']} (PID: {proc.info['pid']})")
                            try:
                                proc.kill()
                            except:
                                pass
            except:
                pass
            
            total_cleaned = cleaned_count + zombie_count
            if total_cleaned > 0:
                print(f"✅ 总共清理了 {total_cleaned} 个Chromium进程 (优雅: {cleaned_count}, 强制: {zombie_count})")
            else:
                print("ℹ️ 没有发现需要清理的Chromium进程")
                
            # 等待系统完成清理
            time.sleep(1)
                
        except Exception as e:
            print(f"⚠️ 清理进程时出错: {e}")
            # 备用清理方法：使用系统命令
            try:
                print("🔄 尝试备用清理方法...")
                if os.name == 'nt':  # Windows
                    subprocess.run(['taskkill', '/F', '/IM', 'chromium.exe'], 
                                   capture_output=True, shell=True)
                    subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                                   capture_output=True, shell=True)
                print("✅ 备用清理完成")
            except:
                print("⚠️ 备用清理也失败了")
    
    def get_chromium_process_count(self):
        """获取当前Chromium进程数量"""
        try:
            count = 0
            for proc in psutil.process_iter(['name']):
                if 'chromium' in proc.info['name'].lower() or 'chrome' in proc.info['name'].lower():
                    count += 1
            return count
        except:
            return -1
    
    def get_account_processed_file(self, account_name: str) -> Path:
        """获取指定账户的已处理视频文件路径"""
        return self.processed_videos_dir / f"{account_name}_processed.txt"
    
    def load_homepage_urls(self) -> List[Dict[str, Any]]:
        """加载主页地址列表，支持数量限制
        返回格式：[{"url": "链接", "limit": 数量或None}, ...]
        支持格式：
        - https://www.douyin.com/user/xxxxx (不限制)
        - https://www.douyin.com/user/xxxxx @30 (限制30个)
        """
        urls = []
        try:
            with open(self.homepage_urls_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                if not line:
                    continue  # 跳过空行
                elif line.startswith('#'):
                    continue  # 跳过注释行
                elif line.startswith("https://www.douyin.com/user/"):
                    # 解析URL和可能的数量限制
                    if ' @' in line:
                        url_part, limit_part = line.split(' @', 1)
                        url = url_part.strip()
                        try:
                            limit = int(limit_part.strip())
                            if limit <= 0:
                                print(f"⚠️ 无效的数量限制 {limit}，使用不限制模式: {url}")
                                limit = None
                        except ValueError:
                            print(f"⚠️ 无效的数量限制格式，使用不限制模式: {line}")
                            limit = None
                    else:
                        url = line
                        limit = None
                    
                    urls.append({"url": url, "limit": limit})
                    if limit:
                        print(f"📍 主页配置: {url[:60]}... (限制{limit}个视频)")
                    else:
                        print(f"📍 主页配置: {url[:60]}... (不限制)")
                else:
                    print(f"⚠️ 跳过无效链接 (行{line_num}): {line[:50]}...")
            
            if urls:
                print(f"✅ 总共加载了 {len(urls)} 个有效主页地址")
            else:
                print(f"⚠️ 未找到有效的主页地址，请检查文件: {self.homepage_urls_file}")
                        
        except Exception as e:
            print(f"❌ 读取主页地址文件失败: {e}")
        
        return urls
    
    def load_processed_videos(self, account_name: str) -> Set[str]:
        """加载指定账户已处理的视频链接（兼容新格式with标题注解）"""
        processed = set()
        processed_file = self.get_account_processed_file(account_name)
        
        try:
            if processed_file.exists():
                with open(processed_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # 提取URL部分（支持新格式：URL #标题）
                            if ' #' in line:
                                url = line.split(' #')[0].strip()
                            else:
                                url = line
                            processed.add(url)
        except Exception as e:
            print(f"❌ 读取账户 {account_name} 已处理视频文件失败: {e}")
        
        return processed
    
    def save_processed_video(self, account_name: str, video_url: str, video_title: str = None):
        """保存指定账户已处理的视频链接，支持添加标题注解"""
        try:
            processed_file = self.get_account_processed_file(account_name)
            # 如果文件不存在，先创建头部
            if not processed_file.exists():
                processed_file.write_text(f"# 账户 {account_name} 已处理视频链接库\n", encoding="utf-8")
            
            with open(processed_file, "a", encoding="utf-8") as f:
                if video_title and video_title.strip():
                    # 清理标题中的换行符和特殊字符，确保格式正确
                    clean_title = video_title.strip().replace('\n', ' ').replace('\r', ' ')
                    f.write(f"{video_url} #{clean_title}\n")
                else:
                    f.write(f"{video_url}\n")
        except Exception as e:
            print(f"❌ 保存账户 {account_name} 已处理视频失败: {e}")
    
    def get_all_processed_videos_count(self) -> int:
        """获取所有账户已处理视频的总数（用于统计）"""
        total = 0
        for processed_file in self.processed_videos_dir.glob("*_processed.txt"):
            try:
                with open(processed_file, "r", encoding="utf-8") as f:
                    count = sum(1 for line in f if line.strip() and not line.startswith('#'))
                    total += count
            except:
                pass
        return total
    
    def get_random_comment(self) -> str:
        """获取随机评论"""
        try:
            with open(self.comments_file, "r", encoding="utf-8") as f:
                comments = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                return random.choice(comments) if comments else "支持一下！"
        except:
            return "支持一下！"
    
    async def process_account_with_all_homepages(self, account: Dict[str, str], homepage_urls: List) -> int:
        """使用指定账户处理所有主页地址 - 优化浏览器资源管理"""
        print(f"\n👤 账户【{account['name']}】开始处理所有主页...")
        
        # 预检查：是否有新视频需要处理
        total_new_videos = 0
        processed_videos = self.load_processed_videos(account['name'])
        
        print(f"  🔍 预检查新视频...")
        for homepage_url in homepage_urls:
            # 这里可以添加快速检查逻辑，现在先假设可能有新视频
            pass
        
        total_processed = 0
        browser = None
        context = None
        page = None
        playwright_instance = None
        
        try:
            # 启动浏览器（整个账户处理期间只启动一次）
            playwright_instance = await async_playwright().start()
            browser = await playwright_instance.chromium.launch(headless=False)
            context = await browser.new_context(storage_state=account['path'])
            page = await context.new_page()
            
            # 处理所有主页
            for homepage_idx, homepage_config in enumerate(homepage_urls, 1):
                homepage_url = homepage_config["url"]
                video_limit = homepage_config["limit"]
                
                limit_text = f"(限制{video_limit}个)" if video_limit else "(不限制)"
                print(f"\n  📍 处理主页 {homepage_idx}/{len(homepage_urls)}: {homepage_url} {limit_text}")
                
                try:
                    # 重新加载已处理视频列表（因为在处理过程中会有新增）
                    processed_videos = self.load_processed_videos(account['name'])
                    
                    newly_processed = await self._process_single_homepage(
                        page, account, homepage_url, processed_videos, video_limit
                    )
                    
                    # 保存新处理的视频（按账户分别保存，包含标题）
                    for video_data in newly_processed:
                        if isinstance(video_data, dict):
                            self.save_processed_video(account['name'], video_data['url'], video_data['title'])
                        else:
                            # 兼容旧格式
                            self.save_processed_video(account['name'], video_data)
                    
                    total_processed += len(newly_processed)
                    
                    if newly_processed:
                        print(f"    ✅ 成功处理 {len(newly_processed)} 个新视频")
                    else:
                        print(f"    ℹ️ 没有新视频需要处理")
                    
                    # 主页间随机等待（在同一账户的主页切换间）
                    if homepage_idx < len(homepage_urls):
                        wait_time = 2  # 大幅减少主页切换等待时间
                        print(f"    ⏳ 主页切换等待 {wait_time} 秒...")
                        await asyncio.sleep(wait_time)
                        
                except Exception as e:
                    print(f"    ❌ 处理主页失败: {e}")
                    # 发生错误时强制清理进程
                    self.force_cleanup_chromium_processes()
                    
                    # 播放错误音频
                    self.audio_manager.play_error_sound()
                    
                    continue
            
            # 播放任务完成音频
            if total_processed > 0:
                self.audio_manager.play_end_sound()
            
            return total_processed
            
        except Exception as e:
            print(f"❌ 账户浏览器操作失败: {e}")
            return total_processed
        finally:
            # 强化资源清理 - 使用多种方法确保清理成功
            cleanup_success = False
            
            # 方法1：正常关闭
            try:
                if page and not page.is_closed():
                    await page.close()
                    print(f"    🗑️ 页面已正常关闭")
                    cleanup_success = True
            except Exception as e:
                print(f"    ⚠️ 页面正常关闭失败: {e}")
            
            try:
                if context:
                    await context.close()
                    print(f"    🗑️ 上下文已正常关闭")
                    cleanup_success = True
            except Exception as e:
                print(f"    ⚠️ 上下文正常关闭失败: {e}")
            
            try:
                if browser:
                    await browser.close()
                    print(f"    🗑️ 浏览器已正常关闭")
                    cleanup_success = True
            except Exception as e:
                print(f"    ⚠️ 浏览器正常关闭失败: {e}")
            
            try:
                if playwright_instance:
                    await playwright_instance.stop()
                    print(f"    🗑️ Playwright实例已关闭")
            except Exception as e:
                print(f"    ⚠️ Playwright实例关闭失败: {e}")
            
            # 方法2：如果正常关闭失败，强制清理进程
            if not cleanup_success:
                print(f"    🧹 正常关闭失败，执行强制进程清理...")
                self.force_cleanup_chromium_processes()
            
            # 方法3：等待一下让系统清理
            await asyncio.sleep(1)
            
            # 最终检查进程数量
            final_count = self.get_chromium_process_count()
            print(f"    📊 资源清理后Chromium进程数: {final_count}")
    
    async def _process_single_homepage(self, page, account: Dict[str, str], homepage_url: str, processed_videos: Set[str], video_limit: int = None) -> List[str]:
        """处理单个主页（重用现有的页面实例）"""
        print(f"\n🔄 开始处理主页: {homepage_url}")
        
        try:
            # 导航到主页
            await page.goto(homepage_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(500)  # 减少等待时间，立即检测弹窗
            
            # 检测并处理登录信息保存弹窗
            await self._handle_login_save_popup(page)
            
            # 滚动加载更多视频 - 智能滚动
            print("  📜 开始智能滚动加载更多视频...")
            
            # 获取初始视频数量
            initial_video_count = await page.evaluate("""
            () => {
                const videoList = document.querySelector('ul.e6wsjNLL.bGEvyQfj[data-e2e="scroll-list"]');
                return videoList ? videoList.querySelectorAll('li').length : 0;
            }
            """)
            print(f"    📊 初始视频数量: {initial_video_count}")
            
            max_scrolls = 5  # 最多滚动5次
            successful_scrolls = 0
            
            for i in range(max_scrolls):
                print(f"  📜 滚动尝试 ({i+1}/{max_scrolls})...")
                
                # 记录滚动前的位置和视频数量
                before_scroll_position = await page.evaluate("window.pageYOffset")
                before_video_count = await page.evaluate("""
                () => {
                    const videoList = document.querySelector('ul.e6wsjNLL.bGEvyQfj[data-e2e="scroll-list"]');
                    return videoList ? videoList.querySelectorAll('li').length : 0;
                }
                """)
                
                # 使用多种滚动方法确保有效
                scroll_success = False
                try:
                    # 方法1: JavaScript滚动到页面底部
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    await page.wait_for_timeout(1500)
                    
                    # 检查是否滚动成功
                    after_scroll_position = await page.evaluate("window.pageYOffset")
                    if after_scroll_position > before_scroll_position:
                        scroll_success = True
                        print(f"    ✅ JavaScript滚动成功: {before_scroll_position}px → {after_scroll_position}px")
                    else:
                        # 方法2: 使用鼠标滚轮滚动
                        await page.mouse.wheel(0, 1500)  # 向下滚动1500像素
                        await page.wait_for_timeout(1500)
                        
                        after_scroll_position = await page.evaluate("window.pageYOffset")
                        if after_scroll_position > before_scroll_position:
                            scroll_success = True
                            print(f"    ✅ 鼠标滚轮滚动成功: {before_scroll_position}px → {after_scroll_position}px")
                        else:
                            # 方法3: 模拟键盘滚动
                            for _ in range(3):
                                await page.keyboard.press('PageDown')
                                await page.wait_for_timeout(500)
                            
                            after_scroll_position = await page.evaluate("window.pageYOffset")
                            if after_scroll_position > before_scroll_position:
                                scroll_success = True
                                print(f"    ✅ 键盘滚动成功: {before_scroll_position}px → {after_scroll_position}px")
                    
                    # 检查是否加载了新视频
                    await page.wait_for_timeout(2000)  # 等待内容加载
                    after_video_count = await page.evaluate("""
                    () => {
                        const videoList = document.querySelector('ul.e6wsjNLL.bGEvyQfj[data-e2e="scroll-list"]');
                        return videoList ? videoList.querySelectorAll('li').length : 0;
                    }
                    """)
                    
                    if after_video_count > before_video_count:
                        successful_scrolls += 1
                        print(f"    📈 新加载视频: {before_video_count} → {after_video_count} (+{after_video_count - before_video_count})")
                    else:
                        print(f"    📊 视频数量未变化: {after_video_count}")
                        if scroll_success:
                            print(f"    ℹ️ 可能已到达页面底部")
                            break
                    
                except Exception as e:
                    print(f"    ⚠️ 滚动过程出错: {e}")
                    # 备用滚动方法
                    try:
                        await page.evaluate("window.scrollBy(0, 1000);")
                        await page.wait_for_timeout(1500)
                        print(f"    ✅ 使用备用滚动方法")
                    except:
                        print(f"    ❌ 所有滚动方法都失败了")
                        break
            
            # 最终统计
            final_video_count = await page.evaluate("""
            () => {
                const videoList = document.querySelector('ul.e6wsjNLL.bGEvyQfj[data-e2e="scroll-list"]');
                return videoList ? videoList.querySelectorAll('li').length : 0;
            }
            """)
            
            print(f"  📊 滚动完成: 初始{initial_video_count}个 → 最终{final_video_count}个视频 (成功滚动{successful_scrolls}次)")
            
            # 提取视频信息
            js_code = """
            (function() {
                const videoListElement = document.querySelector('ul.e6wsjNLL.bGEvyQfj[data-e2e="scroll-list"]');
                if (!videoListElement) {
                    return [];
                }
                const videos = [];
                const videoItems = videoListElement.querySelectorAll('li');
                videoItems.forEach(item => {
                    const linkElement = item.querySelector('a');
                    const imgElement = item.querySelector('img');
                    if (linkElement && imgElement) {
                        const href = linkElement.href;
                        const title = imgElement.alt || '无标题';
                        videos.push({ title: title, link: href });
                    }
                });
                return videos;
            })();
            """
            
            videos_data = await page.evaluate(js_code)
            
            if not videos_data:
                print(f"  ⚠️ 未找到视频数据")
                return []
            
            # 过滤当前账户已处理的视频
            new_videos = [v for v in videos_data if v['link'] not in processed_videos]
            
            # 应用数量限制
            if video_limit and len(new_videos) > video_limit:
                new_videos = new_videos[:video_limit]
                print(f"  📊 找到 {len(videos_data)} 个视频，其中 {len([v for v in videos_data if v['link'] not in processed_videos])} 个未处理，应用限制后处理 {len(new_videos)} 个")
            else:
                print(f"  📊 找到 {len(videos_data)} 个视频，其中 {len(new_videos)} 个未被当前账户处理")
            
            if not new_videos:
                print(f"  ✅ 当前账户已处理所有视频，跳过")
                return []
            
            # 处理新视频（点赞和评论）
            newly_processed = []
            likes_count = 0
            comments_count = 0
            errors_count = 0
            
            for i, video_info in enumerate(new_videos):
                video_url = video_info["link"]
                video_title = video_info["title"]
                
                print(f"\n  🎯 处理视频 {i+1}/{len(new_videos)}: {video_title[:30]}...")
                print(f"    链接: {video_url}")
                
                try:
                    await page.goto(video_url, wait_until="domcontentloaded", timeout=60000)
                    await page.wait_for_timeout(500)  # 减少等待时间，快速检测弹窗
                    
                    # 检测并处理可能的登录保存弹窗
                    await self._handle_login_save_popup(page)
                    
                    # 检查并处理点赞
                    like_result = await self._handle_like(page)
                    if like_result:
                        likes_count += 1
                    
                    # 检查并处理评论
                    comment_result = await self._handle_comment(page, account['name'])
                    if comment_result:
                        comments_count += 1
                    
                    # 记录已处理的视频（包含标题信息）
                    newly_processed.append({"url": video_url, "title": video_title})
                    
                    # 记录操作日志
                    self.log_operation("INFO", f"成功处理视频: {video_title[:30]}", account['name'])
                    
                    # 随机等待，避免被检测
                    wait_time = random.randint(2, 5)
                    print(f"    ⏳ 等待 {wait_time} 秒...")
                    await page.wait_for_timeout(wait_time * 1000)
                    
                except Exception as e:
                    print(f"    ❌ 处理视频失败: {e}")
                    errors_count += 1
                    self.log_operation("ERROR", f"处理视频失败: {video_title[:30]} - {e}", account['name'])
                    
                    # 播放错误音频
                    self.audio_manager.play_error_sound()
                    
                    continue
            
            # 更新统计数据
            if newly_processed:
                self.update_statistics(account['name'], len(newly_processed), likes_count, comments_count, errors_count)
                self.log_operation("INFO", f"主页处理完成: 处理{len(newly_processed)}个视频, 点赞{likes_count}个, 评论{comments_count}个", account['name'])
                
                # 播放任务完成音频
                self.audio_manager.play_end_sound()
            
            return newly_processed
            
        except Exception as e:
            print(f"❌ 处理主页失败: {e}")
            return []
    
    async def _handle_login_save_popup(self, page):
        """处理登录信息保存弹窗 - 优化版（5秒内快速检测）"""
        try:
            print("  🔍 快速检测登录信息保存弹窗...")
            
            # 立即开始检测，不等待
            popup_found = False
            popup_element = None
            
            # 快速检测循环 - 在5秒内多次检测
            for attempt in range(10):  # 10次检测，每次间隔0.5秒
                try:
                    # 使用JavaScript快速检测弹窗
                    popup_info = await page.evaluate("""
                    () => {
                        // 查找包含特定文本的元素
                        const allElements = document.querySelectorAll('*');
                        for (let element of allElements) {
                            if (element.textContent && element.textContent.includes('是否保存登录信息')) {
                                // 检查元素是否可见
                                const rect = element.getBoundingClientRect();
                                const style = window.getComputedStyle(element);
                                if (rect.width > 0 && rect.height > 0 && 
                                    style.display !== 'none' && 
                                    style.visibility !== 'hidden' &&
                                    style.opacity !== '0') {
                                    return {
                                        found: true,
                                        text: element.textContent.substring(0, 100),
                                        className: element.className,
                                        id: element.id,
                                        tagName: element.tagName
                                    };
                                }
                            }
                        }
                        return { found: false };
                    }
                    """)
                    
                    if popup_info.get('found'):
                        print(f"    ✅ 第{attempt+1}次检测发现弹窗: {popup_info.get('text', '')[:50]}...")
                        popup_found = True
                        break
                    
                    # 短暂等待后继续检测
                    await page.wait_for_timeout(500)  # 0.5秒间隔
                    
                except Exception as e:
                    print(f"    ⚠️ 第{attempt+1}次检测失败: {e}")
                    await page.wait_for_timeout(500)
                    continue
            
            if popup_found:
                print("    🚫 立即尝试关闭弹窗...")
                
                # 快速关闭方法 - 按成功率排序
                cancel_methods = [
                    # 最快的方法优先
                    ('Escape', "ESC键"),
                    ('text=取消', "文本取消"),
                    ('button:has-text("取消")', "按钮取消"),
                    # JavaScript直接点击
                    ('js_click', "JavaScript点击"),
                    # 其他备用方法
                    ('.semi-button-tertiary', "第三级按钮"),
                    ('button:first-of-type', "第一个按钮"),
                ]
                
                cancel_success = False
                
                for method, desc in cancel_methods:
                    if cancel_success:
                        break
                        
                    try:
                        if method == 'Escape':
                            await page.keyboard.press('Escape')
                            print(f"    ✅ 使用{desc}关闭弹窗")
                        elif method == 'js_click':
                            # 使用JavaScript直接点击取消按钮
                            js_click_result = await page.evaluate("""
                            () => {
                                // 查找取消按钮
                                const buttons = document.querySelectorAll('button');
                                for (let button of buttons) {
                                    if (button.textContent && button.textContent.includes('取消')) {
                                        button.click();
                                        return { success: true, text: button.textContent };
                                    }
                                }
                                
                                // 如果没找到取消按钮，尝试找第一个按钮
                                const firstButton = document.querySelector('button');
                                if (firstButton) {
                                    firstButton.click();
                                    return { success: true, text: firstButton.textContent };
                                }
                                
                                return { success: false };
                            }
                            """)
                            
                            if js_click_result.get('success'):
                                print(f"    ✅ 使用{desc}关闭弹窗: {js_click_result.get('text', '')}")
                            else:
                                print(f"    ⚠️ {desc}未找到按钮")
                                continue
                        else:
                            await page.click(method, timeout=2000)  # 减少超时时间
                            print(f"    ✅ 使用{desc}关闭弹窗")
                        
                        # 快速验证弹窗是否已关闭
                        await page.wait_for_timeout(300)  # 减少等待时间
                        
                        # 快速验证
                        still_visible = await page.evaluate("""
                        () => {
                            const allElements = document.querySelectorAll('*');
                            for (let element of allElements) {
                                if (element.textContent && element.textContent.includes('是否保存登录信息')) {
                                    const rect = element.getBoundingClientRect();
                                    const style = window.getComputedStyle(element);
                                    if (rect.width > 0 && rect.height > 0 && 
                                        style.display !== 'none' && 
                                        style.visibility !== 'hidden' &&
                                        style.opacity !== '0') {
                                        return true;
                                    }
                                }
                            }
                            return false;
                        }
                        """)
                        
                        if not still_visible:
                            cancel_success = True
                            print(f"    ✅ 弹窗已成功关闭")
                        else:
                            print(f"    ⚠️ {desc}未能关闭弹窗，尝试下一种方法")
                            
                    except Exception as e:
                        print(f"    ⚠️ {desc}失败: {e}")
                        continue
                
                if not cancel_success:
                    print("    ⚠️ 所有关闭方法都失败了，弹窗可能已自动消失")
                
                # 短暂等待确保页面稳定
                await page.wait_for_timeout(500)  # 减少最终等待时间
                
            else:
                print("    ℹ️ 5秒内未发现登录保存弹窗")
                
        except Exception as e:
            print(f"    ⚠️ 处理登录弹窗时出错: {e}，继续执行...")
    
    async def _handle_like(self, page):
        """处理点赞 - 测试验证成功版本"""
        try:
            # 等待页面稳定
            await page.wait_for_timeout(2000)
            
            check_like_js = r"""
            (function() {
                // 寻找主要的操作栏容器 - 增强版
                let actionBar = document.querySelector('div.xi78nG8b');
                
                // 如果第一次没找到，等待一下再试
                if (!actionBar) {
                    return { error: '未找到操作栏', retry: true };
                }
                
                // 检查操作栏是否可见
                const rect = actionBar.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) {
                    return { error: '操作栏不可见', retry: true };
                }

                // 寻找点赞按钮容器
                let likeButton = null;
                
                // 基于真实结构查找
                const likeContainer = actionBar.querySelector('._BMsHw2S');
                if (likeContainer) {
                    const clickableDiv = likeContainer.querySelector('div[tabindex="0"]');
                    if (clickableDiv) {
                        likeButton = clickableDiv;
                    }
                }
                
                if (!likeButton) {
                    const clickableDivs = actionBar.querySelectorAll('div[tabindex="0"]');
                    if (clickableDivs.length > 0) {
                        likeButton = clickableDivs[0];
                    }
                }
                
                if (!likeButton) return { error: '未找到点赞按钮' };

                // 检查点赞状态
                let isLiked = false;
                const svgElements = likeButton.querySelectorAll('svg');
                for (let svg of svgElements) {
                    const paths = svg.querySelectorAll('path');
                    for (let path of paths) {
                        const fill = path.getAttribute('fill') || window.getComputedStyle(path).fill;
                        if (fill) {
                            const normalizedFill = fill.replace(/\s/g, '').toLowerCase();
                            // 检查是否为已点赞的红色
                            if (normalizedFill.includes('rgb(254,44,85)') || 
                                normalizedFill.includes('254,44,85') ||
                                normalizedFill.includes('#fe2c55')) {
                                isLiked = true;
                                break;
                            }
                        }
                    }
                    if (isLiked) break;
                }
                
                return { 
                    liked: isLiked,
                    buttonFound: true,
                    actionBarInfo: {
                        className: actionBar.className,
                        position: rect,
                        textContent: actionBar.textContent.substring(0, 30)
                    }
                };
            })();
            """
            
            like_status = await page.evaluate(check_like_js)
            
            # 如果需要重试，等待一下再试
            if like_status.get('retry'):
                print(f"    ⏳ 等待页面加载完成，重试检测...")
                await page.wait_for_timeout(3000)
                like_status = await page.evaluate(check_like_js)
            
            if like_status.get('error'):
                print(f"    ⚠️ 点赞状态检查失败: {like_status['error']}")
                print("    🔄 使用键盘快捷键点赞...")
                await page.keyboard.press('Z')
                print("    ✅ 点赞成功（键盘方法）")
                return True
            elif like_status.get('liked'):
                print("    ✅ 已点赞，跳过")
                if 'actionBarInfo' in like_status:
                    print(f"    📊 操作栏信息: {like_status['actionBarInfo']['textContent']}")
                return False  # 已经点赞过了，不算新的点赞
            else:
                print("    👍 开始点赞...")
                if 'actionBarInfo' in like_status:
                    print(f"    📊 操作栏信息: {like_status['actionBarInfo']['textContent']}")
                
                success = False
                
                # 尝试多种点击方法（按测试成功的顺序）
                methods = [
                    ('._BMsHw2S div[tabindex="0"]', "基于结构"),
                    ('.xi78nG8b div[tabindex="0"]:first-child', "第一个可点击"),
                    ('.xi78nG8b .KMIJp86N', "图标容器")
                ]
                
                for selector, desc in methods:
                    if success:
                        break
                    try:
                        await page.click(selector, timeout=3000)
                        print(f"    ✅ 点赞成功（{desc}）")
                        success = True
                    except:
                        pass
                
                if not success:
                    try:
                        await page.keyboard.press('Z')
                        print("    ✅ 点赞成功（键盘方法）")
                        success = True
                    except:
                        pass
                
                if not success:
                    print("    ❌ 所有点赞方法都失败了")
                    return False
                
                return success
            
            await page.wait_for_timeout(1000)
            
        except Exception as e:
            print(f"    ❌ 点赞处理失败: {e}")
            # 最后的备用方法
            try:
                await page.keyboard.press('Z')
                print("    ✅ 点赞成功（备用键盘方法）")
                return True
            except:
                print("    ❌ 备用点赞方法也失败了")
                return False
    
    async def _handle_comment(self, page, account_name: str):
        """处理评论"""
        try:
            print("    💬 检查评论状态...")
            
            # 获取当前用户头像
            current_user_avatar = await page.evaluate("""
            () => {
                const headerAvatar = document.querySelector('img.RlLOO79h');
                if (!headerAvatar) return null;
                const avatarUrl = headerAvatar.src;
                const match = avatarUrl.match(/tos-cn[^?]+/);
                return match ? match[0] : avatarUrl;
            }
            """)
            
            if not current_user_avatar:
                print("    ⚠️ 无法获取用户头像，跳过评论检查")
                return False
            
            # 等待评论区加载
            comment_section_selector = '[data-e2e="comment-list"], .HV3aiR5J.comment-mainContent'
            try:
                await page.wait_for_selector(comment_section_selector, state='visible', timeout=7000)
                await page.wait_for_timeout(2000)  # 减少评论区加载等待时间
                
                # 滚动评论区
                try:
                    comment_section = await page.wait_for_selector(comment_section_selector, timeout=5000)
                    await comment_section.click()
                    await page.wait_for_timeout(500)  # 减少点击后等待时间
                    
                    # 使用PageDown键滚动
                    for i in range(3):
                        await page.keyboard.press('PageDown')
                        await page.wait_for_timeout(1500)  # 减少滚动等待时间
                        
                        # 快速检查是否发现重复评论
                        quick_check = await page.evaluate(f"""
                        (() => {{
                            const currentUserAvatarId = '{current_user_avatar}';
                            const commentItems = document.querySelectorAll('[data-e2e="comment-item"]');
                            
                            for (let item of commentItems) {{
                                const avatarSelectors = ['img.RlLOO79h', '.semi-avatar img', '.comment-item-avatar img', 'img[src*="tos-cn"]', 'img'];
                                
                                for (const selector of avatarSelectors) {{
                                    const imgs = item.querySelectorAll(selector);
                                    for (const img of imgs) {{
                                        if (img.src && img.src.includes('tos-cn')) {{
                                            const match = img.src.match(/tos-cn[^?]+/);
                                            if (match && match[0] === currentUserAvatarId) {{
                                                return true;
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                            return false;
                        }})();
                        """)
                        
                        if quick_check:
                            print(f"    ✅ 发现已有评论，跳过")
                            return False
                
                except Exception as e:
                    print(f"    ⚠️ 滚动失败: {e}")
                
                # 最终检查重复评论
                await page.wait_for_timeout(1500)  # 减少最终检查等待时间
                
                has_commented = await page.evaluate(f"""
                (() => {{
                    const currentUserAvatarId = '{current_user_avatar}';
                    const commentItems = document.querySelectorAll('[data-e2e="comment-item"]');
                    
                    if (commentItems.length === 0) return false;
                    
                    for (let item of commentItems) {{
                        const selectors = ['img.RlLOO79h', '.semi-avatar img', '.comment-item-avatar img', 'img[src*="tos-cn"]', 'img'];
                        
                        for (const selector of selectors) {{
                            const avatarImg = item.querySelector(selector);
                            if (avatarImg && avatarImg.src && avatarImg.src.includes('tos-cn')) {{
                                const match = avatarImg.src.match(/tos-cn[^?]+/);
                                if (match && match[0] === currentUserAvatarId) {{
                                    return true;
                                }}
                            }}
                        }}
                    }}
                    return false;
                }})();
                """)
                
                if has_commented:
                    print("    ✅ 已有评论，跳过")
                    return False
                
                # 发表评论
                print("    💬 发表新评论...")
                try:
                    await page.click(".MUlPwgGV.comment-input-inner-container", timeout=5000)
                    await page.wait_for_timeout(500)  # 减少输入框点击等待时间
                    
                    comment = self.get_random_comment()
                    await page.keyboard.type(comment, delay=100)
                    await page.wait_for_timeout(500)  # 减少输入完成等待时间
                    
                    await page.keyboard.press('Enter')
                    print(f"    ✅ 评论成功: {comment}")
                    await page.wait_for_timeout(1500)  # 减少评论发送等待时间
                    
                    # 检查验证码
                    try:
                        verify_popup = await page.wait_for_selector(".uc-ui-verify_sms-verify", timeout=3000)
                        if verify_popup:
                            print("    ⚠️ 出现验证码，请手动处理...")
                            
                            # 播放手机验证码音频
                            self.audio_manager.play_phone_sound()
                            
                            while True:
                                try:
                                    await page.wait_for_selector(".uc-ui-verify_sms-verify", timeout=1000)
                                    await page.wait_for_timeout(2000)
                                except:
                                    print("    ✅ 验证码处理完成")
                                    break
                    except:
                        pass
                    
                    return True  # 成功发表了新评论
                        
                except Exception as e:
                    print(f"    ❌ 评论失败: {e}")
                    return False
                    
            except Exception as e:
                print(f"    ⚠️ 评论区加载失败: {e}")
                return False
                
        except Exception as e:
            print(f"    ❌ 评论处理失败: {e}")
            return False
    
    async def run_auto_cycle(self, max_cycles: int = None):
        """运行自动化循环"""
        print("🚀 开始自动化循环处理...")
        
        # 清理任何残留的Chromium进程
        initial_count = self.get_chromium_process_count()
        if initial_count > 0:
            print(f"⚠️ 发现 {initial_count} 个残留Chromium进程，开始清理...")
            self.force_cleanup_chromium_processes()
        
        # 获取所有账户
        accounts = self.account_manager.list_accounts()
        if not accounts:
            print("❌ 没有可用的账户！")
            return
        
        # 获取主页地址
        homepage_configs = self.load_homepage_urls()
        if not homepage_configs:
            print("❌ 没有可用的主页地址！")
            return
        
        print(f"📊 找到 {len(accounts)} 个账户，{len(homepage_configs)} 个主页地址")
        
        cycle_count = 0
        try:
            while True:
                cycle_count += 1
                if max_cycles and cycle_count > max_cycles:
                    print(f"🏁 达到最大循环次数 ({max_cycles})，停止")
                    break
                    
                print(f"\n{'='*60}")
                print(f"🔄 第 {cycle_count} 轮循环开始")
                print(f"{'='*60}")
                
                # 监控循环前的进程数量
                before_count = self.get_chromium_process_count()
                print(f"🔍 循环前Chromium进程数: {before_count}")
                
                # 对每个账户
                for account_idx, account in enumerate(accounts, 1):
                    print(f"\n👤 使用账户 {account_idx}/{len(accounts)}: {account['name']}")
                    print(f"📋 该账户将处理所有 {len(homepage_configs)} 个主页地址")
                    
                    try:
                        # 该账户处理所有主页地址（传递配置对象列表）
                        account_total_processed = await self.process_account_with_all_homepages(account, homepage_configs)
                        
                        print(f"\n  📊 账户 {account['name']} 本轮共处理 {account_total_processed} 个新视频")
                        
                        # 检查账户处理后的进程数量
                        after_account_count = self.get_chromium_process_count()
                        print(f"  🔍 账户处理后Chromium进程数: {after_account_count}")
                        
                        # 账户间随机等待（账户切换间）
                        if account_idx < len(accounts):
                            wait_time = 2  # 大幅减少账户切换等待时间
                            print(f"  ⏳ 账户切换等待 {wait_time} 秒...")
                            await asyncio.sleep(wait_time)
                            
                    except Exception as e:
                        print(f"  ❌ 账户 {account['name']} 处理失败: {e}")
                        # 发生错误时强制清理进程
                        self.force_cleanup_chromium_processes()
                        
                        # 播放错误音频
                        self.audio_manager.play_error_sound()
                        
                        continue
                
                # 监控循环后的进程数量
                after_count = self.get_chromium_process_count()
                print(f"\n🔍 循环后Chromium进程数: {after_count}")
                
                # 如果进程数量异常增长，进行清理
                if after_count > before_count + 2:  # 允许少量正常进程
                    print(f"⚠️ 进程数量异常增长 ({before_count} → {after_count})，执行清理...")
                    self.force_cleanup_chromium_processes()
                
                print(f"\n✅ 第 {cycle_count} 轮循环完成")
                
                # 循环间等待
                if not max_cycles or cycle_count < max_cycles:
                    wait_time = random.randint(180, 300)  # 减少循环间等待时间：3-5分钟
                    print(f"⏳ 循环间隔等待 {wait_time//60} 分钟...")
                    await asyncio.sleep(wait_time)
                    
        except KeyboardInterrupt:
            print("\n⏹️ 用户手动停止，正在清理资源...")
            self.force_cleanup_chromium_processes()
            raise
        except Exception as e:
            print(f"\n❌ 循环异常: {e}")
            print("🧹 正在清理资源...")
            self.force_cleanup_chromium_processes()
            raise
        finally:
            # 最终清理
            print("🧹 执行最终资源清理...")
            self.force_cleanup_chromium_processes()

    async def process_single_account_single_homepage(self, account_name: str, homepage_url: str = None) -> int:
        """处理指定账户的指定主页"""
        # 获取账户信息
        accounts = self.account_manager.list_accounts()
        target_account = None
        for acc in accounts:
            if acc['name'] == account_name:
                target_account = acc
                break
        
        if not target_account:
            print(f"❌ 账户 {account_name} 不存在")
            return 0
        
        # 如果没有指定主页URL，让用户选择
        if not homepage_url:
            homepage_configs = self.load_homepage_urls()
            homepage_urls = [config["url"] for config in homepage_configs]  # 为了兼容现有代码
            if not homepage_urls:
                print("❌ 没有可用的主页地址！")
                return 0
            
            print(f"\n📋 可用主页地址:")
            for i, url in enumerate(homepage_urls, 1):
                print(f"  {i}. {url}")
            
            try:
                choice = int(input("\n请选择主页编号: ").strip()) - 1
                if 0 <= choice < len(homepage_urls):
                    homepage_url = homepage_urls[choice]
                else:
                    print("❌ 无效的主页编号")
                    return 0
            except ValueError:
                print("❌ 请输入有效的数字")
                return 0
        
        print(f"\n🎯 开始处理:")
        print(f"  👤 账户: {account_name}")
        print(f"  🏠 主页: {homepage_url}")
        
        total_processed = 0
        browser = None
        context = None
        page = None
        playwright_instance = None
        
        try:
            # 启动浏览器
            playwright_instance = await async_playwright().start()
            browser = await playwright_instance.chromium.launch(headless=False)
            context = await browser.new_context(storage_state=target_account['path'])
            page = await context.new_page()
            
            # 加载该账户已处理的视频
            processed_videos = self.load_processed_videos(account_name)
            
            # 处理指定主页
            newly_processed = await self._process_single_homepage(
                page, target_account, homepage_url, processed_videos
            )
            
            # 保存新处理的视频
            for video_url in newly_processed:
                self.save_processed_video(account_name, video_url)
            
            total_processed = len(newly_processed)
            
            if newly_processed:
                print(f"\n✅ 成功处理 {total_processed} 个新视频")
            else:
                print(f"\n ℹ️ 没有新视频需要处理")
            
            # 播放任务完成音频
            if total_processed > 0:
                self.audio_manager.play_end_sound()
            
            return total_processed
            
        except Exception as e:
            print(f"❌ 处理失败: {e}")
            return total_processed
        finally:
            # 清理资源
            cleanup_success = False
            
            try:
                if page and not page.is_closed():
                    await page.close()
                    cleanup_success = True
            except Exception as e:
                print(f"⚠️ 页面关闭失败: {e}")
            
            try:
                if context:
                    await context.close()
                    cleanup_success = True
            except Exception as e:
                print(f"⚠️ 上下文关闭失败: {e}")
            
            try:
                if browser:
                    await browser.close()
                    cleanup_success = True
            except Exception as e:
                print(f"⚠️ 浏览器关闭失败: {e}")
            
            try:
                if playwright_instance:
                    await playwright_instance.stop()
            except Exception as e:
                print(f"⚠️ Playwright实例关闭失败: {e}")
            
            if not cleanup_success:
                print("🧹 执行强制进程清理...")
                self.force_cleanup_chromium_processes()
            
            await asyncio.sleep(1)
            
            final_count = self.get_chromium_process_count()
            print(f"📊 资源清理后Chromium进程数: {final_count}")

async def main():
    auto_manager = AutoManager()
    
    # 启动时强制清理所有残留进程
    print("🚀 程序启动中...")
    initial_count = auto_manager.get_chromium_process_count()
    if initial_count > 0:
        print(f"⚠️ 发现 {initial_count} 个残留Chromium进程，执行强制清理...")
        auto_manager.force_cleanup_chromium_processes()
        
        # 再次检查
        after_cleanup_count = auto_manager.get_chromium_process_count()
        if after_cleanup_count > 0:
            print(f"⚠️ 仍有 {after_cleanup_count} 个进程未清理，可能需要手动处理")
        else:
            print("✅ 环境清理完成，可以安全启动")
    
    while True:
        print("\n=== 🤖 全自动抖音管理器 ===")
        
        # 显示当前Chromium进程数量
        chromium_count = auto_manager.get_chromium_process_count()
        if chromium_count >= 0:
            print(f"🔍 当前Chromium进程数: {chromium_count}")
            if chromium_count > 5:
                print("⚠️ Chromium进程数量较多，建议清理")
            elif chromium_count > 10:
                print("🚨 Chromium进程数量过多！强烈建议立即清理")
        
        # 显示音频状态
        audio_status = "🔊 开启" if auto_manager.audio_manager.enabled else "🔇 关闭"
        print(f"🎵 音频提醒: {audio_status}")
        
        print("1. 查看配置状态")
        print("2. 管理主页地址库")
        print("3. 管理评论库")
        print("4. 查看已处理视频")
        print("5. 🎯 指定账户处理指定主页（快速模式）")
        print("6. 开始自动化运行")
        print("7. 开始自动化运行（限制循环次数）")
        print("8. 清空已处理视频记录")
        print("9. 查看各账户处理状态")
        print("10. 清理Chromium进程")
        print("11. 📊 查看统计报告")
        print("12. 📋 查看操作日志")
        print("13. 🎵 音频设置")
        print("--- 👤 账户管理 ---") # Add account management section header
        print("14. 列出所有账户") # Add option to list accounts
        print("15. 添加新账户") # Add option to add a new account
        print("16. 切换账户") # Add option to switch account
        print("17. 更新账户Cookies") # Add option to update account cookies
        print("18. 检查账户Cookies有效性") # Add option to check cookie validity
        print("19. 删除账户") # Add option to delete account
        print("0. 退出")
        
        choice = input("\n请选择操作 (0-19): ").strip() # Update input prompt range
        
        try:
            if choice == "1":
                # 查看配置状态
                accounts = auto_manager.account_manager.list_accounts()
                homepage_configs = auto_manager.load_homepage_urls()
                homepage_urls = [config["url"] for config in homepage_configs]
                total_processed = auto_manager.get_all_processed_videos_count()
                chromium_count = auto_manager.get_chromium_process_count()
                
                print(f"\n📊 配置状态:")
                print(f"  - 账户数量: {len(accounts)}")
                for acc in accounts:
                    print(f"    • {acc['name']} {'[当前]' if acc['is_current'] else ''}")
                print(f"  - 主页地址数量: {len(homepage_urls)}")
                print(f"  - 总处理视频数量: {total_processed}")
                print(f"  - Chromium进程数: {chromium_count}")
                
            elif choice == "2":
                # 管理主页地址库
                print(f"\n📝 当前主页地址库:")
                urls = auto_manager.load_homepage_urls()
                for i, url in enumerate(urls, 1):
                    print(f"  {i}. {url}")
                
                print(f"\n请编辑文件: {auto_manager.homepage_urls_file}")
                input("编辑完成后按回车继续...")
                
            elif choice == "3":
                # 管理评论库
                try:
                    with open(auto_manager.comments_file, "r", encoding="utf-8") as f:
                        comments = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                    print(f"\n💬 当前评论库 ({len(comments)} 条):")
                    for i, comment in enumerate(comments, 1):
                        print(f"  {i}. {comment}")
                except:
                    print("\n💬 评论库为空")
                
                print(f"\n请编辑文件: {auto_manager.comments_file}")
                input("编辑完成后按回车继续...")
                
            elif choice == "4":
                # 查看已处理视频（显示所有账户的总和）
                total_processed = auto_manager.get_all_processed_videos_count()
                print(f"\n📹 总处理视频数: {total_processed}")
                print("详细信息请选择选项 9")
                    
            elif choice == "5":
                # 指定账户处理指定主页（快速模式）
                accounts = auto_manager.account_manager.list_accounts()
                if not accounts:
                    print("\n❌ 没有可用的账户！")
                else:
                    print(f"\n👤 可用账户:")
                    for i, acc in enumerate(accounts, 1):
                        current = "【当前账户】" if acc["is_current"] else ""
                        print(f"  {i}. {acc['name']} {current}")
                    
                    try:
                        acc_idx = int(input("\n请选择账户编号: ").strip()) - 1
                        if 0 <= acc_idx < len(accounts):
                            account_name = accounts[acc_idx]["name"]
                            
                            # 询问是否要输入自定义URL
                            print(f"\n选择主页地址方式:")
                            print("1. 从地址库中选择")
                            print("2. 手动输入URL")
                            
                            url_choice = input("请选择 (1-2): ").strip()
                            homepage_url = None
                            
                            if url_choice == "1":
                                # 从地址库选择（在方法内部处理）
                                pass
                            elif url_choice == "2":
                                # 手动输入URL
                                homepage_url = input("请输入主页URL: ").strip()
                                if not homepage_url.startswith("https://www.douyin.com/user/"):
                                    print("❌ 请输入有效的抖音用户主页URL")
                                    continue
                            else:
                                print("❌ 无效选择")
                                continue
                            
                            print(f"\n🚀 开始处理账户 【{account_name}】...")
                            total_processed = await auto_manager.process_single_account_single_homepage(account_name, homepage_url)
                            print(f"\n✅ 处理完成! 成功处理 {total_processed} 个新视频")
                        else:
                            print("\n❌ 无效的账户编号")
                    except ValueError:
                        print("\n❌ 请输入有效的数字")
            
            elif choice == "6":
                # 开始自动化运行
                print("\n🚀 开始无限循环自动化运行...")
                print("⚠️ 按 Ctrl+C 可以停止")
                try:
                    await auto_manager.run_auto_cycle()
                except KeyboardInterrupt:
                    print("\n⏹️ 用户手动停止")
                except Exception as e:
                    print(f"\n❌ 运行异常: {e}")
                finally:
                    # 确保清理资源
                    print("🧹 执行最终清理...")
                    auto_manager.force_cleanup_chromium_processes()
                    
            elif choice == "7":
                # 限制循环次数
                try:
                    cycles = int(input("请输入循环次数: "))
                    print(f"\n🚀 开始自动化运行 ({cycles} 轮循环)...")
                    await auto_manager.run_auto_cycle(max_cycles=cycles)
                except ValueError:
                    print("❌ 请输入有效的数字")
                except Exception as e:
                    print(f"\n❌ 运行异常: {e}")
                finally:
                    # 确保清理资源
                    print("🧹 执行最终清理...")
                    auto_manager.force_cleanup_chromium_processes()
                    
            elif choice == "8":
                # 清空已处理视频记录
                confirm = input("⚠️ 确定要清空所有账户的已处理视频记录吗？(y/N): ").strip().lower()
                if confirm == 'y':
                    # 删除所有账户的已处理文件
                    for processed_file in auto_manager.processed_videos_dir.glob("*_processed.txt"):
                        try:
                            processed_file.unlink()
                            print(f"🗑️ 已清空: {processed_file.name}")
                        except Exception as e:
                            print(f"❌ 清空失败 {processed_file.name}: {e}")
                    print("\n✅ 已处理视频记录已清空")
                else:
                    print("\nℹ️ 操作取消")
            
            elif choice == "9":
                # 查看各账户处理状态 (已处理视频)
                print("\n📊 各账户处理状态:")
                accounts = auto_manager.account_manager.list_accounts()
                if not accounts:
                    print("  没有可用账户")
                else:
                    for acc in accounts:
                        processed_file = auto_manager.get_account_processed_file(acc['name'])
                        try:
                            if processed_file.exists():
                                with open(processed_file, "r", encoding="utf-8") as f:
                                    count = sum(1 for line in f if line.strip() and not line.startswith('#'))
                                print(f"  • 账户 {acc['name']}: 处理 {count} 个视频")
                            else:
                                print(f"  • 账户 {acc['name']}: 暂无记录")
                        except Exception as e:
                            print(f"  ❌ 读取账户 {acc['name']} 记录失败: {e}")
                print("\n详细统计数据请选择选项 11")

            elif choice == "10":
                # 清理Chromium进程
                auto_manager.force_cleanup_chromium_processes()

            elif choice == "11":
                # 查看统计报告
                report = auto_manager.get_statistics_report()
                print(report)

            elif choice == "12":
                # 查看操作日志
                log_files = sorted(auto_manager.logs_dir.glob("*.log"))
                if not log_files:
                    print("\n📋 暂无日志文件")
                else:
                    print("\n📋 可用日志文件:")
                    for i, log_file in enumerate(log_files, 1):
                        print(f"  {i}. {log_file.name}")

                    log_choice = input("\n请输入要查看的日志文件编号 (或输入 'all' 查看全部，'latest' 查看最新，按回车跳过): ").strip()
                    if log_choice.lower() == 'all':
                        for log_file in log_files:
                            print(f"\n--- {log_file.name} ---")
                            try:
                                with open(log_file, "r", encoding="utf-8") as f:
                                    print(f.read())
                            except Exception as e:
                                print(f"❌ 读取日志文件失败: {e}")
                        print("\n--- 日志结束 ---")
                    elif log_choice.lower() == 'latest':
                        latest_log = log_files[-1]
                        print(f"\n--- {latest_log.name} ---")
                        try:
                            with open(latest_log, "r", encoding="utf-8") as f:
                                print(f.read())
                        except Exception as e:
                            print(f"❌ 读取日志文件失败: {e}")
                        print("\n--- 日志结束 ---")
                    elif log_choice.isdigit():
                        log_idx = int(log_choice) - 1
                        if 0 <= log_idx < len(log_files):
                            target_log = log_files[log_idx]
                            print(f"\n--- {target_log.name} ---")
                            try:
                                with open(target_log, "r", encoding="utf-8") as f:
                                    print(f.read())
                            except Exception as e:
                                print(f"❌ 读取日志文件失败: {e}")
                            print("\n--- 日志结束 ---")
                        else:
                            print("\n❌ 无效的日志文件编号")
                    elif log_choice != '':
                        print("\n❌ 无效输入")

            elif choice == "13":
                # 音频设置
                print("\n🎵 音频设置:")
                print(f"当前状态: {'🔊 开启' if auto_manager.audio_manager.enabled else '🔇 关闭'}")
                print("该设置依赖于 pygame 库是否安装。")
                print("安装命令: pip install pygame")
                print("若已安装但仍提示关闭，请检查是否缺少音频文件 (sound/ 目录下)")

            elif choice == "14": # New option: List accounts
                print("\n👤 所有账户列表:")
                accounts = auto_manager.account_manager.list_accounts()
                if not accounts:
                    print("  没有可用的账户")
                else:
                    for i, acc in enumerate(accounts, 1):
                        current = "【当前账户】" if acc["is_current"] else ""
                        print(f"  {i}. {acc['name']} {current}")

            elif choice == "15": # New option: Add new account
                print("\n➕ 添加新账户:")
                try:
                    account_name = input("请输入新账户名称: ").strip()
                    if not account_name:
                        print("❌ 账户名称不能为空")
                        continue
                    print(f"\n请在弹出的浏览器窗口中完成账户 {account_name} 的登录。")
                    print("登录成功后，浏览器会自动关闭。")
                    await auto_manager.account_manager.add_account(account_name)
                    print(f"✅ 账户 {account_name} 添加成功并已自动切换")
                except ValueError as e:
                    print(f"❌ 添加账户失败: {e}")
                except Exception as e:
                    print(f"❌ 添加账户过程中出现错误: {e}")
                    # 播放错误音频
                    auto_manager.audio_manager.play_error_sound()

            elif choice == "16": # New option: Switch account
                print("\n🔄 切换账户:")
                accounts = auto_manager.account_manager.list_accounts()
                if not accounts:
                    print("❌ 没有可用的账户！")
                else:
                    print(f"\n👤 可用账户:")
                    for i, acc in enumerate(accounts, 1):
                        current = "【当前账户】" if acc["is_current"] else ""
                        print(f"  {i}. {acc['name']} {current}")

                    try:
                        acc_idx = int(input("\n请选择要切换的账户编号: ").strip()) - 1
                        if 0 <= acc_idx < len(accounts):
                            account_name = accounts[acc_idx]["name"]
                            auto_manager.account_manager.switch_account(account_name)
                            print(f"✅ 已切换到账户: {account_name}")
                        else:
                            print("\n❌ 无效的账户编号")
                    except ValueError:
                        print("\n❌ 请输入有效的数字")

            elif choice == "17": # New option: Update account cookies
                print("\n🍪 更新账户 Cookies:")
                accounts = auto_manager.account_manager.list_accounts()
                if not accounts:
                    print("❌ 没有可用的账户！")
                else:
                    print(f"\n👤 可用账户:")
                    for i, acc in enumerate(accounts, 1):
                        print(f"  {i}. {acc['name']}")

                    try:
                        acc_idx = int(input("\n请选择要更新 Cookies 的账户编号: ").strip()) - 1
                        if 0 <= acc_idx < len(accounts):
                            account_name = accounts[acc_idx]["name"]
                            print(f"\n请在弹出的浏览器窗口中重新登录账户 {account_name}。")
                            print("更新成功后，浏览器会自动关闭。")
                            await auto_manager.account_manager.update_account_cookies(account_name)
                            print(f"✅ 账户 {account_name} 的 Cookies 更新成功")
                        else:
                            print("\n❌ 无效的账户编号")
                    except ValueError:
                        print("\n❌ 请输入有效的数字")
                    except Exception as e:
                        print(f"❌ 更新 Cookies 过程中出现错误: {e}")
                        # 播放错误音频
                        auto_manager.audio_manager.play_error_sound()

            elif choice == "18": # New option: Check account cookies validity
                print("\n✅ 检查账户 Cookies 有效性:")
                accounts = auto_manager.account_manager.list_accounts()
                if not accounts:
                    print("❌ 没有可用的账户！")
                else:
                    print(f"\n👤 可用账户:")
                    for i, acc in enumerate(accounts, 1):
                        current = "【当前账户】" if acc["is_current"] else ""
                        print(f"  {i}. {acc['name']} {current}")
                    print("  0. 检查所有账户")

                    try:
                        acc_choice = input("\n请选择要检查的账户编号 (0 检查所有): ").strip()
                        if acc_choice == "0":
                            results = await auto_manager.account_manager.check_cookies_validity()
                            print("\n--- Cookies 有效性检查结果 ---")
                            for acc_name, status in results.items():
                                print(f"  账户 {acc_name}: {'✅ 有效' if status['valid'] else '❌ 失效'} ({status['reason']})")
                            print("------------------------------")
                        elif acc_choice.isdigit():
                            acc_idx = int(acc_choice) - 1
                            if 0 <= acc_idx < len(accounts):
                                account_name = accounts[acc_idx]["name"]
                                results = await auto_manager.account_manager.check_cookies_validity(account_name)
                                print("\n--- Cookies 有效性检查结果 ---")
                                for acc_name, status in results.items():
                                    print(f"  账户 {acc_name}: {'✅ 有效' if status['valid'] else '❌ 失效'} ({status['reason']})")
                                print("------------------------------")
                            else:
                                print("\n❌ 无效的账户编号")
                        else:
                            print("\n❌ 无效输入")
                    except ValueError:
                        print("\n❌ 请输入有效的数字")
                    except Exception as e:
                        print(f"❌ 检查 Cookies 过程中出现错误: {e}")
                        # 播放错误音频
                        auto_manager.audio_manager.play_error_sound()

            elif choice == "19": # New option: Delete account
                print("\n🗑️ 删除账户:")
                accounts = auto_manager.account_manager.list_accounts()
                if not accounts:
                    print("❌ 没有可用的账户！")
                else:
                    print(f"\n👤 可用账户:")
                    for i, acc in enumerate(accounts, 1):
                        print(f"  {i}. {acc['name']}")

                    try:
                        acc_idx = int(input("\n请选择要删除的账户编号: ").strip()) - 1
                        if 0 <= acc_idx < len(accounts):
                            account_name = accounts[acc_idx]["name"]
                            confirm = input(f"⚠️ 确定要删除账户 {account_name} 及其所有相关数据吗？(y/N): ").strip().lower()
                            if confirm == 'y':
                                await auto_manager.account_manager.delete_account(account_name)
                                print(f"✅ 账户 {account_name} 已删除")
                            else:
                                print("\nℹ️ 操作取消")
                        else:
                            print("\n❌ 无效的账户编号")
                    except ValueError:
                        print("\n❌ 请输入有效的数字")
                    except Exception as e:
                        print(f"❌ 删除账户过程中出现错误: {e}")
                        # 播放错误音频
                        auto_manager.audio_manager.play_error_sound()

            elif choice == "0":
                # 退出
                print("\n👋 正在退出程序...")
                # 退出前强制清理所有残留进程
                auto_manager.force_cleanup_chromium_processes()
                print("✅ 程序已安全退出")
                break

            else:
                print("\n❌ 无效的选择，请重新输入。")

        except Exception as e:
            print(f"\n❌ 执行操作时出错: {e}")
            # 播放错误音频
            auto_manager.audio_manager.play_error_sound()

        input("\n按回车键继续...") # Add prompt to continue after each operation


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被用户中断.")
    except Exception as e:
        print(f"程序发生未捕获的异常: {e}")
