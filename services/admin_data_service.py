def _get_cursor(conn):
    try:
        conn.ping(True)
    except TypeError:
        conn.ping()
    return conn.cursor()


def fetch_all_stocks(conn):
    cur = _get_cursor(conn)
    cur.execute("SELECT `item_id`, `name`, `price`, `quantity`, `category`, `date` FROM `stocks` ORDER BY `id` ASC")
    return cur.fetchall()


def fetch_stock_by_item_id(conn, item_id):
    cur = _get_cursor(conn)
    cur.execute("SELECT * FROM stocks WHERE `item_id` = %s", (item_id,))
    return cur.fetchall()


def insert_stock(conn, item_id, name, price_value, quantity_value, category_value):
    cur = _get_cursor(conn)
    cur.execute(
        "INSERT INTO stocks (`item_id`, `name`, `price`, `quantity`, `category`) VALUES (%s, %s, %s, %s, %s)",
        (item_id, name, price_value, quantity_value, category_value),
    )


def update_stock(conn, item_id, name, price_value, quantity_value, category_value):
    cur = _get_cursor(conn)
    cur.execute(
        "UPDATE stocks SET `name`=%s, `price`=%s, `quantity`=%s, `category`=%s WHERE `item_id`=%s",
        (name, price_value, quantity_value, category_value, item_id),
    )


def count_active_orders_for_item(conn, item_id):
    cur = _get_cursor(conn)
    cur.execute(
        """
        SELECT COUNT(*) FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        WHERE oi.item_id = %s AND o.status IN ('Pending', 'Processing', 'Shipped')
        """,
        (item_id,),
    )
    row = cur.fetchone()
    return int(row[0]) if row else 0


def delete_stock_and_details(conn, item_id):
    cur = _get_cursor(conn)
    cur.execute("DELETE FROM product_details WHERE item_id = %s", (item_id,))
    cur.execute("DELETE FROM stocks WHERE `item_id` = %s", (item_id,))


def fetch_product_details(conn, item_id):
    cur = _get_cursor(conn)
    cur.execute(
        "SELECT description, image_path FROM product_details WHERE item_id = %s",
        (item_id,),
    )
    return cur.fetchone()


def save_product_details(conn, item_id, description, image_path):
    cur = _get_cursor(conn)
    if not any([description, image_path]):
        cur.execute("DELETE FROM product_details WHERE item_id = %s", (item_id,))
        return

    cur.execute(
        """
        INSERT INTO product_details (item_id, description, image_path)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            description = VALUES(description),
            image_path = VALUES(image_path)
        """,
        (item_id, description, image_path),
    )


def search_stocks(conn, item_id, name, normalized_price, quantity, category):
    params = []
    if item_id and item_id.strip():
        sql = "SELECT `item_id`, `name`, `price`, `quantity`, `category`, `date` FROM stocks WHERE `item_id` LIKE %s"
        params.append(f"%{item_id}%")
    elif name and name.strip():
        sql = "SELECT `item_id`, `name`, `price`, `quantity`, `category`, `date` FROM stocks WHERE `name` LIKE %s"
        params.append(f"%{name}%")
    elif normalized_price:
        sql = "SELECT `item_id`, `name`, `price`, `quantity`, `category`, `date` FROM stocks WHERE CAST(`price` AS CHAR) LIKE %s"
        params.append(f"%{normalized_price}%")
    elif quantity and quantity.strip():
        sql = "SELECT `item_id`, `name`, `price`, `quantity`, `category`, `date` FROM stocks WHERE CAST(`quantity` AS CHAR) LIKE %s"
        params.append(f"%{quantity}%")
    elif category and category.strip():
        sql = "SELECT `item_id`, `name`, `price`, `quantity`, `category`, `date` FROM stocks WHERE `category` LIKE %s"
        params.append(f"%{category}%")
    else:
        return []

    cur = _get_cursor(conn)
    cur.execute(sql, params)
    return cur.fetchall()


def fetch_stocks_for_export(conn):
    cur = _get_cursor(conn)
    cur.execute("SELECT `item_id`, `name`, `price`, `quantity`, `category`, `date` FROM stocks ORDER BY `id` DESC")
    return cur.fetchall()


def fetch_filtered_orders(conn, term, status):
    sql = "SELECT `order_id`, `customer_name`, `total_amount`, `order_date`, `status` FROM `orders` WHERE 1=1"
    params = []

    if term:
        sql += " AND (CAST(`order_id` AS CHAR) LIKE %s OR `customer_name` LIKE %s)"
        params.extend([f"%{term}%", f"%{term}%"])

    if status != "All":
        sql += " AND `status` = %s"
        params.append(status)

    sql += " ORDER BY `order_id` DESC"

    cur = _get_cursor(conn)
    cur.execute(sql, params)
    return cur.fetchall()


def fetch_order_items_for_restock(conn, order_id):
    cur = _get_cursor(conn)
    cur.execute("SELECT item_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
    return cur.fetchall()


def restock_items(conn, items):
    cur = _get_cursor(conn)
    for item_id, quantity in items:
        cur.execute("UPDATE stocks SET quantity = quantity + %s WHERE item_id = %s", (quantity, item_id))


def update_order_status(conn, order_id, new_status):
    cur = _get_cursor(conn)
    cur.execute("UPDATE orders SET status=%s WHERE order_id=%s", (new_status, order_id))


def fetch_order_header(conn, order_id):
    cur = _get_cursor(conn)
    cur.execute(
        """
        SELECT
            o.customer_name,
            o.contact_number,
            o.customer_address,
            o.customer_email,
            COALESCE(o.customer_username, c.username) AS customer_username,
            o.vat_amount,
            o.grand_total,
            o.payment_method,
            o.order_date,
            o.status
        FROM orders o
        LEFT JOIN customers c ON c.email = o.customer_email
        WHERE o.order_id=%s
        """,
        (order_id,),
    )
    return cur.fetchone()


def fetch_order_detail_items(conn, order_id):
    cur = _get_cursor(conn)
    cur.execute(
        """
        SELECT oi.item_id, s.name, oi.quantity, oi.price, (oi.quantity * oi.price) as subtotal
        FROM order_items oi
        LEFT JOIN stocks s ON oi.item_id = s.item_id
        WHERE oi.order_id = %s
        """,
        (order_id,),
    )
    return cur.fetchall()


def fetch_admin_for_login(conn, username):
    cur = _get_cursor(conn)
    cur.execute(
        """
        SELECT id, username, password, COALESCE(failed_login_count, 0),
               COALESCE(account_locked, 0), locked_until
        FROM users
        WHERE username = %s
        """,
        (username,),
    )
    return cur.fetchone()


def mark_admin_login_locked(conn, user_id, failed_count, current_time, locked_until):
    cur = _get_cursor(conn)
    cur.execute(
        """
        UPDATE users
        SET failed_login_count=%s, last_failed_login=%s, account_locked=1, locked_until=%s
        WHERE id=%s
        """,
        (failed_count, current_time, locked_until, user_id),
    )


def mark_admin_login_failed(conn, user_id, failed_count, current_time):
    cur = _get_cursor(conn)
    cur.execute(
        """
        UPDATE users
        SET failed_login_count=%s, last_failed_login=%s
        WHERE id=%s
        """,
        (failed_count, current_time, user_id),
    )


def reset_admin_login_status(conn, user_id, new_password_hash=None):
    cur = _get_cursor(conn)
    if new_password_hash:
        cur.execute(
            """
            UPDATE users
            SET password=%s, failed_login_count=0, last_failed_login=NULL, account_locked=0, locked_until=NULL
            WHERE id=%s
            """,
            (new_password_hash, user_id),
        )
        return

    cur.execute(
        """
        UPDATE users
        SET failed_login_count=0, last_failed_login=NULL, account_locked=0, locked_until=NULL
        WHERE id=%s
        """,
        (user_id,),
    )


def fetch_admin_user(conn, username):
    cur = _get_cursor(conn)
    cur.execute("SELECT id, password FROM users WHERE username=%s", (username,))
    return cur.fetchone()


def update_user_password(conn, user_id, new_hash):
    cur = _get_cursor(conn)
    cur.execute("UPDATE users SET password=%s WHERE id=%s", (new_hash, user_id))


def admin_exists(conn, username):
    cur = _get_cursor(conn)
    cur.execute("SELECT id FROM users WHERE username=%s", (username,))
    return cur.fetchone() is not None


def insert_admin_user(conn, username, password_hash, role="admin"):
    cur = _get_cursor(conn)
    cur.execute(
        "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
        (username, password_hash, role),
    )
