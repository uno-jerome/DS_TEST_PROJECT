import pymysql
import threading
from security_utils import hash_password

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",
    "db": "itc_database_admin",
}

_SESSION_CONNECTIONS = {}
_SESSION_LOCK = threading.Lock()


def _create_connection():
    return pymysql.connect(**DB_CONFIG)

# Centralized Database Connection
def connectDB():
    try:
        return _create_connection()
    except Exception as e:
        print("Error connecting to database:", e)
        return None


def get_session_connection(session_name="default"):
    with _SESSION_LOCK:
        existing_conn = _SESSION_CONNECTIONS.get(session_name)
        if existing_conn:
            try:
                existing_conn.ping(reconnect=True)
                return existing_conn
            except Exception:
                try:
                    existing_conn.close()
                except Exception:
                    pass
                _SESSION_CONNECTIONS.pop(session_name, None)

        try:
            session_conn = _create_connection()
            _SESSION_CONNECTIONS[session_name] = session_conn
            return session_conn
        except Exception as e:
            print(f"Error creating session connection '{session_name}':", e)
            return None


def close_session_connection(session_name="default"):
    with _SESSION_LOCK:
        session_conn = _SESSION_CONNECTIONS.pop(session_name, None)

    if session_conn:
        try:
            session_conn.close()
        except Exception:
            pass


def close_all_session_connections():
    with _SESSION_LOCK:
        session_names = list(_SESSION_CONNECTIONS.keys())

    for session_name in session_names:
        close_session_connection(session_name)

# Combined initialization for all tables (Admin & Shop)
def setup_database():
    try:
        conn = connectDB()
        if not conn:
            return

        cursor = conn.cursor()

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
        
        # Fast-path startup: skip heavy migration queries if schema is already current.
        required_tables = ["users", "stocks", "orders", "customers", "order_items", "product_details"]
        schema_ready = all(table_exists(tbl) for tbl in required_tables) and all(
            [
                column_exists("users", "locked_until"),
                column_exists("customers", "locked_until"),
                column_exists("orders", "customer_email"),
                column_exists("product_details", "image_path"),
                index_exists("stocks", "ux_stocks_item_id"),
                index_exists("product_details", "ux_product_details_item_id"),
            ]
        )
        if schema_ready:
            conn.close()
            print("Database setup skipped (schema already current).")
            return


        # 1. users table for admin login
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'admin'
            )
        ''')
        # Expand password column for modern hash formats and lockout fields.
        try_alter("ALTER TABLE users MODIFY password VARCHAR(255) NOT NULL;")
        try_alter("ALTER TABLE users ADD COLUMN failed_login_count INT DEFAULT 0;")
        try_alter("ALTER TABLE users ADD COLUMN last_failed_login DATETIME NULL;")
        try_alter("ALTER TABLE users ADD COLUMN account_locked TINYINT(1) DEFAULT 0;")
        try_alter("ALTER TABLE users ADD COLUMN locked_until DATETIME NULL;")

        # Create a default admin account if none exists, with a hashed password
        cursor.execute("SELECT * FROM users")
        if len(cursor.fetchall()) == 0:
            default_hashed_pw = hash_password("admin123")
            cursor.execute(
                "INSERT IGNORE INTO users (username, password, role) VALUES (%s, %s, %s)",
                ("admin", default_hashed_pw, "admin"),
            )
            
        # Security Patch: Auto-migrate any unhashed 'admin123' to hashed format
        cursor.execute("SELECT id FROM users WHERE password = %s", ("admin123",))
        unhashed = cursor.fetchall()
        if len(unhashed) > 0:
            hashed_pw = hash_password("admin123")
            cursor.execute(
                "UPDATE users SET password = %s WHERE password = %s",
                (hashed_pw, "admin123"),
            )
        
        # 2. stocks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                item_id VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                quantity INT NOT NULL,
                category VARCHAR(50),
                date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try_alter("ALTER TABLE stocks MODIFY item_id VARCHAR(50) NOT NULL;")
        try_alter("ALTER TABLE stocks ADD UNIQUE INDEX ux_stocks_item_id (item_id);")
        try_alter("ALTER TABLE stocks ADD INDEX idx_stocks_category_name (category, name);")
        try_alter("ALTER TABLE stocks ENGINE=InnoDB;")

        # 3. orders table (with new Phase 4 fields and Address/Contact)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id INT AUTO_INCREMENT PRIMARY KEY,
                customer_name VARCHAR(100),
                contact_number VARCHAR(50),
                customer_address VARCHAR(255),
                total_amount DECIMAL(10, 2),
                vat_amount DECIMAL(10, 2) DEFAULT 0.00,
                grand_total DECIMAL(10, 2) DEFAULT 0.00,
                payment_method VARCHAR(50) DEFAULT 'Cash',
                order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(50) DEFAULT 'Pending'
            )
        ''')
        # Try to add new columns to an existing orders table if they don't exist
        try_alter("ALTER TABLE orders ADD COLUMN vat_amount DECIMAL(10, 2) DEFAULT 0.00;")
        try_alter("ALTER TABLE orders ADD COLUMN grand_total DECIMAL(10, 2) DEFAULT 0.00;")
        try_alter("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(50) DEFAULT 'Cash';")
        try_alter("ALTER TABLE orders ADD COLUMN contact_number VARCHAR(50);")
        try_alter("ALTER TABLE orders ADD INDEX idx_orders_customer_email (customer_email);")
        try_alter("ALTER TABLE orders ADD INDEX idx_orders_order_date (order_date);")
        try_alter("ALTER TABLE orders ADD INDEX idx_orders_status (status);")
        
        # 4. customers table (Phase 5 Authentication)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(100) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(100),
                contact_number VARCHAR(50),
                address VARCHAR(255),
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try_alter("ALTER TABLE customers MODIFY password_hash VARCHAR(255) NOT NULL;")
        try_alter("ALTER TABLE customers ADD COLUMN failed_login_count INT DEFAULT 0;")
        try_alter("ALTER TABLE customers ADD COLUMN last_failed_login DATETIME NULL;")
        try_alter("ALTER TABLE customers ADD COLUMN account_locked TINYINT(1) DEFAULT 0;")
        try_alter("ALTER TABLE customers ADD COLUMN locked_until DATETIME NULL;")
        try_alter("ALTER TABLE orders ADD COLUMN customer_address VARCHAR(255);")
        try_alter("ALTER TABLE orders ADD COLUMN customer_email VARCHAR(100);")
        
        # 4. order_items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT,
                item_id VARCHAR(50),
                quantity INT,
                price DECIMAL(10, 2)
            )
        ''')
        try_alter("ALTER TABLE order_items ADD INDEX idx_order_items_order_id (order_id);")
        try_alter("ALTER TABLE order_items ADD INDEX idx_order_items_item_id (item_id);")

        # 5. product_details table for richer buyer-facing catalog data.
        # Create table first without FK to avoid migration failures on legacy schemas.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_details (
                id INT AUTO_INCREMENT PRIMARY KEY,
                item_id VARCHAR(50) NOT NULL UNIQUE,
                description TEXT,
                specs_json TEXT,
                image_path VARCHAR(255),
                return_policy_text TEXT
            ) ENGINE=InnoDB
        ''')

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

        conn.commit()
        conn.close()
        print("Database setup complete.")
    except Exception as e:
        print("Database structure check error:", e)

if __name__ == "__main__":
    setup_database()
