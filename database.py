import os
import threading

import MySQLdb

from security_utils import hash_password


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "passwd": os.getenv("DB_PASSWORD", "root"),
    "db": os.getenv("DB_NAME", "itc_database_admin"),
    "port": _safe_int(os.getenv("DB_PORT", "3306"), 3306),
    "charset": "utf8mb4",
    "connect_timeout": 10,
    "autocommit": False,
    "use_unicode": True,
}

_SESSION_CONNECTIONS = {}
_SESSION_LOCK = threading.Lock()


def _create_connection():
    return MySQLdb.connect(**DB_CONFIG)


def _ping_connection(connection):
    try:
        connection.ping(True)
    except TypeError:
        connection.ping()


def connectDB():
    try:
        return _create_connection()
    except Exception as error:
        print("Error connecting to database:", error)
        return None


def get_session_connection(session_name="default"):
    with _SESSION_LOCK:
        existing_connection = _SESSION_CONNECTIONS.get(session_name)
        if existing_connection:
            try:
                _ping_connection(existing_connection)
                return existing_connection
            except Exception:
                try:
                    existing_connection.close()
                except Exception:
                    pass
                _SESSION_CONNECTIONS.pop(session_name, None)

        try:
            session_connection = _create_connection()
            _SESSION_CONNECTIONS[session_name] = session_connection
            return session_connection
        except Exception as error:
            print(f"Error creating session connection '{session_name}':", error)
            return None


def close_session_connection(session_name="default"):
    with _SESSION_LOCK:
        session_connection = _SESSION_CONNECTIONS.pop(session_name, None)

    if session_connection:
        try:
            session_connection.close()
        except Exception:
            pass


def close_all_session_connections():
    with _SESSION_LOCK:
        session_names = list(_SESSION_CONNECTIONS.keys())

    for session_name in session_names:
        close_session_connection(session_name)


def setup_database():
    try:
        connection = connectDB()
        if not connection:
            return

        cursor = connection.cursor()

        def try_alter(sql_statement):
            try:
                cursor.execute(sql_statement)
            except Exception:
                pass

        def table_exists(table_name):
            cursor.execute("SHOW TABLES LIKE %s", (table_name,))
            return cursor.fetchone() is not None

        def column_exists(table_name, column_name):
            cursor.execute(
                """
                SELECT 1
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND COLUMN_NAME = %s
                LIMIT 1
                """,
                (table_name, column_name),
            )
            return cursor.fetchone() is not None

        def index_exists(table_name, index_name):
            cursor.execute(
                """
                SELECT 1
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND INDEX_NAME = %s
                LIMIT 1
                """,
                (table_name, index_name),
            )
            return cursor.fetchone() is not None

        required_tables = ["users", "stocks", "orders", "customers", "order_items", "product_details"]
        schema_ready = all(table_exists(table_name) for table_name in required_tables) and all(
            [
                column_exists("users", "locked_until"),
                column_exists("customers", "locked_until"),
                column_exists("customers", "username"),
                column_exists("orders", "customer_email"),
                column_exists("orders", "customer_username"),
                column_exists("product_details", "image_path"),
                index_exists("stocks", "ux_stocks_item_id"),
                index_exists("customers", "ux_customers_username"),
                index_exists("product_details", "ux_product_details_item_id"),
            ]
        )
        if schema_ready:
            connection.close()
            print("Database setup skipped (schema already current).")
            return

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'admin'
            )
            """
        )
        try_alter("ALTER TABLE users MODIFY password VARCHAR(255) NOT NULL;")
        try_alter("ALTER TABLE users ADD COLUMN failed_login_count INT DEFAULT 0;")
        try_alter("ALTER TABLE users ADD COLUMN last_failed_login DATETIME NULL;")
        try_alter("ALTER TABLE users ADD COLUMN account_locked TINYINT(1) DEFAULT 0;")
        try_alter("ALTER TABLE users ADD COLUMN locked_until DATETIME NULL;")

        cursor.execute("SELECT COUNT(*) FROM users")
        existing_user_count = int(cursor.fetchone()[0] or 0)
        if existing_user_count == 0:
            default_hashed_password = hash_password("admin123")
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                ("admin", default_hashed_password, "admin"),
            )

        cursor.execute("SELECT id FROM users WHERE password = %s", ("admin123",))
        unhashed_rows = cursor.fetchall()
        if unhashed_rows:
            hashed_password = hash_password("admin123")
            cursor.execute(
                "UPDATE users SET password = %s WHERE password = %s",
                (hashed_password, "admin123"),
            )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stocks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                item_id VARCHAR(50) UNIQUE NOT NULL,
                name MEDIUMTEXT,
                price MEDIUMTEXT,
                quantity MEDIUMTEXT,
                category MEDIUMTEXT,
                date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
            """
        )
        try_alter("ALTER TABLE stocks MODIFY item_id VARCHAR(50) NOT NULL;")
        try_alter("ALTER TABLE stocks ADD UNIQUE INDEX ux_stocks_item_id (item_id);")
        try_alter("ALTER TABLE stocks ADD INDEX idx_stocks_category_name (category(100), name(100));")
        try_alter("ALTER TABLE stocks ENGINE=InnoDB;")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id BIGINT PRIMARY KEY,
                customer_name VARCHAR(100),
                total_amount DECIMAL(10, 2),
                order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(50) DEFAULT 'Pending',
                vat_amount DECIMAL(10, 2) DEFAULT 0.00,
                grand_total DECIMAL(10, 2) DEFAULT 0.00,
                payment_method VARCHAR(50) DEFAULT 'Cash',
                contact_number VARCHAR(50),
                customer_address VARCHAR(255),
                customer_email VARCHAR(100),
                customer_username VARCHAR(50)
            ) ENGINE=InnoDB
            """
        )
        try_alter("ALTER TABLE orders MODIFY order_id BIGINT NOT NULL;")
        try_alter("ALTER TABLE orders ADD COLUMN vat_amount DECIMAL(10, 2) DEFAULT 0.00;")
        try_alter("ALTER TABLE orders ADD COLUMN grand_total DECIMAL(10, 2) DEFAULT 0.00;")
        try_alter("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(50) DEFAULT 'Cash';")
        try_alter("ALTER TABLE orders ADD COLUMN contact_number VARCHAR(50);")
        try_alter("ALTER TABLE orders ADD COLUMN customer_address VARCHAR(255);")
        try_alter("ALTER TABLE orders ADD COLUMN customer_email VARCHAR(100);")
        try_alter("ALTER TABLE orders ADD COLUMN customer_username VARCHAR(50);")
        try_alter("ALTER TABLE orders ADD INDEX idx_orders_customer_email (customer_email);")
        try_alter("ALTER TABLE orders ADD INDEX idx_orders_customer_username (customer_username);")
        try_alter("ALTER TABLE orders ADD INDEX idx_orders_order_date (order_date);")
        try_alter("ALTER TABLE orders ADD INDEX idx_orders_status (status);")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(100) NOT NULL UNIQUE,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(100),
                contact_number VARCHAR(50),
                address VARCHAR(255),
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
            """
        )
        try_alter("ALTER TABLE customers MODIFY password_hash VARCHAR(255) NOT NULL;")
        try_alter("ALTER TABLE customers ADD COLUMN username VARCHAR(50) NULL;")
        try_alter("ALTER TABLE customers ADD COLUMN failed_login_count INT DEFAULT 0;")
        try_alter("ALTER TABLE customers ADD COLUMN last_failed_login DATETIME NULL;")
        try_alter("ALTER TABLE customers ADD COLUMN account_locked TINYINT(1) DEFAULT 0;")
        try_alter("ALTER TABLE customers ADD COLUMN locked_until DATETIME NULL;")

        cursor.execute("SELECT id, username FROM customers ORDER BY id ASC")
        customer_username_rows = cursor.fetchall() or []
        assigned_usernames = set()
        for customer_id, existing_username in customer_username_rows:
            normalized_username = str(existing_username or "").strip()
            if not normalized_username:
                normalized_username = f"buyer{int(customer_id)}"

            base_username = normalized_username
            suffix = 1
            while normalized_username.lower() in assigned_usernames:
                normalized_username = f"{base_username}_{suffix}"
                suffix += 1

            if str(existing_username or "").strip() != normalized_username:
                cursor.execute(
                    "UPDATE customers SET username = %s WHERE id = %s",
                    (normalized_username, customer_id),
                )

            assigned_usernames.add(normalized_username.lower())

        try_alter("ALTER TABLE customers MODIFY username VARCHAR(50) NOT NULL;")
        try_alter("ALTER TABLE customers ADD UNIQUE INDEX ux_customers_username (username);")
        try_alter("ALTER TABLE customers ADD INDEX idx_customers_contact_number (contact_number);")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id BIGINT,
                item_id VARCHAR(50),
                quantity INT,
                price DECIMAL(10, 2)
            ) ENGINE=InnoDB
            """
        )
        try_alter("ALTER TABLE order_items MODIFY order_id BIGINT;")
        try_alter("ALTER TABLE order_items ADD INDEX idx_order_items_order_id (order_id);")
        try_alter("ALTER TABLE order_items ADD INDEX idx_order_items_item_id (item_id);")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS product_details (
                id INT AUTO_INCREMENT PRIMARY KEY,
                item_id VARCHAR(50) NOT NULL UNIQUE,
                description TEXT,
                specs_json TEXT,
                image_path VARCHAR(255),
                return_policy_text TEXT
            ) ENGINE=InnoDB
            """
        )
        try_alter("ALTER TABLE product_details ADD COLUMN description TEXT;")
        try_alter("ALTER TABLE product_details ADD COLUMN specs_json TEXT;")
        try_alter("ALTER TABLE product_details ADD COLUMN image_path VARCHAR(255);")
        try_alter("ALTER TABLE product_details ADD COLUMN return_policy_text TEXT;")
        try_alter("ALTER TABLE product_details MODIFY item_id VARCHAR(50) NOT NULL;")
        try_alter("ALTER TABLE product_details ADD UNIQUE INDEX ux_product_details_item_id (item_id);")
        try_alter("ALTER TABLE product_details ENGINE=InnoDB;")
        try_alter(
            """
            ALTER TABLE product_details
            ADD CONSTRAINT fk_product_details_item_id
            FOREIGN KEY (item_id) REFERENCES stocks(item_id)
            ON DELETE CASCADE ON UPDATE CASCADE
            """
        )

        connection.commit()
        connection.close()
        print("Database setup complete.")
    except Exception as error:
        print("Database structure check error:", error)


if __name__ == "__main__":
    setup_database()
