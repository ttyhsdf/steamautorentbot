#!/usr/bin/env python3
"""
Утилита для массового управления аккаунтами Steam
Позволяет удалять, заменять .maFile и проверять аккаунты
"""

import os
import sys
import json
import shutil
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from databaseHandler.databaseSetup import SQLiteDB
from logger import logger

class AccountManager:
    """Менеджер для управления аккаунтами Steam"""
    
    def __init__(self):
        self.db = SQLiteDB()
        self.accounts_dir = "accounts"
        self.backup_dir = "backups"
        
        # Создаем директории если их нет
        os.makedirs(self.accounts_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def list_all_accounts(self):
        """Показать все аккаунты в системе"""
        try:
            accounts = self.db.get_all_accounts()
            
            if not accounts:
                print("📋 Список аккаунтов пуст")
                return
            
            print(f"📋 Всего аккаунтов: {len(accounts)}")
            print("=" * 80)
            
            for i, account in enumerate(accounts, 1):
                status = "🔴 В аренде" if account['owner'] else "🟢 Свободен"
                owner_info = f"Владелец: {account['owner']}" if account['owner'] else "Свободен"
                
                print(f"{i:2d}. {account['account_name']}")
                print(f"    ID: {account['id']}")
                print(f"    Логин: {account['login']}")
                print(f"    Продолжительность: {account['rental_duration']}ч")
                print(f"    Статус: {status}")
                print(f"    {owner_info}")
                print(f"    .maFile: {account['path_to_maFile']}")
                print("-" * 40)
                
        except Exception as e:
            logger.error(f"Error listing accounts: {str(e)}")
            print(f"❌ Ошибка при получении списка аккаунтов: {str(e)}")
    
    def delete_account(self, account_id):
        """Удалить аккаунт по ID"""
        try:
            account = self.db.get_account_by_id(account_id)
            if not account:
                print(f"❌ Аккаунт с ID {account_id} не найден")
                return False
            
            print(f"🗑 Удаление аккаунта: {account['account_name']}")
            print(f"   ID: {account['id']}")
            print(f"   Логин: {account['login']}")
            print(f"   .maFile: {account['path_to_maFile']}")
            
            # Подтверждение
            confirm = input("\n⚠️  Вы уверены? Это действие необратимо! (yes/no): ")
            if confirm.lower() != 'yes':
                print("❌ Отменено")
                return False
            
            # Удаляем аккаунт
            success = self.db.delete_account(account_id)
            
            if success:
                print("✅ Аккаунт успешно удален")
                return True
            else:
                print("❌ Ошибка при удалении аккаунта")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting account {account_id}: {str(e)}")
            print(f"❌ Ошибка при удалении аккаунта: {str(e)}")
            return False
    
    def replace_mafile(self, account_id, new_mafile_path):
        """Заменить .maFile для аккаунта"""
        try:
            account = self.db.get_account_by_id(account_id)
            if not account:
                print(f"❌ Аккаунт с ID {account_id} не найден")
                return False
            
            if not os.path.exists(new_mafile_path):
                print(f"❌ Файл .maFile не найден: {new_mafile_path}")
                return False
            
            print(f"📁 Замена .maFile для аккаунта: {account['account_name']}")
            print(f"   Текущий: {account['path_to_maFile']}")
            print(f"   Новый: {new_mafile_path}")
            
            # Проверяем новый .maFile
            validation_result = self.db.validate_mafile(new_mafile_path)
            if not validation_result["valid"]:
                print(f"❌ Неверный .maFile: {validation_result['error']}")
                return False
            
            print("✅ .maFile валиден")
            
            # Создаем резервную копию старого файла
            if os.path.exists(account['path_to_maFile']):
                backup_path = os.path.join(self.backup_dir, f"backup_{account_id}_{int(time.time())}.maFile")
                shutil.copy2(account['path_to_maFile'], backup_path)
                print(f"💾 Создана резервная копия: {backup_path}")
            
            # Копируем новый файл
            new_filename = f"account_{account_id}_{int(time.time())}.maFile"
            new_filepath = os.path.join(self.accounts_dir, new_filename)
            shutil.copy2(new_mafile_path, new_filepath)
            
            # Обновляем в базе данных
            success = self.db.update_account_mafile(account_id, new_filepath)
            
            if success:
                print(f"✅ .maFile успешно заменен: {new_filepath}")
                return True
            else:
                print("❌ Ошибка при обновлении базы данных")
                return False
                
        except Exception as e:
            logger.error(f"Error replacing mafile for account {account_id}: {str(e)}")
            print(f"❌ Ошибка при замене .maFile: {str(e)}")
            return False
    
    def validate_mafile(self, mafile_path):
        """Проверить .maFile"""
        try:
            if not os.path.exists(mafile_path):
                print(f"❌ Файл не найден: {mafile_path}")
                return False
            
            print(f"🔍 Проверка .maFile: {mafile_path}")
            
            validation_result = self.db.validate_mafile(mafile_path)
            
            if validation_result["valid"]:
                data = validation_result["data"]
                print("✅ .maFile валиден!")
                print(f"   Аккаунт: {data['account_name']}")
                print(f"   Steam ID: {data['Session']['SteamID']}")
                print(f"   Device ID: {data['device_id']}")
                return True
            else:
                print(f"❌ .maFile невалиден: {validation_result['error']}")
                return False
                
        except Exception as e:
            logger.error(f"Error validating mafile {mafile_path}: {str(e)}")
            print(f"❌ Ошибка при проверке .maFile: {str(e)}")
            return False
    
    def cleanup_unused_accounts(self):
        """Очистить неиспользуемые аккаунты"""
        try:
            accounts = self.db.get_all_accounts()
            unused_accounts = [acc for acc in accounts if not acc['owner']]
            
            if not unused_accounts:
                print("🧹 Неиспользуемых аккаунтов не найдено")
                return
            
            print(f"🧹 Найдено {len(unused_accounts)} неиспользуемых аккаунтов:")
            for acc in unused_accounts:
                print(f"   • {acc['account_name']} (ID: {acc['id']})")
            
            confirm = input("\n⚠️  Удалить все неиспользуемые аккаунты? (yes/no): ")
            if confirm.lower() != 'yes':
                print("❌ Отменено")
                return
            
            deleted_count = 0
            for acc in unused_accounts:
                if self.db.delete_account(acc['id']):
                    deleted_count += 1
                    print(f"✅ Удален: {acc['account_name']}")
                else:
                    print(f"❌ Ошибка удаления: {acc['account_name']}")
            
            print(f"\n✅ Удалено {deleted_count} из {len(unused_accounts)} аккаунтов")
            
        except Exception as e:
            logger.error(f"Error cleaning up accounts: {str(e)}")
            print(f"❌ Ошибка при очистке аккаунтов: {str(e)}")
    
    def batch_validate_mafiles(self):
        """Проверить все .maFile в системе"""
        try:
            accounts = self.db.get_all_accounts()
            
            if not accounts:
                print("📋 Аккаунтов не найдено")
                return
            
            print(f"🔍 Проверка {len(accounts)} .maFile файлов...")
            print("=" * 60)
            
            valid_count = 0
            invalid_count = 0
            
            for account in accounts:
                mafile_path = account['path_to_maFile']
                print(f"Проверка: {account['account_name']}")
                
                if not os.path.exists(mafile_path):
                    print(f"   ❌ Файл не найден: {mafile_path}")
                    invalid_count += 1
                    continue
                
                validation_result = self.db.validate_mafile(mafile_path)
                if validation_result["valid"]:
                    print(f"   ✅ Валиден")
                    valid_count += 1
                else:
                    print(f"   ❌ Невалиден: {validation_result['error']}")
                    invalid_count += 1
                
                print("-" * 30)
            
            print(f"\n📊 Результаты проверки:")
            print(f"   ✅ Валидных: {valid_count}")
            print(f"   ❌ Невалидных: {invalid_count}")
            print(f"   📈 Процент валидных: {valid_count/len(accounts)*100:.1f}%")
            
        except Exception as e:
            logger.error(f"Error batch validating mafiles: {str(e)}")
            print(f"❌ Ошибка при массовой проверке .maFile: {str(e)}")
    
    def export_accounts(self, filename="accounts_export.json"):
        """Экспортировать все аккаунты в JSON"""
        try:
            accounts = self.db.get_all_accounts()
            
            if not accounts:
                print("📋 Аккаунтов для экспорта не найдено")
                return
            
            # Убираем чувствительные данные
            export_data = []
            for account in accounts:
                export_account = {
                    "id": account["id"],
                    "account_name": account["account_name"],
                    "login": account["login"],
                    "rental_duration": account["rental_duration"],
                    "owner": account["owner"],
                    "rental_start": account["rental_start"],
                    "path_to_maFile": account["path_to_maFile"]
                }
                export_data.append(export_account)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Экспорт завершен: {filename}")
            print(f"   Экспортировано {len(export_data)} аккаунтов")
            
        except Exception as e:
            logger.error(f"Error exporting accounts: {str(e)}")
            print(f"❌ Ошибка при экспорте: {str(e)}")

def main():
    """Главное меню утилиты"""
    manager = AccountManager()
    
    while True:
        print("\n" + "=" * 60)
        print("🔧 МЕНЕДЖЕР АККАУНТОВ STEAM")
        print("=" * 60)
        print("1. 📋 Список всех аккаунтов")
        print("2. 🗑 Удалить аккаунт")
        print("3. 📁 Заменить .maFile")
        print("4. 🔍 Проверить .maFile")
        print("5. 🧹 Очистить неиспользуемые")
        print("6. 🔍 Массовая проверка .maFile")
        print("7. 📤 Экспорт аккаунтов")
        print("8. ❌ Выход")
        print("=" * 60)
        
        choice = input("Выберите действие (1-8): ").strip()
        
        if choice == "1":
            manager.list_all_accounts()
        
        elif choice == "2":
            try:
                account_id = int(input("Введите ID аккаунта для удаления: "))
                manager.delete_account(account_id)
            except ValueError:
                print("❌ Неверный формат ID")
        
        elif choice == "3":
            try:
                account_id = int(input("Введите ID аккаунта: "))
                mafile_path = input("Введите путь к новому .maFile: ").strip()
                manager.replace_mafile(account_id, mafile_path)
            except ValueError:
                print("❌ Неверный формат ID")
        
        elif choice == "4":
            mafile_path = input("Введите путь к .maFile для проверки: ").strip()
            manager.validate_mafile(mafile_path)
        
        elif choice == "5":
            manager.cleanup_unused_accounts()
        
        elif choice == "6":
            manager.batch_validate_mafiles()
        
        elif choice == "7":
            filename = input("Введите имя файла для экспорта (по умолчанию: accounts_export.json): ").strip()
            if not filename:
                filename = "accounts_export.json"
            manager.export_accounts(filename)
        
        elif choice == "8":
            print("👋 До свидания!")
            break
        
        else:
            print("❌ Неверный выбор")

if __name__ == "__main__":
    import time
    main()
