"""
Работа с базой данных SQLite
"""
import aiosqlite
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import DB_PATH

class Database:
    """Класс для работы с БД"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
    
    async def init_db(self):
        """Инициализация таблиц"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    role TEXT DEFAULT 'user',
                    balance REAL DEFAULT 0,
                    stars_balance INTEGER DEFAULT 0,
                    registered_at TIMESTAMP,
                    last_activity TIMESTAMP,
                    total_purchases INTEGER DEFAULT 0,
                    total_sales INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # Таблица товаров
            await db.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seller_id INTEGER,
                    title TEXT,
                    description TEXT,
                    price REAL,
                    data TEXT,  -- JSON с данными аккаунта
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    views INTEGER DEFAULT 0,
                    purchases INTEGER DEFAULT 0,
                    FOREIGN KEY (seller_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица заказов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    buyer_id INTEGER,
                    seller_id INTEGER,
                    product_id INTEGER,
                    price REAL,
                    stars_price INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    payment_method TEXT,  -- 'balance' или 'stars'
                    created_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    dispute_reason TEXT,
                    dispute_opened_at TIMESTAMP,
                    FOREIGN KEY (buyer_id) REFERENCES users (user_id),
                    FOREIGN KEY (seller_id) REFERENCES users (user_id),
                    FOREIGN KEY (product_id) REFERENCES products (product_id)
                )
            ''')
            
            # Таблица транзакций
            await db.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    stars_amount INTEGER DEFAULT 0,
                    type TEXT,  -- 'deposit', 'purchase', 'sale', 'refund', 'withdraw'
                    description TEXT,
                    created_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица отзывов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER,
                    from_user_id INTEGER,
                    to_user_id INTEGER,
                    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                    comment TEXT,
                    created_at TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders (order_id),
                    FOREIGN KEY (from_user_id) REFERENCES users (user_id),
                    FOREIGN KEY (to_user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица споров
            await db.execute('''
                CREATE TABLE IF NOT EXISTS disputes (
                    dispute_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER UNIQUE,
                    opened_by INTEGER,
                    reason TEXT,
                    status TEXT DEFAULT 'open',  -- 'open', 'resolved'
                    resolved_by INTEGER,
                    resolution TEXT,
                    resolved_at TIMESTAMP,
                    created_at TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders (order_id),
                    FOREIGN KEY (opened_by) REFERENCES users (user_id),
                    FOREIGN KEY (resolved_by) REFERENCES users (user_id)
                )
            ''')
            
            # Индексы для быстрого поиска
            await db.execute('CREATE INDEX IF NOT EXISTS idx_products_seller ON products(seller_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_orders_buyer ON orders(buyer_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_orders_seller ON orders(seller_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
            
            await db.commit()
    
    # ==================== ПОЛЬЗОВАТЕЛИ ====================
    
    async def add_user(self, user_id: int, username: str = None, 
                       first_name: str = None, last_name: str = None) -> bool:
        """Добавление нового пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute('''
                    INSERT OR IGNORE INTO users 
                    (user_id, username, first_name, last_name, registered_at, last_activity)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, username, first_name, last_name, 
                      datetime.now(), datetime.now()))
                await db.commit()
                return True
            except Exception as e:
                print(f"Error adding user: {e}")
                return False
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение пользователя по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def update_user_role(self, user_id: int, role: str) -> bool:
        """Обновление роли пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET role = ? WHERE user_id = ?', (role, user_id))
            await db.commit()
            return True
    
    async def update_user_activity(self, user_id: int) -> bool:
        """Обновление времени последней активности"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET last_activity = ? WHERE user_id = ?', 
                           (datetime.now(), user_id))
            await db.commit()
            return True
    
    # ==================== БАЛАНС ====================
    
    async def add_balance(self, user_id: int, amount: float) -> bool:
        """Пополнение баланса"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', 
                           (amount, user_id))
            await db.commit()
            return True
    
    async def add_stars(self, user_id: int, stars: int) -> bool:
        """Пополнение звёзд"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET stars_balance = stars_balance + ? WHERE user_id = ?', 
                           (stars, user_id))
            await db.commit()
            return True
    
    async def deduct_balance(self, user_id: int, amount: float) -> bool:
        """Списание с баланса"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?', 
                           (amount, user_id, amount))
            await db.commit()
            return True
    
    async def deduct_stars(self, user_id: int, stars: int) -> bool:
        """Списание звёзд"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET stars_balance = stars_balance - ? WHERE user_id = ? AND stars_balance >= ?', 
                           (stars, user_id, stars))
            await db.commit()
            return True
    
    # ==================== ТОВАРЫ ====================
    
    async def add_product(self, seller_id: int, title: str, description: str, 
                          price: float, data: dict) -> int:
        """Добавление товара"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO products 
                (seller_id, title, description, price, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (seller_id, title, description, price, json.dumps(data), 
                  datetime.now(), datetime.now()))
            await db.commit()
            return cursor.lastrowid
    
    async def get_product(self, product_id: int) -> Optional[Dict]:
        """Получение товара по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM products WHERE product_id = ?', (product_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    product = dict(row)
                    product['data'] = json.loads(product['data'])
                    return product
                return None
    
    async def get_active_products(self, exclude_user_id: int = None) -> List[Dict]:
        """Получение активных товаров"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = 'SELECT * FROM products WHERE is_active = 1'
            params = []
            
            if exclude_user_id:
                query += ' AND seller_id != ?'
                params.append(exclude_user_id)
            
            query += ' ORDER BY created_at DESC'
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                products = []
                for row in rows:
                    product = dict(row)
                    product['data'] = json.loads(product['data'])
                    products.append(product)
                return products
    
    async def get_user_products(self, user_id: int) -> List[Dict]:
        """Получение товаров пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM products WHERE seller_id = ? ORDER BY created_at DESC', 
                                 (user_id,)) as cursor:
                rows = await cursor.fetchall()
                products = []
                for row in rows:
                    product = dict(row)
                    product['data'] = json.loads(product['data'])
                    products.append(product)
                return products
    
    async def deactivate_product(self, product_id: int) -> bool:
        """Деактивация товара"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE products SET is_active = 0 WHERE product_id = ?', (product_id,))
            await db.commit()
            return True
    
    async def increment_product_views(self, product_id: int) -> bool:
        """Увеличение счетчика просмотров"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE products SET views = views + 1 WHERE product_id = ?', (product_id,))
            await db.commit()
            return True
    
    # ==================== ЗАКАЗЫ ====================
    
    async def create_order(self, buyer_id: int, seller_id: int, product_id: int, 
                          price: float, payment_method: str, stars_price: int = 0) -> int:
        """Создание заказа"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO orders 
                (buyer_id, seller_id, product_id, price, stars_price, status, payment_method, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (buyer_id, seller_id, product_id, price, stars_price, 'pending', 
                  payment_method, datetime.now()))
            await db.commit()
            return cursor.lastrowid
    
    async def get_order(self, order_id: int) -> Optional[Dict]:
        """Получение заказа по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def get_user_orders(self, user_id: int, as_buyer: bool = True) -> List[Dict]:
        """Получение заказов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            field = 'buyer_id' if as_buyer else 'seller_id'
            async with db.execute(f'SELECT * FROM orders WHERE {field} = ? ORDER BY created_at DESC', 
                                 (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def update_order_status(self, order_id: int, status: str, completed_at: datetime = None) -> bool:
        """Обновление статуса заказа"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE orders 
                SET status = ?, completed_at = ? 
                WHERE order_id = ?
            ''', (status, completed_at or datetime.now(), order_id))
            await db.commit()
            return True
    
    async def open_dispute(self, order_id: int, user_id: int, reason: str) -> bool:
        """Открытие спора"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE orders 
                SET status = 'disputed', dispute_reason = ?, dispute_opened_at = ? 
                WHERE order_id = ?
            ''', (reason, datetime.now(), order_id))
            
            await db.execute('''
                INSERT INTO disputes (order_id, opened_by, reason, created_at)
                VALUES (?, ?, ?, ?)
            ''', (order_id, user_id, reason, datetime.now()))
            
            await db.commit()
            return True
    
    # ==================== ТРАНЗАКЦИИ ====================
    
    async def add_transaction(self, user_id: int, amount: float, stars_amount: int,
                             type: str, description: str) -> bool:
        """Добавление транзакции"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO transactions (user_id, amount, stars_amount, type, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, amount, stars_amount, type, description, datetime.now()))
            await db.commit()
            return True
    
    # ==================== СТАТИСТИКА ====================
    
    async def get_user_stats(self, user_id: int) -> Dict:
        """Получение статистики пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем данные пользователя
            user = await self.get_user(user_id)
            
            # Получаем количество покупок
            async with db.execute('SELECT COUNT(*) FROM orders WHERE buyer_id = ?', (user_id,)) as cursor:
                total_purchases = (await cursor.fetchone())[0]
            
            # Получаем количество продаж
            async with db.execute('SELECT COUNT(*) FROM orders WHERE seller_id = ?', (user_id,)) as cursor:
                total_sales = (await cursor.fetchone())[0]
            
            # Получаем активные товары
            async with db.execute('SELECT COUNT(*) FROM products WHERE seller_id = ? AND is_active = 1', 
                                 (user_id,)) as cursor:
                active_products = (await cursor.fetchone())[0]
            
            return {
                'balance': user['balance'] if user else 0,
                'stars_balance': user['stars_balance'] if user else 0,
                'total_purchases': total_purchases,
                'total_sales': total_sales,
                'active_products': active_products
            }
    
    async def get_admin_stats(self) -> Dict:
        """Получение общей статистики для админа"""
        async with aiosqlite.connect(self.db_path) as db:
            stats = {}
            
            # Пользователи
            async with db.execute('SELECT COUNT(*) FROM users') as cursor:
                stats['total_users'] = (await cursor.fetchone())[0]
            
            async with db.execute('SELECT COUNT(*) FROM users WHERE role = "seller"') as cursor:
                stats['total_sellers'] = (await cursor.fetchone())[0]
            
            # Товары
            async with db.execute('SELECT COUNT(*) FROM products') as cursor:
                stats['total_products'] = (await cursor.fetchone())[0]
            
            async with db.execute('SELECT COUNT(*) FROM products WHERE is_active = 1') as cursor:
                stats['active_products'] = (await cursor.fetchone())[0]
            
            # Заказы
            async with db.execute('SELECT COUNT(*) FROM orders') as cursor:
                stats['total_orders'] = (await cursor.fetchone())[0]
            
            async with db.execute('SELECT COUNT(*) FROM orders WHERE status = "completed"') as cursor:
                stats['completed_orders'] = (await cursor.fetchone())[0]
            
            async with db.execute('SELECT COUNT(*) FROM orders WHERE status = "disputed"') as cursor:
                stats['disputed_orders'] = (await cursor.fetchone())[0]
            
            # Финансы
            async with db.execute('SELECT SUM(price) FROM orders WHERE status = "completed"') as cursor:
                stats['total_volume'] = (await cursor.fetchone())[0] or 0
            
            return stats

# Создаем глобальный экземпляр БД
db = Database()
