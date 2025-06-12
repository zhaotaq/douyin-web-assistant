# -*- coding: utf-8 -*-
from datetime import datetime
from playwright.async_api import Playwright, async_playwright, Page
import os
import asyncio

from conf import LOCAL_CHROME_PATH

async def cookie_auth(storage_state):
    """
    使用给定的 storage_state (可以是文件路径或字典) 验证Cookie是否有效。
    """
    print(f"[DEBUG] 开始验证cookie...")
    if not storage_state:
        print("[DEBUG] storage_state为空，无法验证。")
        return False
        
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            # new_context 可以接受路径或字典对象
            context = await browser.new_context(storage_state=storage_state)
            page = await context.new_page()
            print("[DEBUG] 正在访问抖音创作者平台...")
            await page.goto("https://creator.douyin.com/creator-micro/content/upload")
            try:
                # 等待页面加载完成的标志，而不是URL，因为URL可能因为重定向而不变
                await page.locator('//div[contains(@class, "upload-btn")]//input[@name="upload-input"]').wait_for(timeout=5000)
                print("[DEBUG] cookie 验证成功 (找到上传按钮)。")
                return True
            except Exception:
                # 检查是否跳转到了登录页
                if await page.get_by_text('手机号登录').count() or await page.get_by_text('扫码登录').count():
                    print("[DEBUG] 检测到登录页面，cookie已失效。")
                    return False
                else:
                    # 如果既没有找到上传按钮，也没找到登录按钮，可能页面有变动或加载缓慢
                    print("[DEBUG] 未能明确验证cookie状态，可能页面结构已更新。")
                    return False
    except Exception as e:
        print(f"[ERROR] cookie验证过程出错: {str(e)}")
        return False
    finally:
        if 'browser' in locals() and browser.is_connected():
            await browser.close()


async def douyin_setup(path=None, headless=False, handle=False):
    """
    设置并验证抖音cookie。
    :param path: cookie文件的保存路径。如果为None，则直接返回cookie数据。
    :param headless: 是否以无头模式运行浏览器。
    :param handle: 当cookie无效或不存在时，是否启动手动获取流程。
    :return: 如果path不为None，返回布尔值。如果path为None，返回cookie字典或None。
    """
    print(f"[DEBUG] 开始设置，路径: {'无' if path is None else path}")
    
    # 检查cookie是否存在且有效
    cookie_is_valid = False
    if path and os.path.exists(path):
        cookie_is_valid = await cookie_auth(path)

    if not cookie_is_valid:
        if not handle:
            print("[DEBUG] Cookie无效且未配置手动处理，设置失败。")
            return None if path is None else False
        
        print('[DEBUG] Cookie无效或不存在，准备获取新的cookie...')
        return await douyin_cookie_gen(path=path, headless=headless)
    
    print("[DEBUG] 现有Cookie有效，设置完成。")
    if path is None:
        # 如果一开始就没有提供path，但走到这里意味着逻辑有问题，因为无法验证一个不存在的cookie
        # 但为严谨起见，返回None
        return None
    return True


async def douyin_cookie_gen(path=None, headless=False):
    """
    通过手动登录生成新的抖音cookie。
    :param path: cookie文件的保存路径。如果为None，则直接返回cookie数据。
    :param headless: 是否以无头模式运行浏览器。
    :return: 如果path不为None，返回布尔值。如果path为None，返回cookie字典或None。
    """
    print("[DEBUG] 开始生成新的cookie...")
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=headless,
                args=['--start-maximized'] if not headless else []
            )
            context = await browser.new_context(no_viewport=True)
            page = await context.new_page()
            print("[DEBUG] 访问抖音创作者平台...")
            await page.goto("https://creator.douyin.com/")
            print("[DEBUG] 请在浏览器中手动扫码登录...")
            
            # 等待用户成功登录，通过检查页面是否不再是登录页来判断
            # 等待上传入口出现作为登录成功的标志
            try:
                await page.locator('//div[contains(@class, "upload-btn")]//input[@name="upload-input"]').wait_for(timeout=120000) # 等待2分钟
                print("[DEBUG] 用户登录成功！")
            except Exception:
                print("[ERROR] 等待用户登录超时（2分钟），未能获取Cookie。")
                await browser.close()
                return None if path is None else False

            if path:
                print(f"[DEBUG] 保存cookie到文件: {path}...")
                await context.storage_state(path=path)
                print(f"[DEBUG] cookie已保存。")
                return True
            else:
                print("[DEBUG] 直接返回cookie数据...")
                cookie_data = await context.storage_state()
                return cookie_data
    except Exception as e:
        print(f"[ERROR] 生成cookie过程出错: {str(e)}")
        return None if path is None else False
    finally:
        if 'browser' in locals() and browser.is_connected():
            await browser.close() 