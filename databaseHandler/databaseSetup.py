import sqlite3

from datetime import datetime, timedelta

from logger import logger


class SQLiteDB:
    def __init__(self, db_name="database.db"):
        self.db_name = db_name
        # Open a persistent connection to the database
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.create_table()

    def create_table(self):
        """Create the 'accounts' table if it does not exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT NOT NULL UNIQUE,
                path_to_maFile TEXT NOT NULL,
                login TEXT NOT NULL,
                password TEXT NOT NULL,
                rental_duration INTEGER NOT NULL,
                owner TEXT DEFAULT NULL,
                rental_start TIMESTAMP DEFAULT NULL,
                access_count INTEGER DEFAULT 0,
                max_access_count INTEGER DEFAULT 3,
                last_access TIMESTAMP DEFAULT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS authorized_users (
                user_id INTEGER PRIMARY KEY,
                authorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Таблица для отслеживания покупателей
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_username TEXT NOT NULL,
                account_id INTEGER,
                account_name TEXT,
                purchase_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                rental_duration INTEGER,
                access_count INTEGER DEFAULT 0,
                max_access_count INTEGER DEFAULT 3,
                last_access_time TIMESTAMP DEFAULT NULL,
                feedback_rating INTEGER DEFAULT NULL,
                feedback_text TEXT DEFAULT NULL,
                feedback_time TIMESTAMP DEFAULT NULL,
                rental_extended_count INTEGER DEFAULT 0,
                total_extension_hours INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Миграция для обновления таблицы authorized_users
        self._migrate_authorized_users_table(cursor)
        
        # Миграция для обновления таблицы accounts
        self._migrate_accounts_table(cursor)
        
        # Создаем таблицы для системы платежей
        self._create_payment_tables(cursor)
        
        # Создаем таблицу для привязки FunPay username к Telegram ID
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT NOT NULL,
                funpay_username TEXT NOT NULL,
                bound_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(telegram_id, funpay_username)
            )
            """
        )
        
        self.conn.commit()
        cursor.close()

    def _migrate_authorized_users_table(self, cursor):
        """Миграция таблицы authorized_users для добавления новых полей."""
        try:
            # Проверяем, есть ли уже новые поля
            cursor.execute("PRAGMA table_info(authorized_users)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Добавляем новые поля, если их нет
            if 'username' not in columns:
                cursor.execute("ALTER TABLE authorized_users ADD COLUMN username TEXT")
            if 'first_name' not in columns:
                cursor.execute("ALTER TABLE authorized_users ADD COLUMN first_name TEXT")
            if 'last_name' not in columns:
                cursor.execute("ALTER TABLE authorized_users ADD COLUMN last_name TEXT")
            if 'last_activity' not in columns:
                cursor.execute("ALTER TABLE authorized_users ADD COLUMN last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            if 'is_active' not in columns:
                cursor.execute("ALTER TABLE authorized_users ADD COLUMN is_active BOOLEAN DEFAULT 1")
            if 'permissions' not in columns:
                cursor.execute("ALTER TABLE authorized_users ADD COLUMN permissions TEXT DEFAULT 'user'")
            
            # Обновляем существующие записи
            cursor.execute("UPDATE authorized_users SET last_activity = authorized_at WHERE last_activity IS NULL")
            cursor.execute("UPDATE authorized_users SET is_active = 1 WHERE is_active IS NULL")
            cursor.execute("UPDATE authorized_users SET permissions = 'user' WHERE permissions IS NULL")
            
            logger.info("Migration completed successfully")
        except Exception as e:
            logger.error(f"Migration error: {str(e)}")
            # Если миграция не удалась, пересоздаем таблицу
            cursor.execute("DROP TABLE IF EXISTS authorized_users")
            cursor.execute(
                """
                CREATE TABLE authorized_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    authorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    permissions TEXT DEFAULT 'user'
                )
                """
            )

    def _migrate_accounts_table(self, cursor):
        """Миграция таблицы accounts для добавления полей ограничения доступа."""
        try:
            # Проверяем, есть ли уже новые поля
            cursor.execute("PRAGMA table_info(accounts)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Добавляем новые поля, если их нет
            if 'access_count' not in columns:
                cursor.execute("ALTER TABLE accounts ADD COLUMN access_count INTEGER DEFAULT 0")
            if 'max_access_count' not in columns:
                cursor.execute("ALTER TABLE accounts ADD COLUMN max_access_count INTEGER DEFAULT 3")
            if 'last_access' not in columns:
                cursor.execute("ALTER TABLE accounts ADD COLUMN last_access TIMESTAMP DEFAULT NULL")
            
            logger.info("Accounts table migration completed successfully")
        except Exception as e:
            logger.error(f"Accounts table migration error: {str(e)}")

    def add_account(
        self, account_name, path_to_maFile, login, password, duration, owner=None
    ):
        """Add an account to the database."""
        try:
            # Проверяем, не существует ли уже аккаунт с таким названием
            existing_account = self.get_account_by_name(account_name)
            if existing_account:
                logger.error(f"Account with name '{account_name}' already exists!")
                return False
            
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO accounts (account_name, path_to_maFile, login, password, rental_duration, owner)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (account_name, path_to_maFile, login, password, duration, owner),
            )
            self.conn.commit()
            logger.info(f"Account '{account_name}' added successfully")
            return True
        except Exception as e:
            logger.error(f"Error adding account: {str(e)}")
            return False
        finally:
            cursor.close()

    def delete_account(self, account_id):
        """Delete an account from the database."""
        try:
            cursor = self.conn.cursor()
            
            # Получаем информацию об аккаунте перед удалением
            cursor.execute("SELECT account_name, path_to_maFile FROM accounts WHERE ID = ?", (account_id,))
            account_info = cursor.fetchone()
            
            if not account_info:
                logger.warning(f"Account with ID {account_id} not found")
                return False
            
            account_name, mafile_path = account_info
            
            # Удаляем аккаунт
            cursor.execute("DELETE FROM accounts WHERE ID = ?", (account_id,))
            self.conn.commit()
            
            # Пытаемся удалить .maFile файл
            try:
                import os
                if os.path.exists(mafile_path):
                    os.remove(mafile_path)
                    logger.info(f"Deleted .maFile: {mafile_path}")
            except Exception as file_error:
                logger.warning(f"Could not delete .maFile {mafile_path}: {str(file_error)}")
            
            logger.info(f"Account '{account_name}' (ID: {account_id}) deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting account {account_id}: {str(e)}")
            return False
        finally:
            cursor.close()

    def update_account_mafile(self, account_id, new_mafile_path):
        """Update the .maFile path for an account."""
        try:
            cursor = self.conn.cursor()
            
            # Проверяем существование аккаунта
            cursor.execute("SELECT account_name, path_to_maFile FROM accounts WHERE ID = ?", (account_id,))
            account_info = cursor.fetchone()
            
            if not account_info:
                logger.warning(f"Account with ID {account_id} not found")
                return False
            
            account_name, old_mafile_path = account_info
            
            # Обновляем путь к .maFile
            cursor.execute(
                "UPDATE accounts SET path_to_maFile = ? WHERE ID = ?",
                (new_mafile_path, account_id)
            )
            self.conn.commit()
            
            # Удаляем старый .maFile если он существует и отличается от нового
            try:
                import os
                if old_mafile_path != new_mafile_path and os.path.exists(old_mafile_path):
                    os.remove(old_mafile_path)
                    logger.info(f"Deleted old .maFile: {old_mafile_path}")
            except Exception as file_error:
                logger.warning(f"Could not delete old .maFile {old_mafile_path}: {str(file_error)}")
            
            logger.info(f"Updated .maFile for account '{account_name}' (ID: {account_id}): {new_mafile_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating .maFile for account {account_id}: {str(e)}")
            return False
        finally:
            cursor.close()

    def update_account_info(self, account_id, account_name=None, login=None, password=None, duration=None):
        """Update account information."""
        try:
            cursor = self.conn.cursor()
            
            # Проверяем существование аккаунта
            cursor.execute("SELECT account_name FROM accounts WHERE ID = ?", (account_id,))
            if not cursor.fetchone():
                logger.warning(f"Account with ID {account_id} not found")
                return False
            
            # Строим запрос обновления
            updates = []
            params = []
            
            if account_name is not None:
                updates.append("account_name = ?")
                params.append(account_name)
            
            if login is not None:
                updates.append("login = ?")
                params.append(login)
            
            if password is not None:
                updates.append("password = ?")
                params.append(password)
            
            if duration is not None:
                updates.append("rental_duration = ?")
                params.append(duration)
            
            if not updates:
                logger.warning("No fields to update")
                return False
            
            params.append(account_id)
            
            cursor.execute(
                f"UPDATE accounts SET {', '.join(updates)} WHERE ID = ?",
                params
            )
            self.conn.commit()
            
            logger.info(f"Updated account {account_id} with fields: {', '.join(updates)}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating account {account_id}: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_account_by_id(self, account_id):
        """Get account by ID."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT ID, account_name, path_to_maFile, login, password, rental_duration, owner, rental_start
                FROM accounts 
                WHERE ID = ?
                """,
                (account_id,)
            )
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                return {
                    "id": row[0],
                    "account_name": row[1],
                    "path_to_maFile": row[2],
                    "login": row[3],
                    "password": row[4],
                    "rental_duration": row[5],
                    "owner": row[6],
                    "rental_start": row[7]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting account by ID {account_id}: {str(e)}")
            return None

    def validate_mafile(self, mafile_path):
        """Validate .maFile format and content."""
        try:
            import json
            import os
            
            if not os.path.exists(mafile_path):
                return {"valid": False, "error": "File not found"}
            
            with open(mafile_path, "r", encoding='utf-8') as f:
                data = json.load(f)
            
            required_fields = ["account_name", "shared_secret", "identity_secret", "device_id", "Session"]
            missing_fields = []
            
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
            
            if missing_fields:
                return {"valid": False, "error": f"Missing fields: {', '.join(missing_fields)}"}
            
            if "SteamID" not in data["Session"]:
                return {"valid": False, "error": "Missing SteamID in Session"}
            
            # Проверяем формат shared_secret (должен быть base64)
            try:
                import base64
                base64.b64decode(data["shared_secret"])
            except Exception:
                return {"valid": False, "error": "Invalid shared_secret format (not base64)"}
            
            return {"valid": True, "data": data}
            
        except json.JSONDecodeError:
            return {"valid": False, "error": "Invalid JSON format"}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def can_access_account(self, account_id, username):
        """Проверить, может ли пользователь получить доступ к аккаунту."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT access_count, max_access_count, owner, rental_start, rental_duration
                FROM accounts 
                WHERE id = ? AND owner = ?
                """,
                (account_id, username)
            )
            result = cursor.fetchone()
            
            if not result:
                return {"can_access": False, "reason": "Account not found or not owned by user"}
            
            access_count, max_access_count, owner, rental_start, rental_duration = result
            
            # Проверяем, не истекла ли аренда
            if rental_start:
                from datetime import datetime, timedelta
                start_time = datetime.fromisoformat(rental_start)
                end_time = start_time + timedelta(hours=rental_duration)
                
                if datetime.now() >= end_time:
                    return {"can_access": False, "reason": "Rental period expired"}
            
            # Проверяем лимит доступа
            if access_count >= max_access_count:
                return {"can_access": False, "reason": f"Access limit reached ({access_count}/{max_access_count})"}
            
            return {"can_access": True, "access_count": access_count, "max_access_count": max_access_count}
            
        except Exception as e:
            logger.error(f"Error checking account access: {str(e)}")
            return {"can_access": False, "reason": "Database error"}
        finally:
            cursor.close()

    def increment_access_count(self, account_id, username):
        """Увеличить счетчик доступа к аккаунту."""
        try:
            cursor = self.conn.cursor()
            from datetime import datetime
            
            cursor.execute(
                """
                UPDATE accounts 
                SET access_count = access_count + 1, last_access = ?
                WHERE id = ? AND owner = ?
                """,
                (datetime.now().isoformat(), account_id, username)
            )
            
            self.conn.commit()
            
            # Получаем обновленную информацию
            cursor.execute(
                "SELECT access_count, max_access_count FROM accounts WHERE id = ?",
                (account_id,)
            )
            result = cursor.fetchone()
            
            if result:
                access_count, max_access_count = result
                logger.info(f"Access count incremented for account {account_id}: {access_count}/{max_access_count}")
                return {"success": True, "access_count": access_count, "max_access_count": max_access_count}
            else:
                return {"success": False, "error": "Account not found"}
                
        except Exception as e:
            logger.error(f"Error incrementing access count: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            cursor.close()

    def reset_access_count(self, account_id):
        """Сбросить счетчик доступа к аккаунту (при новой аренде)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE accounts SET access_count = 0, last_access = NULL WHERE id = ?",
                (account_id,)
            )
            self.conn.commit()
            logger.info(f"Access count reset for account {account_id}")
            return True
        except Exception as e:
            logger.error(f"Error resetting access count: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_account_access_info(self, account_id):
        """Получить информацию о доступе к аккаунту."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT access_count, max_access_count, last_access, owner, rental_start, rental_duration
                FROM accounts 
                WHERE id = ?
                """,
                (account_id,)
            )
            result = cursor.fetchone()
            
            if result:
                access_count, max_access_count, last_access, owner, rental_start, rental_duration = result
                return {
                    "access_count": access_count,
                    "max_access_count": max_access_count,
                    "last_access": last_access,
                    "owner": owner,
                    "rental_start": rental_start,
                    "rental_duration": rental_duration
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting account access info: {str(e)}")
            return None
        finally:
            cursor.close()

    def get_unowned_accounts(self):
        """Retrieve all accounts with no owner assigned."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT ID, account_name, path_to_maFile, login, password, rental_duration
            FROM accounts 
            WHERE owner IS NULL
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        accounts = [
            {
                "id": row[0],
                "account_name": row[1],
                "path_to_maFile": row[2],
                "login": row[3],
                "password": row[4],
                "rental_duration": row[5],
            }
            for row in rows
        ]
        return accounts

    def set_account_owner(self, account_id: int, owner_id: str) -> bool:
        """
        Set the owner of an account and record the rental start time with a +3 hours offset.
        Also marks all accounts with the same login as 'OTHER_ACCOUNT'.
        """
        try:
            cursor = self.conn.cursor()
            # Update owner and set rental start time
            cursor.execute(
                """
                UPDATE accounts 
                SET owner = ?, rental_start = DATETIME(CURRENT_TIMESTAMP, '+3 hours', '+10 minutes'), 
                    access_count = 0, last_access = NULL
                WHERE ID = ? AND owner IS NULL
                """,
                (owner_id, account_id),
            )
            if cursor.rowcount == 0:
                return False
            # Get the login of the updated account
            cursor.execute(
                """
                SELECT login 
                FROM accounts 
                WHERE ID = ?
                """,
                (account_id,),
            )
            login_row = cursor.fetchone()
            if login_row:
                login = login_row[0]
                # Mark all accounts with the same login as 'OTHER_ACCOUNT'
                cursor.execute(
                    """
                    UPDATE accounts 
                    SET owner = 'OTHER_ACCOUNT'
                    WHERE login = ? AND owner IS NULL
                    """,
                    (login,),
                )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error setting account owner: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_active_owners(self):
        """Retrieve all unique owner IDs where owner is not NULL."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT owner 
            FROM accounts 
            WHERE owner IS NOT NULL
            """
        )
        owners = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return owners

    def get_owner_mafile(self, owner_id: str) -> list:
        """
        Retrieve the .maFile path and account details from the most recent account
        associated with the given owner ID.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT ID, account_name, path_to_maFile, login, rental_duration
            FROM accounts 
            WHERE owner = ?
            ORDER BY rental_start DESC
            """,
            (owner_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def update_password_by_owner(self, owner_name: str, new_password: str) -> bool:
        """
        Update the password for the most recent account owned by the specified owner.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE accounts 
                SET password = ?
                WHERE owner = ? 
                AND rental_start = (
                    SELECT MAX(rental_start) 
                    FROM accounts 
                    WHERE owner = ?
                )
                """,
                (new_password, owner_name, owner_name),
            )
            success = cursor.rowcount > 0
            self.conn.commit()
            return success
        except Exception as e:
            logger.error(f"Error updating password: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_active_owners_with_mafiles(self):
        """
        Retrieve all unique owner IDs and their associated maFile paths,
        based on the most recent rental_start for each owner.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT a.owner, a.path_to_maFile
            FROM accounts a
            INNER JOIN (
                SELECT owner, MAX(rental_start) as latest_rental
                FROM accounts
                WHERE owner IS NOT NULL
                GROUP BY owner
            ) b ON a.owner = b.owner AND a.rental_start = b.latest_rental
            """
        )
        owners_data = cursor.fetchall()
        cursor.close()
        return owners_data

    def get_all_accounts(self):
        """Retrieve all accounts from the database."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT ID, account_name, path_to_maFile, login, password, rental_duration, owner
            FROM accounts
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        accounts = [
            {
                "id": row[0],
                "account_name": row[1],
                "path_to_maFile": row[2],
                "login": row[3],
                "password": row[4],
                "rental_duration": row[5],
                "owner": row[6],
            }
            for row in rows
        ]
        return accounts

    def delete_account_by_id(self, account_id: int) -> bool:
        """
        Delete all accounts that share the same login as the account with the given ID.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT login
                FROM accounts
                WHERE ID = ?
                """,
                (account_id,),
            )
            result = cursor.fetchone()
            if not result:
                logger.error(f"No account found with ID {account_id}.")
                return False
            login = result[0]
            cursor.execute(
                """
                DELETE FROM accounts
                WHERE login = ?
                """,
                (login,),
            )
            success = cursor.rowcount > 0
            self.conn.commit()
            return success
        except Exception as e:
            logger.error(f"Error deleting accounts: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_total_accounts(self):
        """Retrieve the total number of accounts."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM accounts")
            total_accounts = cursor.fetchone()[0]
            return total_accounts
        except Exception as e:
            logger.error(f"Error retrieving total accounts: {str(e)}")
            return 0
        finally:
            cursor.close()

    def get_all_account_names(self) -> list:
        """Retrieve all distinct account names."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT account_name FROM accounts")
            account_names = [row[0] for row in cursor.fetchall()]
            return account_names
        except Exception as e:
            logger.error(f"Error retrieving account names: {str(e)}")
            return []
        finally:
            cursor.close()

    def get_unowned_account_names(self) -> list:
        """Retrieve account names for accounts with no owner."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT account_name FROM accounts WHERE owner IS NULL")
            unowned_account_names = [row[0] for row in cursor.fetchall()]
            return unowned_account_names
        except Exception as e:
            logger.error(f"Error retrieving unowned account names: {str(e)}")
            return []
        finally:
            cursor.close()

    def get_account_by_name(self, account_name: str):
        """Get account by its name."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT ID, account_name, path_to_maFile, login, password, rental_duration, owner, rental_start
                FROM accounts 
                WHERE account_name = ?
                """,
                (account_name,)
            )
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                return {
                    "id": row[0],
                    "account_name": row[1],
                    "path_to_maFile": row[2],
                    "login": row[3],
                    "password": row[4],
                    "rental_duration": row[5],
                    "owner": row[6],
                    "rental_start": row[7]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting account by name: {str(e)}")
            return None

    def get_account_by_id(self, account_id: int) -> dict:
        """
        Get account details by ID.
        
        Args:
            account_id (int): The ID of the account
            
        Returns:
            dict: Account details or None if not found
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT ID, account_name, path_to_maFile, login, password, 
                       rental_duration, owner, rental_start
                FROM accounts 
                WHERE ID = ?
                """,
                (account_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "account_name": row[1],
                    "path_to_maFile": row[2],
                    "login": row[3],
                    "password": row[4],
                    "rental_duration": row[5],
                    "owner": row[6],
                    "rental_start": row[7],
                }
            return None
        except Exception as e:
            logger.error(f"Error getting account by ID: {str(e)}")
            return None
        finally:
            cursor.close()

    def get_rental_statistics(self) -> dict:
        """
        Get rental statistics for the system.
        
        Returns:
            dict: Statistics including total accounts, active rentals, etc.
        """
        try:
            cursor = self.conn.cursor()
            
            # Total accounts
            cursor.execute("SELECT COUNT(*) FROM accounts")
            total_accounts = cursor.fetchone()[0]
            
            # Active rentals
            cursor.execute("SELECT COUNT(*) FROM accounts WHERE owner IS NOT NULL")
            active_rentals = cursor.fetchone()[0]
            
            # Available accounts
            cursor.execute("SELECT COUNT(*) FROM accounts WHERE owner IS NULL")
            available_accounts = cursor.fetchone()[0]
            
            # Total rental hours
            cursor.execute("SELECT SUM(rental_duration) FROM accounts WHERE owner IS NOT NULL")
            total_hours = cursor.fetchone()[0] or 0
            
            # Recent rentals (last 24 hours)
            cursor.execute(
                """
                SELECT COUNT(*) FROM accounts 
                WHERE owner IS NOT NULL 
                AND rental_start >= datetime('now', '-1 day')
                """
            )
            recent_rentals = cursor.fetchone()[0]
            
            return {
                "total_accounts": total_accounts,
                "active_rentals": active_rentals,
                "available_accounts": available_accounts,
                "total_hours": total_hours,
                "recent_rentals": recent_rentals
            }
        except Exception as e:
            logger.error(f"Error getting rental statistics: {str(e)}")
            return {}
        finally:
            cursor.close()

    def get_user_rental_history(self, owner_id: str) -> list:
        """
        Get rental history for a specific user.
        
        Args:
            owner_id (str): The owner ID to get history for
            
        Returns:
            list: List of rental records
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT ID, account_name, login, rental_duration, rental_start
                FROM accounts 
                WHERE owner = ?
                ORDER BY rental_start DESC
                """,
                (owner_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "account_name": row[1],
                    "login": row[2],
                    "rental_duration": row[3],
                    "rental_start": row[4],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting user rental history: {str(e)}")
            return []
        finally:
            cursor.close()

    def add_time_to_owner_accounts(self, owner: str, hours: int) -> bool:
        """
        Extract the rental_start timestamp, add the specified number of hours to it,
        and update the rental_start field for all accounts with the same owner.
        """
        try:
            cursor = self.conn.cursor()
            # Retrieve the current rental_start timestamps for the owner
            cursor.execute(
                """
                SELECT ID, rental_start
                FROM accounts
                WHERE owner = ? AND rental_start IS NOT NULL
                """,
                (owner,),
            )
            accounts = cursor.fetchall()

            if not accounts:
                logger.info(
                    f"No accounts found for owner {owner} with a valid rental_start."
                )
                return False

            # Update each account with the new timestamp
            for account_id, rental_start in accounts:
                if rental_start:
                    # Parse the timestamp and add the specified hours
                    new_rental_start = datetime.strptime(
                        rental_start, "%Y-%m-%d %H:%M:%S"
                    ) - timedelta(hours=hours)
                    new_rental_start_str = new_rental_start.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                    # Update the database with the new timestamp
                    cursor.execute(
                        """
                        UPDATE accounts
                        SET rental_start = ?
                        WHERE ID = ?
                        """,
                        (new_rental_start_str, account_id),
                    )

            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding hours for owner {owner}: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_active_users(self):
        """
        Retrieve all active users from the database along with their account details.
        An active user is one who has a non-null owner and rental_start time.

        Returns:
            list: A list of dictionaries containing active user details
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT 
                    ID,
                    account_name,
                    owner,
                    rental_start,
                    rental_duration,
                    path_to_maFile,
                    login
                FROM accounts 
                WHERE owner IS NOT NULL 
                AND owner != 'OTHER_ACCOUNT'
                AND rental_start IS NOT NULL
                ORDER BY rental_start DESC
                """
            )
            rows = cursor.fetchall()
            active_users = [
                {
                    "id": row[0],
                    "account_name": row[1],
                    "owner": row[2],
                    "rental_start": row[3],
                    "rental_duration": row[4],
                    "path_to_maFile": row[5],
                    "login": row[6],
                }
                for row in rows
            ]
            return active_users
        except Exception as e:
            logger.error(f"Error retrieving active users: {str(e)}")
            return []
        finally:
            cursor.close()

    def get_user_accounts_by_name(self, owner_id: str, account_name: str) -> list:
        """
        Get active accounts of a specific user by account name.
        
        Args:
            owner_id (str): The owner ID
            account_name (str): The name of the account type
            
        Returns:
            list: List of active accounts with the specified name
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT ID, account_name, login, password, rental_duration, rental_start
                FROM accounts 
                WHERE owner = ? AND account_name = ?
                """,
                (owner_id, account_name),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "account_name": row[1],
                    "login": row[2],
                    "password": row[3],
                    "rental_duration": row[4],
                    "rental_start": row[5],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting user accounts by name: {str(e)}")
            return []
        finally:
            cursor.close()

    def get_user_active_accounts(self, owner_id: str) -> list:
        """
        Get all active accounts of a specific user.
        
        Args:
            owner_id (str): The owner ID
            
        Returns:
            list: List of all active accounts for the user
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT ID, account_name, login, password, rental_duration, rental_start
                FROM accounts 
                WHERE owner = ?
                ORDER BY rental_start DESC
                """,
                (owner_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "account_name": row[1],
                    "login": row[2],
                    "password": row[3],
                    "rental_duration": row[4],
                    "rental_start": row[5],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting user active accounts: {str(e)}")
            return []
        finally:
            cursor.close()

    def close(self):
        """Close the persistent database connection."""
        self.conn.close()

    def add_authorized_user(self, user_id: int, username: str = None, first_name: str = None, 
                           last_name: str = None, permissions: str = 'user') -> bool:
        """Add a user to the authorized users list with detailed information."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO authorized_users 
                (user_id, username, first_name, last_name, authorized_at, last_activity, is_active, permissions)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, ?)
                """,
                (user_id, username, first_name, last_name, permissions),
            )
            self.conn.commit()
            logger.info(f"User {user_id} ({username or 'Unknown'}) added to authorized users")
            return True
        except Exception as e:
            logger.error(f"Error adding authorized user: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_authorized_users(self) -> list:
        """Retrieve all authorized user IDs."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT user_id FROM authorized_users WHERE is_active = 1")
            users = [row[0] for row in cursor.fetchall()]
            return users
        except Exception as e:
            logger.error(f"Error retrieving authorized users: {str(e)}")
            return []
        finally:
            cursor.close()

    def is_user_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT user_id FROM authorized_users WHERE user_id = ? AND is_active = 1",
                (user_id,)
            )
            result = cursor.fetchone()
            return result is not None
        except Exception as e:
            logger.error(f"Error checking user authorization: {str(e)}")
            return False
        finally:
            cursor.close()

    def update_user_activity(self, user_id: int) -> bool:
        """Update user's last activity timestamp."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE authorized_users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,)
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating user activity: {str(e)}")
            return False
        finally:
            cursor.close()

    def get_user_info(self, user_id: int) -> dict:
        """Get detailed user information."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT user_id, username, first_name, last_name, authorized_at, 
                       last_activity, is_active, permissions
                FROM authorized_users WHERE user_id = ?
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "user_id": row[0],
                    "username": row[1],
                    "first_name": row[2],
                    "last_name": row[3],
                    "authorized_at": row[4],
                    "last_activity": row[5],
                    "is_active": bool(row[6]),
                    "permissions": row[7]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user info: {str(e)}")
            return None
        finally:
            cursor.close()

    def get_all_users_info(self) -> list:
        """Get information about all users."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT user_id, username, first_name, last_name, authorized_at, 
                       last_activity, is_active, permissions
                FROM authorized_users ORDER BY authorized_at DESC
                """
            )
            rows = cursor.fetchall()
            return [
                {
                    "user_id": row[0],
                    "username": row[1],
                    "first_name": row[2],
                    "last_name": row[3],
                    "authorized_at": row[4],
                    "last_activity": row[5],
                    "is_active": bool(row[6]),
                    "permissions": row[7]
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting all users info: {str(e)}")
            return []
        finally:
            cursor.close()

    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user (soft delete)."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE authorized_users SET is_active = 0 WHERE user_id = ?",
                (user_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deactivating user: {str(e)}")
            return False
        finally:
            cursor.close()

    def activate_user(self, user_id: int) -> bool:
        """Activate a user."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE authorized_users SET is_active = 1 WHERE user_id = ?",
                (user_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error activating user: {str(e)}")
            return False
        finally:
            cursor.close()

    def update_user_permissions(self, user_id: int, permissions: str) -> bool:
        """Update user permissions."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE authorized_users SET permissions = ? WHERE user_id = ?",
                (permissions, user_id)
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating user permissions: {str(e)}")
            return False
        finally:
            cursor.close()

    def extend_rental_duration(self, account_id: int, additional_hours: int) -> bool:
        """
        Extend the rental duration for a specific account.
        
        Args:
            account_id (int): The ID of the account to extend
            additional_hours (int): Number of hours to add to the rental duration
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE accounts 
                SET rental_duration = rental_duration + ?
                WHERE ID = ? AND owner IS NOT NULL
                """,
                (additional_hours, account_id),
            )
            success = cursor.rowcount > 0
            self.conn.commit()
            
            if success:
                logger.info(f"Rental extended for account {account_id} by {additional_hours} hours")
            
            return success
        except Exception as e:
            logger.error(f"Error extending rental duration: {str(e)}")
            return False
        finally:
            cursor.close()
    
    def get_rental_extension_stats(self, account_id: int) -> dict:
        """
        Get statistics about rental extensions for an account.
        
        Args:
            account_id (int): The ID of the account
            
        Returns:
            dict: Statistics about extensions
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT rental_duration, rental_start, owner
                FROM accounts 
                WHERE ID = ?
                """,
                (account_id,)
            )
            
            result = cursor.fetchone()
            if not result:
                return {"error": "Account not found"}
            
            rental_duration, rental_start, owner = result
            
            # Calculate original duration (assuming base duration is 24 hours)
            # This is a simplified calculation - in real implementation you might want to track this separately
            base_duration = 24  # Default base duration
            extensions = max(0, rental_duration - base_duration)
            
            return {
                "account_id": account_id,
                "current_duration": rental_duration,
                "extensions": extensions,
                "rental_start": rental_start,
                "owner": owner
            }
            
        except Exception as e:
            logger.error(f"Error getting rental extension stats: {str(e)}")
            return {"error": str(e)}
        finally:
            cursor.close()
    
    def log_customer_purchase(self, customer_username: str, account_id: int, account_name: str, rental_duration: int) -> bool:
        """
        Логировать покупку покупателя
        
        Args:
            customer_username (str): Имя пользователя покупателя
            account_id (int): ID аккаунта
            account_name (str): Название аккаунта
            rental_duration (int): Длительность аренды в часах
            
        Returns:
            bool: True если успешно, False иначе
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO customer_activity 
                (customer_username, account_id, account_name, rental_duration, purchase_time)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (customer_username, account_id, account_name, rental_duration)
            )
            self.conn.commit()
            
            logger.info(f"Customer purchase logged: {customer_username} -> {account_name} (ID: {account_id})")
            return True
            
        except Exception as e:
            logger.error(f"Error logging customer purchase: {str(e)}")
            return False
        finally:
            cursor.close()
    
    def log_customer_access(self, customer_username: str, account_id: int) -> bool:
        """
        Логировать доступ к данным аккаунта
        
        Args:
            customer_username (str): Имя пользователя
            account_id (int): ID аккаунта
            
        Returns:
            bool: True если успешно, False иначе
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE customer_activity 
                SET access_count = access_count + 1, 
                    last_access_time = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE customer_username = ? AND account_id = ? AND is_active = TRUE
                """,
                (customer_username, account_id)
            )
            self.conn.commit()
            
            logger.info(f"Customer access logged: {customer_username} -> account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging customer access: {str(e)}")
            return False
        finally:
            cursor.close()
    
    def log_customer_feedback(self, customer_username: str, account_id: int, rating: int, feedback_text: str) -> bool:
        """
        Логировать отзыв покупателя
        
        Args:
            customer_username (str): Имя пользователя
            account_id (int): ID аккаунта
            rating (int): Рейтинг отзыва (1-5)
            feedback_text (str): Текст отзыва
            
        Returns:
            bool: True если успешно, False иначе
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE customer_activity 
                SET feedback_rating = ?, 
                    feedback_text = ?,
                    feedback_time = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE customer_username = ? AND account_id = ? AND is_active = TRUE
                """,
                (rating, feedback_text, customer_username, account_id)
            )
            self.conn.commit()
            
            logger.info(f"Customer feedback logged: {customer_username} -> {rating}/5 for account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging customer feedback: {str(e)}")
            return False
        finally:
            cursor.close()
    
    def log_rental_extension(self, customer_username: str, account_id: int, extension_hours: int) -> bool:
        """
        Логировать продление аренды
        
        Args:
            customer_username (str): Имя пользователя
            account_id (int): ID аккаунта
            extension_hours (int): Количество часов продления
            
        Returns:
            bool: True если успешно, False иначе
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE customer_activity 
                SET rental_extended_count = rental_extended_count + 1,
                    total_extension_hours = total_extension_hours + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE customer_username = ? AND account_id = ? AND is_active = TRUE
                """,
                (extension_hours, customer_username, account_id)
            )
            self.conn.commit()
            
            logger.info(f"Rental extension logged: {customer_username} -> +{extension_hours}h for account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging rental extension: {str(e)}")
            return False
        finally:
            cursor.close()
    
    def get_customer_activity(self, customer_username: str = None, account_id: int = None) -> list:
        """
        Получить активность покупателей
        
        Args:
            customer_username (str, optional): Фильтр по имени пользователя
            account_id (int, optional): Фильтр по ID аккаунта
            
        Returns:
            list: Список записей активности
        """
        try:
            cursor = self.conn.cursor()
            
            if customer_username and account_id:
                cursor.execute(
                    """
                    SELECT * FROM customer_activity 
                    WHERE customer_username = ? AND account_id = ?
                    ORDER BY updated_at DESC
                    """,
                    (customer_username, account_id)
                )
            elif customer_username:
                cursor.execute(
                    """
                    SELECT * FROM customer_activity 
                    WHERE customer_username = ?
                    ORDER BY updated_at DESC
                    """,
                    (customer_username,)
                )
            elif account_id:
                cursor.execute(
                    """
                    SELECT * FROM customer_activity 
                    WHERE account_id = ?
                    ORDER BY updated_at DESC
                    """,
                    (account_id,)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM customer_activity 
                    ORDER BY updated_at DESC
                    """
                )
            
            results = cursor.fetchall()
            
            # Преобразуем в список словарей
            columns = [description[0] for description in cursor.description]
            activity_list = []
            
            for row in results:
                activity_dict = dict(zip(columns, row))
                activity_list.append(activity_dict)
            
            return activity_list
            
        except Exception as e:
            logger.error(f"Error getting customer activity: {str(e)}")
            return []
        finally:
            cursor.close()
    
    def get_customer_stats(self, customer_username: str) -> dict:
        """
        Получить статистику покупателя
        
        Args:
            customer_username (str): Имя пользователя
            
        Returns:
            dict: Статистика покупателя
        """
        try:
            cursor = self.conn.cursor()
            
            # Общая статистика
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total_purchases,
                    SUM(rental_duration) as total_rental_hours,
                    SUM(access_count) as total_accesses,
                    SUM(rental_extended_count) as total_extensions,
                    SUM(total_extension_hours) as total_extension_hours,
                    AVG(feedback_rating) as avg_rating
                FROM customer_activity 
                WHERE customer_username = ? AND is_active = TRUE
                """,
                (customer_username,)
            )
            
            stats = cursor.fetchone()
            
            if stats and stats[0] > 0:
                return {
                    "customer_username": customer_username,
                    "total_purchases": stats[0] or 0,
                    "total_rental_hours": stats[1] or 0,
                    "total_accesses": stats[2] or 0,
                    "total_extensions": stats[3] or 0,
                    "total_extension_hours": stats[4] or 0,
                    "avg_rating": round(stats[5], 2) if stats[5] else None
                }
            else:
                return {
                    "customer_username": customer_username,
                    "total_purchases": 0,
                    "total_rental_hours": 0,
                    "total_accesses": 0,
                    "total_extensions": 0,
                    "total_extension_hours": 0,
                    "avg_rating": None
                }
                
        except Exception as e:
            logger.error(f"Error getting customer stats: {str(e)}")
            return {}
        finally:
            cursor.close()
    
    def deactivate_customer_activity(self, customer_username: str, account_id: int) -> bool:
        """
        Деактивировать активность покупателя (при завершении аренды)
        
        Args:
            customer_username (str): Имя пользователя
            account_id (int): ID аккаунта
            
        Returns:
            bool: True если успешно, False иначе
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                UPDATE customer_activity 
                SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE customer_username = ? AND account_id = ? AND is_active = TRUE
                """,
                (customer_username, account_id)
            )
            self.conn.commit()
            
            logger.info(f"Customer activity deactivated: {customer_username} -> account {account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deactivating customer activity: {str(e)}")
            return False
        finally:
            cursor.close()
    
    def _create_payment_tables(self, cursor):
        """Создает таблицы для системы платежей и подписок."""
        try:
            # Таблица балансов пользователей
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_balances (
                    user_id INTEGER PRIMARY KEY,
                    balance DECIMAL(10, 2) DEFAULT 0.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            
            # Таблица подписок пользователей
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    plan_id TEXT NOT NULL,
                    subscription_end TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
                """
            )
            
            # Таблица транзакций
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_transactions (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    amount DECIMAL(10, 2) NOT NULL,
                    currency TEXT DEFAULT 'RUB',
                    payment_method TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    paid_at TIMESTAMP NULL,
                    description TEXT DEFAULT ''
                )
                """
            )
            
            # Таблица настроек платежей
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            
            logger.info("Payment tables created successfully")
            
        except Exception as e:
            logger.error(f"Error creating payment tables: {str(e)}")
            self.conn.rollback()
