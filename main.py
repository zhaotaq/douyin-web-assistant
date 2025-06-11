# -*- coding: utf-8 -*-
from datetime import datetime
from playwright.async_api import Playwright, async_playwright, Page
import os
import asyncio

from conf import LOCAL_CHROME_PATH

async def cookie_auth(account_file):
    print(f"[DEBUG] 开始验证cookie文件: {account_file}")
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=account_file)
            # 创建一个新的页面
            page = await context.new_page()
            print("[DEBUG] 正在访问抖音创作者平台...")
            # 访问指定的 URL
            await page.goto("https://creator.douyin.com/creator-micro/content/upload")
            try:
                await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload", timeout=5000)
            except Exception as e:
                print(f"[DEBUG] 等待超时: {str(e)}")
                await context.close()
                await browser.close()
                return False
            # 2024.06.17 抖音创作者中心改版
            if await page.get_by_text('手机号登录').count() or await page.get_by_text('扫码登录').count():
                print("[DEBUG] 检测到登录页面，cookie已失效")
                return False
            else:
                print("[DEBUG] cookie 验证成功")
                return True
    except Exception as e:
        print(f"[ERROR] cookie验证过程出错: {str(e)}")
        return False

async def douyin_setup(account_file, handle=False):
    print(f"[DEBUG] 开始设置，检查文件: {account_file}")
    if not os.path.exists(account_file):
        print("[DEBUG] cookie文件不存在")
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            return False
        print('[DEBUG] 准备获取新的cookie')
        await douyin_cookie_gen(account_file)
    return True

async def douyin_cookie_gen(account_file):
    print("[DEBUG] 开始生成新的cookie")
    try:
        async with async_playwright() as playwright:
            print("[DEBUG] 启动浏览器...")
            browser = await playwright.chromium.launch(
                headless=False,
                args=['--start-maximized']
            )
            context = await browser.new_context(no_viewport=True)
            page = await context.new_page()
            print("[DEBUG] 访问抖音创作者平台...")
            await page.goto("https://creator.douyin.com/")
            print("[DEBUG] 等待用户扫码登录...")
            await page.pause()
            print("[DEBUG] 保存cookie...")
            await context.storage_state(path=account_file)
            print(f"[DEBUG] cookie已保存到: {account_file}")
    except Exception as e:
        print(f"[ERROR] 生成cookie过程出错: {str(e)}")
        raise e 