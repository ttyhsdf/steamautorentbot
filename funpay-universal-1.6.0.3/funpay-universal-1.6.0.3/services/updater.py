from __init__ import ACCENT_COLOR, VERSION, SKIP_UPDATES
import os
import requests
import zipfile
import io
import shutil
from colorama import Fore
from core.console import restart
from logging import getLogger
logger = getLogger(f"universal.updater")


class Updater:
    REPO = "alleexxeeyy/funpay-universal"

    @staticmethod
    def check_for_updates():
        try:
            response = requests.get(f"https://api.github.com/repos/{Updater.REPO}/releases")
            if response.status_code != 200:
                raise Exception(f"Ошибка запроса к GitHub API: {response.status_code}")
            
            releases = response.json()
            latest_release = releases[0]
            versions = [release["tag_name"] for release in releases]
            if VERSION not in versions:
                logger.info(f"Вашей версии {Fore.LIGHTWHITE_EX}{VERSION} {Fore.WHITE}нету в релизах репозитория. Последняя версия: {Fore.LIGHTWHITE_EX}{latest_release['tag_name']}")
                return
            elif VERSION == latest_release["tag_name"]:
                logger.info(f"У вас установлена последняя версия: {Fore.LIGHTWHITE_EX}{VERSION}")
                return
            logger.info(f"{Fore.YELLOW}Доступна новая версия: {Fore.LIGHTWHITE_EX}{latest_release['tag_name']}")
            if SKIP_UPDATES:
                logger.info(f"Пропускаю установку обновления. Если вы хотите автоматически скачивать обновления, измените значение "
                            f"{Fore.LIGHTWHITE_EX}SKIP_UPDATES{Fore.WHITE} на {Fore.YELLOW}False {Fore.WHITE}в файле инициализации {Fore.LIGHTWHITE_EX}(__init__.py)")
                return
            
            logger.info(f"Скачиваю обновление: {Fore.LIGHTWHITE_EX}{latest_release['html_url']}")
            logger.info(f"Загружаю обновление...")
            bytes = Updater.download_update(latest_release)
            if bytes:
                logger.info(f"Устанавливаю обновление...")
                if Updater.install_update(bytes):
                    logger.info(f"✅ Обновление {Fore.LIGHTWHITE_EX}{latest_release['tag_name']} {Fore.YELLOW}было успешно установлено.")
                    restart()
        except Exception as e:
            logger.error(f"{Fore.LIGHTRED_EX}При проверке на наличие обновлений произошла ошибка: {Fore.WHITE}{e}")

    @staticmethod
    def download_update(release_info: str):
        try:
            zip_url = release_info['zipball_url']
            zip_response = requests.get(zip_url)
            if zip_response.status_code != 200:
                raise Exception(f"При скачивании архива обновления произошла ошибка: {zip_response.status_code}")
            return zip_response.content
        except Exception as e:
            logger.error(f"{Fore.LIGHTRED_EX}При скачивании обновления произошла ошибка: {Fore.WHITE}{e}")
            return False
    
    @staticmethod
    def install_update(zip_response_content: bytes):
        temp_dir = ".temp_update"
        try:
            with zipfile.ZipFile(io.BytesIO(zip_response_content), 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                
                archive_root = None
                for item in os.listdir(temp_dir):
                    if os.path.isdir(os.path.join(temp_dir, item)):
                        archive_root = os.path.join(temp_dir, item)
                        break
                if not archive_root:
                    raise Exception("В архиве нет корневой папки!")
                
                for root, _, files in os.walk(archive_root):
                    for file in files:
                        src = os.path.join(root, file)
                        dst = os.path.join('.', os.path.relpath(src, archive_root))
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.copy2(src, dst)
                
                return True
        except Exception as e:
            logger.error(f"{Fore.LIGHTRED_EX}При установке обновления произошла ошибка: {Fore.WHITE}{e}")
            return False
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)