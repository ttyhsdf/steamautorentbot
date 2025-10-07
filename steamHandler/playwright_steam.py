#!/usr/bin/env python3
"""
Продвинутая Steam интеграция с Playwright
Автоматизация браузера для работы с Steam аккаунтами
"""

import os
import asyncio
import tempfile
import shutil
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, List
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None
    Browser = None
    BrowserContext = None
    Page = None
    PLAYWRIGHT_AVAILABLE = False

from logger import logger

class PlaywrightSteamManager:
    """Менеджер для работы с Steam через Playwright"""
    
    def __init__(self, headless: bool = True, debug: bool = False):
        self.headless = headless
        self.debug = debug
        self.sessions_dir = Path("sessions")
        self.screenshots_dir = Path("screenshots")
        self.sessions_dir.mkdir(exist_ok=True)
        self.screenshots_dir.mkdir(exist_ok=True)
        
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not available. Install with: pip install playwright")
    
    async def get_browser_context(self, login: str, password: str, 
                                email_login: str = None, email_password: str = None,
                                imap_host: str = None) -> Tuple[BrowserContext, Page]:
        """Создает контекст браузера с авторизацией в Steam"""
        try:
            async with async_playwright() as p:
                # Конфигурация браузера
                browser_config = {
                    "headless": self.headless,
                    "args": [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-extensions",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-renderer-backgrounding",
                        "--disable-features=TranslateUI",
                        "--disable-ipc-flooding-protection",
                        "--disable-web-security",
                        "--disable-features=VizDisplayCompositor",
                        "--no-first-run",
                        "--no-default-browser-check"
                    ]
                }
                
                # Запускаем браузер
                browser = await p.chromium.launch(**browser_config)
                
                # Создаем контекст
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    locale="ru-RU",
                    timezone_id="Europe/Moscow"
                )
                
                # Создаем страницу
                page = await context.new_page()
                
                # Настраиваем таймауты
                page.set_default_timeout(30000)
                page.set_default_navigation_timeout(30000)
                
                # Авторизуемся в Steam
                success = await self._steam_login(page, login, password, email_login, email_password, imap_host)
                
                if success:
                    # Сохраняем сессию
                    await self._save_session(context, login)
                    logger.info(f"Steam login successful for {login}")
                    return context, page
                else:
                    await browser.close()
                    raise Exception("Steam login failed")
                    
        except Exception as e:
            logger.error(f"Error creating browser context: {e}")
            raise
    
    async def _steam_login(self, page: Page, login: str, password: str, 
                          email_login: str = None, email_password: str = None,
                          imap_host: str = None) -> bool:
        """Выполняет авторизацию в Steam"""
        try:
            # Переходим на страницу входа
            await page.goto("https://store.steampowered.com/login/")
            await page.wait_for_load_state("networkidle")
            
            # Вводим логин
            await page.fill("input[name='username']", login)
            await page.fill("input[name='password']", password)
            
            # Нажимаем кнопку входа
            await page.click("input[type='submit']")
            await page.wait_for_load_state("networkidle")
            
            # Проверяем, нужен ли Steam Guard
            if await self._handle_steam_guard(page, email_login, email_password, imap_host):
                # Проверяем успешность входа
                if await self._is_logged_in(page):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Steam login error: {e}")
            return False
    
    async def _handle_steam_guard(self, page: Page, email_login: str = None, 
                                 email_password: str = None, imap_host: str = None) -> bool:
        """Обрабатывает Steam Guard код"""
        try:
            # Проверяем, есть ли поле для Steam Guard
            guard_input = await page.query_selector("input[name='twofactorcode']")
            if not guard_input:
                return True  # Steam Guard не требуется
            
            # Получаем код из email если есть данные
            if email_login and email_password and imap_host:
                code = await self._get_steam_guard_code_from_email(email_login, email_password, imap_host)
                if code:
                    await page.fill("input[name='twofactorcode']", code)
                    await page.click("input[type='submit']")
                    await page.wait_for_load_state("networkidle")
                    return True
            
            # Если нет email данных, ждем ручного ввода
            logger.warning("Steam Guard required but no email credentials provided")
            return False
            
        except Exception as e:
            logger.error(f"Steam Guard handling error: {e}")
            return False
    
    async def _get_steam_guard_code_from_email(self, email_login: str, email_password: str, 
                                             imap_host: str) -> Optional[str]:
        """Получает Steam Guard код из email"""
        try:
            # Здесь должна быть интеграция с email клиентом
            # Пока возвращаем None для совместимости
            logger.info("Email Steam Guard code retrieval not implemented yet")
            return None
        except Exception as e:
            logger.error(f"Email Steam Guard code error: {e}")
            return None
    
    async def _is_logged_in(self, page: Page) -> bool:
        """Проверяет, авторизован ли пользователь"""
        try:
            # Проверяем наличие элементов, указывающих на успешную авторизацию
            profile_link = await page.query_selector("a[href*='/profiles/']")
            return profile_link is not None
        except Exception as e:
            logger.error(f"Login check error: {e}")
            return False
    
    async def _save_session(self, context: BrowserContext, login: str):
        """Сохраняет сессию браузера"""
        try:
            session_file = self.sessions_dir / f"steam_session_{login}.json"
            await context.storage_state(path=str(session_file))
            logger.info(f"Session saved for {login}")
        except Exception as e:
            logger.error(f"Session save error: {e}")
    
    async def load_session(self, login: str) -> Optional[Tuple[BrowserContext, Page]]:
        """Загружает сохраненную сессию"""
        try:
            session_file = self.sessions_dir / f"steam_session_{login}.json"
            if not session_file.exists():
                return None
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(storage_state=str(session_file))
                page = await context.new_page()
                
                # Проверяем, действительна ли сессия
                await page.goto("https://store.steampowered.com/")
                if await self._is_logged_in(page):
                    return context, page
                else:
                    await browser.close()
                    return None
                    
        except Exception as e:
            logger.error(f"Session load error: {e}")
            return None
    
    async def change_steam_password(self, context: BrowserContext, page: Page, 
                                  new_password: str, account_name: str) -> Tuple[bool, List[str], List[str]]:
        """Меняет пароль Steam аккаунта"""
        logs = []
        screenshots = []
        
        try:
            logs.append(f"[STEAM] Starting password change for {account_name}")
            
            # Переходим на страницу настроек аккаунта
            await page.goto("https://store.steampowered.com/account/")
            await page.wait_for_load_state("networkidle")
            
            # Ищем ссылку на изменение пароля
            change_password_link = await page.query_selector("a[href*='changepassword']")
            if not change_password_link:
                logs.append("[STEAM] Change password link not found")
                return False, logs, screenshots
            
            # Переходим на страницу смены пароля
            await change_password_link.click()
            await page.wait_for_load_state("networkidle")
            
            # Делаем скриншот
            screenshot_path = self.screenshots_dir / f"password_change_start_{account_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=str(screenshot_path))
            screenshots.append(str(screenshot_path))
            
            # Вводим новый пароль
            current_password_field = await page.query_selector("input[name='currentPassword']")
            new_password_field = await page.query_selector("input[name='newPassword']")
            confirm_password_field = await page.query_selector("input[name='confirmPassword']")
            
            if not all([current_password_field, new_password_field, confirm_password_field]):
                logs.append("[STEAM] Password fields not found")
                return False, logs, screenshots
            
            # Заполняем поля
            await current_password_field.fill("")  # Текущий пароль (пустой для сброса)
            await new_password_field.fill(new_password)
            await confirm_password_field.fill(new_password)
            
            logs.append(f"[STEAM] Password fields filled for {account_name}")
            
            # Нажимаем кнопку подтверждения
            submit_button = await page.query_selector("input[type='submit']")
            if submit_button:
                await submit_button.click()
                await page.wait_for_load_state("networkidle")
                
                # Делаем финальный скриншот
                screenshot_path = self.screenshots_dir / f"password_change_result_{account_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await page.screenshot(path=str(screenshot_path))
                screenshots.append(str(screenshot_path))
                
                # Проверяем успешность
                success_text = await page.query_selector("text=successfully")
                if success_text:
                    logs.append(f"[STEAM] Password changed successfully for {account_name}")
                    return True, logs, screenshots
                else:
                    logs.append("[STEAM] Password change may have failed")
                    return False, logs, screenshots
            else:
                logs.append("[STEAM] Submit button not found")
                return False, logs, screenshots
                
        except Exception as e:
            logs.append(f"[STEAM] Password change error: {e}")
            return False, logs, screenshots
    
    async def logout_all_sessions(self, context: BrowserContext, page: Page) -> bool:
        """Выходит из всех сессий Steam"""
        try:
            # Переходим на страницу управления сессиями
            await page.goto("https://store.steampowered.com/account/")
            await page.wait_for_load_state("networkidle")
            
            # Ищем ссылку на управление сессиями
            sessions_link = await page.query_selector("a[href*='sessions']")
            if sessions_link:
                await sessions_link.click()
                await page.wait_for_load_state("networkidle")
                
                # Ищем кнопку выхода из всех сессий
                logout_all_button = await page.query_selector("input[value*='logout']")
                if logout_all_button:
                    await logout_all_button.click()
                    await page.wait_for_load_state("networkidle")
                    logger.info("Logged out from all Steam sessions")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Logout all sessions error: {e}")
            return False
    
    async def get_account_info(self, context: BrowserContext, page: Page) -> Optional[Dict]:
        """Получает информацию об аккаунте"""
        try:
            await page.goto("https://store.steampowered.com/account/")
            await page.wait_for_load_state("networkidle")
            
            # Извлекаем информацию об аккаунте
            account_info = {}
            
            # Steam ID
            steam_id_element = await page.query_selector("text=/Steam ID: \\d+/")
            if steam_id_element:
                steam_id_text = await steam_id_element.text_content()
                account_info['steam_id'] = steam_id_text.split(': ')[1] if ': ' in steam_id_text else None
            
            # Имя пользователя
            username_element = await page.query_selector(".account_name")
            if username_element:
                account_info['username'] = await username_element.text_content()
            
            # Уровень аккаунта
            level_element = await page.query_selector(".level")
            if level_element:
                account_info['level'] = await level_element.text_content()
            
            return account_info
            
        except Exception as e:
            logger.error(f"Get account info error: {e}")
            return None
    
    async def cleanup(self, context: BrowserContext):
        """Очищает ресурсы"""
        try:
            if context:
                await context.close()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

# Утилиты для работы с Playwright
class PlaywrightUtils:
    """Утилиты для работы с Playwright"""
    
    @staticmethod
    async def take_screenshot(page: Page, name: str, screenshots_dir: Path) -> str:
        """Делает скриншот страницы"""
        try:
            screenshot_path = screenshots_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=str(screenshot_path))
            return str(screenshot_path)
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return ""
    
    @staticmethod
    async def wait_for_element(page: Page, selector: str, timeout: int = 10000) -> bool:
        """Ждет появления элемента на странице"""
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"Wait for element error: {e}")
            return False
    
    @staticmethod
    async def safe_click(page: Page, selector: str) -> bool:
        """Безопасно кликает по элементу"""
        try:
            element = await page.query_selector(selector)
            if element:
                await element.click()
                return True
            return False
        except Exception as e:
            logger.error(f"Safe click error: {e}")
            return False
    
    @staticmethod
    async def safe_fill(page: Page, selector: str, text: str) -> bool:
        """Безопасно заполняет поле"""
        try:
            element = await page.query_selector(selector)
            if element:
                await element.fill(text)
                return True
            return False
        except Exception as e:
            logger.error(f"Safe fill error: {e}")
            return False
