import json
import os
import random  # 添加random模块用于随机选择评论
from datetime import datetime
from pathlib import Path
import asyncio

from conf import BASE_DIR
from main import douyin_setup, cookie_auth
from playwright.async_api import async_playwright

class AccountManager:
    def __init__(self):
        self.accounts_dir = BASE_DIR / "cookies" / "douyin_uploader" / "accounts"
        self.accounts_dir.mkdir(parents=True, exist_ok=True)
        self.current_account_file = self.accounts_dir.parent / "current_account.txt"
        self.video_data_dir = BASE_DIR / "cookies" / "douyin_uploader" / "video_data"
        self.video_data_dir.mkdir(parents=True, exist_ok=True)
        self.comments_file = BASE_DIR / "comments_pool.txt"  # 添加评论池文件路径
    
    def list_accounts(self):
        """列出所有账户"""
        accounts = []
        if self.accounts_dir.exists():
            for file in self.accounts_dir.glob("*.json"):
                account_name = file.stem
                accounts.append({
                    "name": account_name,
                    "path": str(file),
                    "is_current": self._is_current_account(account_name)
                })
        return accounts
    
    def _is_current_account(self, account_name):
        """检查是否是当前账户"""
        if not self.current_account_file.exists():
            return False
        with open(self.current_account_file, "r", encoding="utf-8") as f:
            current = f.read().strip()
            return current == account_name
    
    def get_current_account(self):
        """获取当前账户信息"""
        if not self.current_account_file.exists():
            return None
        with open(self.current_account_file, "r", encoding="utf-8") as f:
            current = f.read().strip()
            account_file = self.accounts_dir / f"{current}.json"
            if account_file.exists():
                return {
                    "name": current,
                    "path": str(account_file)
                }
        return None
    
    def switch_account(self, account_name):
        """切换到指定账户"""
        account_file = self.accounts_dir / f"{account_name}.json"
        if not account_file.exists():
            raise ValueError(f"账户 {account_name} 不存在")
        
        with open(self.current_account_file, "w", encoding="utf-8") as f:
            f.write(account_name)
        return {
            "name": account_name,
            "path": str(account_file)
        }
    
    async def add_account(self, account_name):
        """添加新账户"""
        # 检查账户名是否已存在
        account_file = self.accounts_dir / f"{account_name}.json"
        if account_file.exists():
            raise ValueError(f"账户 {account_name} 已存在")
        
        # 获取新账户的 cookies
        print(f"[DEBUG] 开始获取账户 {account_name} 的 cookies")
        cookie_setup = await douyin_setup(str(account_file), handle=True)
        
        if cookie_setup:
            # 自动切换到新账户
            return self.switch_account(account_name)
        else:
            raise Exception("获取 cookies 失败")

    async def update_account_cookies(self, account_name):
        """更新指定账户的cookies"""
        account_file = self.accounts_dir / f"{account_name}.json"
        if not account_file.exists():
            raise ValueError(f"账户 {account_name} 不存在")
        
        print(f"[INFO] 开始更新账户 【{account_name}】 的 cookies...")
        print("      请在打开的浏览器中重新登录该账户")
        
        # 备份原有cookies
        backup_file = self.accounts_dir / f"{account_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        if account_file.exists():
            with open(account_file, "r", encoding="utf-8") as f:
                backup_data = f.read()
            with open(backup_file, "w", encoding="utf-8") as f:
                f.write(backup_data)
            print(f"[INFO] 原cookies已备份到: {backup_file.name}")
        
        # 获取新的cookies
        cookie_setup = await douyin_setup(str(account_file), handle=True)
        
        if cookie_setup:
            print(f"[SUCCESS] 账户 【{account_name}】 cookies更新成功!")
            return True
        else:
            # 如果失败，恢复备份
            if backup_file.exists():
                with open(backup_file, "r", encoding="utf-8") as f:
                    backup_data = f.read()
                with open(account_file, "w", encoding="utf-8") as f:
                    f.write(backup_data)
                print(f"[INFO] cookies更新失败，已恢复原cookies")
            raise Exception("更新 cookies 失败")

    async def check_cookies_validity(self, account_name=None):
        """检查cookies有效性"""
        if account_name:
            accounts_to_check = [account_name]
        else:
            # 检查所有账户
            all_accounts = self.list_accounts()
            accounts_to_check = [acc["name"] for acc in all_accounts]
        
        if not accounts_to_check:
            print("没有找到任何账户")
            return {}
        
        print(f"正在检查 {len(accounts_to_check)} 个账户的cookies有效性...")
        results = {}
        
        async with async_playwright() as playwright:
            for account in accounts_to_check:
                account_file = self.accounts_dir / f"{account}.json"
                if not account_file.exists():
                    results[account] = {"valid": False, "reason": "账户文件不存在"}
                    continue
                
                print(f"  检查账户: {account}")
                try:
                    browser = await playwright.chromium.launch(headless=True)
                    context = await browser.new_context(storage_state=str(account_file))
                    page = await context.new_page()
                    
                    # 访问抖音主页检查登录状态
                    await page.goto("https://www.douyin.com/", timeout=30000)
                    await page.wait_for_timeout(3000)
                    
                    # 检查是否有登录用户头像
                    user_avatar = await page.query_selector('img.RlLOO79h')
                    if user_avatar:
                        results[account] = {"valid": True, "reason": "cookies有效"}
                        print(f"    ✅ 有效")
                    else:
                        results[account] = {"valid": False, "reason": "未检测到登录状态"}
                        print(f"    ❌ 失效")
                    
                    await browser.close()
                    
                except Exception as e:
                    results[account] = {"valid": False, "reason": f"检查失败: {str(e)}"}
                    print(f"    ❌ 检查失败: {e}")
                    try:
                        await browser.close()
                    except:
                        pass
        
        return results

    async def delete_account(self, account_name):
        """删除指定账户"""
        account_file = self.accounts_dir / f"{account_name}.json"
        if not account_file.exists():
            raise ValueError(f"账户 {account_name} 不存在")
        
        # 如果是当前账户，清除当前账户记录
        if self._is_current_account(account_name):
            if self.current_account_file.exists():
                self.current_account_file.unlink()
        
        # 删除账户文件
        account_file.unlink()
        
        # 删除相关的视频数据
        account_video_dir = self.video_data_dir / account_name
        if account_video_dir.exists():
            import shutil
            shutil.rmtree(account_video_dir)
        
        print(f"账户 【{account_name}】 及相关数据已删除")

    async def extract_videos_from_current_page(self):
        """从用户指定的URL提取视频信息并保存（全自动）"""
        current_account = self.get_current_account()
        if not current_account:
            print("\n请先切换到一个账户。")
            return

        account_name = current_account["name"]
        account_cookie_file = current_account["path"]

        print(f"\n准备为账户 【{account_name}】 提取视频信息。")
        
        target_url = input("请输入目标抖音用户主页的URL (例如: https://www.douyin.com/user/MS4wLjABAAAAxxxx): ").strip()
        if not target_url:
            print("\nURL 不能为空。")
            return

        if not target_url.startswith("https://www.douyin.com/user/"):
            print("\n请输入一个有效的抖音用户主页URL。")
            return

        print(f"\n正在尝试从 {target_url} 提取视频信息... (这可能需要一些时间)")

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=False) # 设置为 False，使用有头模式
                context = await browser.new_context(storage_state=account_cookie_file)
                page = await context.new_page()

                await page.goto(target_url, wait_until="domcontentloaded", timeout=60000) # 修改 wait_until 条件

                # 尝试滚动页面加载更多视频
                scroll_attempts = 5 # 可以根据需要调整滚动次数
                for i in range(scroll_attempts):
                    print(f"  滚动页面 ({i+1}/{scroll_attempts})...")
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    await page.wait_for_timeout(3000) # 等待3秒让内容加载

                js_code = """
                (function() {
                    const videoListElement = document.querySelector('ul.e6wsjNLL.bGEvyQfj[data-e2e="scroll-list"]');
                    if (!videoListElement) {
                        return JSON.stringify({error: '找不到视频列表元素 (ul.e6wsjNLL.bGEvyQfj)。请确保URL正确或页面结构未改变。'});
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
                    return videos; // 直接返回数组
                })();
                """
                
                videos_data = await page.evaluate(js_code)

                await browser.close()

                if isinstance(videos_data, dict) and 'error' in videos_data:
                    print(f"\nJavaScript 执行出错: {videos_data['error']}")
                    return

                if not videos_data:
                    print("\n没有提取到任何视频信息。可能是页面结构已更改，或者没有视频。")
                    return

                print(f"\n成功提取到 {len(videos_data)} 个视频的信息:")
                for i, video in enumerate(videos_data):
                    print(f"  {i+1}. 标题: {video['title']}, 链接: {video['link']}")

                # 保存数据
                account_video_dir = self.video_data_dir / account_name
                account_video_dir.mkdir(parents=True, exist_ok=True)
                
                now = datetime.now()
                filename = now.strftime("%Y-%m-%d_%H-%M-%S") + ".json"
                save_path = account_video_dir / filename
                
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(videos_data, f, ensure_ascii=False, indent=4)
                
                print(f"\n视频信息已保存到: {save_path}")

                # 开始处理点赞和评论
                if videos_data:
                    print("\n开始处理视频点赞和评论...")
                    
                    async with async_playwright() as p_like:
                        browser_like = await p_like.chromium.launch(headless=False)
                        context_like = await browser_like.new_context(storage_state=account_cookie_file)
                        page_like = await context_like.new_page()

                        try:
                            for i, video_info in enumerate(videos_data):
                                video_url = video_info["link"]
                                video_title = video_info["title"]
                                print(f"\n处理视频 {i+1}/{len(videos_data)}: {video_title[:50]}...")
                                print(f"  导航到: {video_url}")
                                
                                try:
                                    await page_like.goto(video_url, wait_until="domcontentloaded", timeout=60000)
                                    await page_like.wait_for_timeout(3000)

                                    # JavaScript 来判断是否已点赞
                                    check_like_js = """
                                    (function() {
                                        const actionBar = document.querySelector('div.xi78nG8b'); // 操作栏容器
                                        if (!actionBar) return { error: '未找到操作栏 (div.xi78nG8b)' };

                                        // 尝试找到点赞的SVG图标
                                        let likeIconSvg = null;
                                        const primarySvgContainer = actionBar.querySelector('.KMIJp86N.CPXV46AA');
                                        if (primarySvgContainer) {
                                            likeIconSvg = primarySvgContainer.querySelector('svg');
                                        }

                                        if (!likeIconSvg) {
                                            const fallbackContainer = actionBar.querySelector('._BMsHw2S > div:first-child');
                                            if (fallbackContainer) {
                                                likeIconSvg = fallbackContainer.querySelector('svg');
                                            }
                                        }

                                        if (!likeIconSvg) return { error: '未找到点赞SVG图标元素。可能页面结构已改变。' };

                                        const paths = likeIconSvg.querySelectorAll('path');
                                        if (paths.length === 0) return { error: '在点赞SVG中未找到path元素。' };

                                        const likedColor = 'rgb(254, 44, 85)'; // 已点赞的红色

                                        for (let path of paths) {
                                            // 1. 优先检查 path 元素的 'fill' HTML属性
                                            const attributeFill = path.getAttribute('fill');
                                            if (attributeFill && attributeFill.trim().toLowerCase() === likedColor) {
                                                return { liked: true, method: 'attribute' };
                                            }

                                            // 2. 检查计算后的样式中的 'fill'
                                            try {
                                                const computedFill = window.getComputedStyle(path).getPropertyValue('fill');
                                                if (computedFill && computedFill.trim().toLowerCase() === likedColor) {
                                                    return { liked: true, method: 'computedStyle' };
                                                }
                                            } catch (e) {
                                                // 忽略 getComputedStyle 可能出现的错误，继续检查下一个path
                                            }
                                        }
                                        return { liked: false }; // 未找到红色填充，视为未点赞
                                    })();
                                    """
                                    like_status = await page_like.evaluate(check_like_js)

                                    if like_status.get('error'):
                                        print(f"  无法判断点赞状态: {like_status['error']}")
                                    elif like_status.get('liked'):
                                        print("  状态: 已点赞，跳过。")
                                    else:
                                        print("  状态: 未点赞，尝试点赞...")
                                        # 尝试找到可点击的点赞按钮区域
                                        like_button_selector_1 = '.xi78nG8b .KMIJp86N.CPXV46AA'
                                        like_button_selector_2 = '.xi78nG8b ._BMsHw2S > div[tabindex="0"]' 
                                        
                                        try:
                                            await page_like.click(like_button_selector_1, timeout=5000)
                                            print("  通过选择器1点击点赞按钮成功。")
                                        except Exception:
                                            try:
                                                await page_like.click(like_button_selector_2, timeout=5000)
                                                print("  通过选择器2点击点赞按钮成功。")
                                            except Exception as e_click:
                                                print(f"  尝试点击点赞按钮失败: {e_click}。尝试使用键盘 press 'Z'。")
                                                await page_like.keyboard.press('Z')
                                        
                                        await page_like.wait_for_timeout(2000)

                                    # 检查是否已评论的功能
                                    print("  检查是否已经评论过...")
                                    try:
                                        # 获取当前登录用户的头像URL
                                        get_current_user_avatar_js = """
                                        () => {
                                            const headerAvatar = document.querySelector('img.RlLOO79h');
                                            if (!headerAvatar) {
                                                return null;
                                            }
                                            const avatarUrl = headerAvatar.src;
                                            const match = avatarUrl.match(/tos-cn[^?]+/);
                                            return match ? match[0] : avatarUrl;
                                        }
                                        """
                                        current_user_avatar = await page_like.evaluate(get_current_user_avatar_js)
                                        
                                        if not current_user_avatar:
                                            print("  无法获取当前用户头像，跳过评论检查")
                                        else:
                                            print(f"  成功获取当前用户头像标识: {current_user_avatar}")

                                            # 等待评论区元素加载
                                            comment_section_selector = '[data-e2e="comment-list"], .HV3aiR5J.comment-mainContent'
                                            try:
                                                print(f"  等待评论区加载...")
                                                await page_like.wait_for_selector(comment_section_selector, state='visible', timeout=7000)
                                                print("  评论区已加载。")

                                                # 额外等待，确保内容完全加载
                                                await page_like.wait_for_timeout(3000)
                                                
                                                # 添加滚动功能以确保所有评论加载
                                                print("  尝试滚动评论区以加载所有评论...")
                                                try:
                                                    # 点击评论区获得焦点
                                                    comment_section = await page_like.wait_for_selector(comment_section_selector, timeout=5000)
                                                    await comment_section.click()
                                                    await page_like.wait_for_timeout(1000)
                                                    
                                                    # 使用PageDown键滚动，这是经测试有效的方法
                                                    for scroll_i in range(3):
                                                        print(f"    滚动尝试 {scroll_i+1}/3")
                                                        await page_like.keyboard.press('PageDown')
                                                        await page_like.wait_for_timeout(2000)
                                                        
                                                        # 检查是否能找到重复评论（快速检查）
                                                        quick_check = await page_like.evaluate(f"""
                                                        (() => {{
                                                            const currentUserAvatarId = '{current_user_avatar}';
                                                            const commentItems = document.querySelectorAll('[data-e2e="comment-item"]');
                                                            
                                                            for (let item of commentItems) {{
                                                                const avatarSelectors = [
                                                                    'img.RlLOO79h',
                                                                    '.semi-avatar img',
                                                                    '.comment-item-avatar img',
                                                                    'img[src*="tos-cn"]',
                                                                    'img'
                                                                ];
                                                                
                                                                for (const selector of avatarSelectors) {{
                                                                    const imgs = item.querySelectorAll(selector);
                                                                    for (const img of imgs) {{
                                                                        if (img.src && img.src.includes('tos-cn')) {{
                                                                            const match = img.src.match(/tos-cn[^?]+/);
                                                                            if (match && match[0] === currentUserAvatarId) {{
                                                                                return true; // 找到重复评论，可以提前退出滚动
                                                                            }}
                                                                        }}
                                                                    }}
                                                                }}
                                                            }}
                                                            return false;
                                                        }})();
                                                        """)
                                                        
                                                        if quick_check:
                                                            print(f"    ✅ 滚动第{scroll_i+1}次后发现重复评论，停止滚动")
                                                            break
                                                        else:
                                                            print(f"    第{scroll_i+1}次滚动后未发现重复评论，继续滚动")
                                                
                                                    print("  滚动完成。")
                                                except Exception as scroll_e:
                                                    print(f"  滚动失败: {scroll_e}，但继续执行检测")
                                                
                                                # 等待头像元素实际加载
                                                await page_like.wait_for_timeout(3000)
                                                
                                                # 检查评论区是否存在相同头像  
                                                check_comment_exists_js = f"""
(() => {{
    console.log('=== 开始检查重复评论 ===');
    const currentUserAvatarId = '{current_user_avatar}';
    console.log('当前用户头像ID:', currentUserAvatarId);
    
    const commentItems = document.querySelectorAll('[data-e2e="comment-item"]');
    console.log('找到评论项数量:', commentItems.length);
    
    if (commentItems.length === 0) {{
        console.log('没有找到评论项');
        return false;
    }}
    
    // 检查是否存在匹配的头像
    for (let i = 0; i < commentItems.length; i++) {{
        const item = commentItems[i];
        console.log(`检查评论项 ${{i+1}}`);
        
        // 尝试多种选择器，确保找到头像
        const selectors = [
            'img.RlLOO79h',
            '.semi-avatar img', 
            '.comment-item-avatar img',
            'img[src*="tos-cn"]',
            'img'
        ];
        
        let foundAvatar = false;
        for (const selector of selectors) {{
            const avatarImg = item.querySelector(selector);
            if (avatarImg && avatarImg.src) {{
                console.log(`  选择器 "${{selector}}" 找到头像: ${{avatarImg.src.substring(0, 80)}}...`);
                
                if (avatarImg.src.includes('tos-cn')) {{
                    const match = avatarImg.src.match(/tos-cn[^?]+/);
                    if (match) {{
                        const avatarId = match[0];
                        console.log(`  提取的头像ID: ${{avatarId}}`);
                        console.log(`  当前用户ID: ${{currentUserAvatarId}}`);
                        
                        // 比较头像ID
                        if (avatarId === currentUserAvatarId) {{
                            console.log(`  🎯 匹配成功！这是当前用户的评论`);
                            return true;
                        }}
                        foundAvatar = true;
                        break;
                    }}
                }}
            }}
        }}
        
        if (!foundAvatar) {{
            console.log('  ❌ 未找到有效头像');
        }}
    }}
    
    console.log('=== 检查完成：无重复评论 ===');
    return false;
}})();
"""
                                                
                                                js_result = await page_like.evaluate(check_comment_exists_js)
                                                print(f"  JavaScript执行结果: {js_result}")
                                                
                                                if js_result:
                                                    print("  检测到已经评论过，跳过评论")
                                                    continue # 跳到下一个视频
                                                
                                                print("  未发现已有评论，继续评论流程")
                                            
                                            except Exception as e_wait_comment:
                                                print(f"  等待评论区加载或JavaScript执行失败: {e_wait_comment}")
                                                print("  将假定未评论并尝试发表评论。")
                                            
                                            # 尝试发表评论...
                                            print("  尝试发表评论...")
                                            try:
                                                # 点击评论框
                                                await page_like.click(".MUlPwgGV.comment-input-inner-container", timeout=5000)
                                                await page_like.wait_for_timeout(1000)  # 等待评论框完全展开
                                                
                                                # 获取随机评论
                                                comment = self.get_random_comment()
                                                
                                                # 输入评论内容
                                                await page_like.keyboard.type(comment, delay=100)  # 添加延迟模拟真实输入
                                                await page_like.wait_for_timeout(1000)  # 等待输入完成
                                                
                                                # 使用Enter键发送评论，替换原来的点击发送按钮
                                                await page_like.keyboard.press('Enter')
                                                print(f"  评论发送成功: {comment}")
                                                await page_like.wait_for_timeout(2000)  # 等待评论发送完成

                                                # 检查是否出现验证码弹窗
                                                try:
                                                    # 检查验证码弹窗
                                                    verify_popup = await page_like.wait_for_selector(".uc-ui-verify_sms-verify", timeout=3000)
                                                    if verify_popup:
                                                        print("\n检测到验证码弹窗，等待手动输入验证码...")
                                                        print("请在手机上查看验证码并输入:")
                                                        
                                                        # 等待用户手动处理验证码
                                                        while True:
                                                            # 检查验证码弹窗是否还存在
                                                            try:
                                                                await page_like.wait_for_selector(".uc-ui-verify_sms-verify", timeout=1000)
                                                                await page_like.wait_for_timeout(2000)  # 每2秒检查一次
                                                            except:
                                                                print("验证码验证完成，继续处理...")
                                                                break
                                                        
                                                        # 验证完成后等待一下
                                                        await page_like.wait_for_timeout(2000)
                                                except:
                                                    # 没有出现验证码弹窗，继续处理
                                                    pass

                                            except Exception as comment_e:
                                                print(f"  发表评论失败: {comment_e}")
                                    
                                    except Exception as check_e:
                                        print(f"  检查评论状态时出错: {check_e}")

                                except Exception as video_e:
                                    print(f"  处理视频 {video_url} 时出错: {video_e}")
                        
                        finally:
                            await page_like.close()
                            await context_like.close()
                            await browser_like.close()
                            
                    print("\n所有视频点赞和评论处理完毕。")

        except Exception as e:
            print(f"\n提取视频信息过程中发生错误: {e}")
            print("  可能的原因包括：")
            print("  - 目标URL无效或无法访问。")
            print("  - 网络问题或超时。")
            print("  - 当前账户的Cookie已失效 (请尝试重新添加账户或切换账户后重试)。")
            print("  - 抖音页面结构发生重大变化。")

    def get_random_comment(self):
        """从评论池中随机获取一条评论"""
        if not self.comments_file.exists():
            return "好视频，支持一下！"  # 默认评论
        
        with open(self.comments_file, "r", encoding="utf-8") as f:
            comments = f.read().strip().split("\n")
            return random.choice(comments) if comments else "好视频，支持一下！"

async def main():
    manager = AccountManager()
    
    while True:
        print("\n=== 抖音账户管理器 ===")
        print("1. 列出所有账户")
        print("2. 添加新账户")
        print("3. 切换账户")
        print("4. 显示当前账户")
        print("5. 获取当前页面视频信息")
        print("6. 更新账户cookies")
        print("7. 检查cookies有效性")
        print("8. 删除账户")
        print("0. 退出")
        
        choice = input("\n请选择操作 (0-8): ").strip()
        
        try:
            if choice == "1":
                accounts = manager.list_accounts()
                if not accounts:
                    print("\n当前没有保存的账户")
                else:
                    print("\n账户列表:")
                    for acc in accounts:
                        current = "【当前账户】" if acc["is_current"] else ""
                        print(f"- {acc['name']} {current}")
            
            elif choice == "2":
                name = input("请输入新账户名称: ").strip()
                if name:
                    print("\n请在打开的浏览器中完成登录...")
                    account = await manager.add_account(name)
                    print(f"\n成功添加并切换到账户: {account['name']}")
                else:
                    print("\n账户名称不能为空")
            
            elif choice == "3":
                accounts = manager.list_accounts()
                if not accounts:
                    print("\n当前没有保存的账户")
                else:
                    print("\n可用账户:")
                    for i, acc in enumerate(accounts, 1):
                        current = "【当前账户】" if acc["is_current"] else ""
                        print(f"{i}. {acc['name']} {current}")
                    
                    idx = input("\n请选择要切换的账户编号: ").strip()
                    try:
                        idx = int(idx) - 1
                        if 0 <= idx < len(accounts):
                            account = manager.switch_account(accounts[idx]["name"])
                            print(f"\n已切换到账户: {account['name']}")
                        else:
                            print("\n无效的账户编号")
                    except ValueError:
                        print("\n请输入有效的数字")
            
            elif choice == "4":
                current = manager.get_current_account()
                if current:
                    print(f"\n当前账户: {current['name']}")
                else:
                    print("\n当前未选择账户")
            
            elif choice == "5":
                await manager.extract_videos_from_current_page()

            elif choice == "6":
                # 更新账户cookies
                accounts = manager.list_accounts()
                if not accounts:
                    print("\n当前没有保存的账户")
                else:
                    print("\n可用账户:")
                    for i, acc in enumerate(accounts, 1):
                        current = "【当前账户】" if acc["is_current"] else ""
                        print(f"{i}. {acc['name']} {current}")
                    
                    idx = input("\n请选择要更新cookies的账户编号: ").strip()
                    try:
                        idx = int(idx) - 1
                        if 0 <= idx < len(accounts):
                            await manager.update_account_cookies(accounts[idx]["name"])
                        else:
                            print("\n无效的账户编号")
                    except ValueError:
                        print("\n请输入有效的数字")

            elif choice == "7":
                # 检查cookies有效性
                print("\n检查选项:")
                print("1. 检查所有账户")
                print("2. 检查指定账户")
                check_choice = input("请选择 (1-2): ").strip()
                
                if check_choice == "1":
                    results = await manager.check_cookies_validity()
                    print("\n=== Cookies检查结果 ===")
                    for account, result in results.items():
                        status = "✅ 有效" if result["valid"] else "❌ 失效"
                        print(f"{account}: {status} - {result['reason']}")
                
                elif check_choice == "2":
                    accounts = manager.list_accounts()
                    if not accounts:
                        print("\n当前没有保存的账户")
                    else:
                        print("\n可用账户:")
                        for i, acc in enumerate(accounts, 1):
                            print(f"{i}. {acc['name']}")
                        
                        idx = input("\n请选择要检查的账户编号: ").strip()
                        try:
                            idx = int(idx) - 1
                            if 0 <= idx < len(accounts):
                                account_name = accounts[idx]["name"]
                                results = await manager.check_cookies_validity(account_name)
                                result = results[account_name]
                                status = "✅ 有效" if result["valid"] else "❌ 失效"
                                print(f"\n{account_name}: {status} - {result['reason']}")
                            else:
                                print("\n无效的账户编号")
                        except ValueError:
                            print("\n请输入有效的数字")

            elif choice == "8":
                # 删除账户
                accounts = manager.list_accounts()
                if not accounts:
                    print("\n当前没有保存的账户")
                else:
                    print("\n可用账户:")
                    for i, acc in enumerate(accounts, 1):
                        current = "【当前账户】" if acc["is_current"] else ""
                        print(f"{i}. {acc['name']} {current}")
                    
                    idx = input("\n请选择要删除的账户编号: ").strip()
                    try:
                        idx = int(idx) - 1
                        if 0 <= idx < len(accounts):
                            account_name = accounts[idx]["name"]
                            confirm = input(f"\n确认删除账户 【{account_name}】 吗？(输入 'yes' 确认): ").strip()
                            if confirm.lower() == 'yes':
                                await manager.delete_account(account_name)
                            else:
                                print("\n取消删除操作")
                        else:
                            print("\n无效的账户编号")
                    except ValueError:
                        print("\n请输入有效的数字")

            elif choice == "0":
                print("\n再见！")
                break
            
            else:
                print("\n无效的选择，请重试")
                
        except Exception as e:
            print(f"\n操作出错: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 