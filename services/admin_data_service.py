def _get_cursor(conn):
    conn.ping(reconnect=True)
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
        SELECT customer_name, contact_number, customer_address,
               vat_amount, grand_total, payment_method, order_date, status
        FROM orders WHERE order_id=%s
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
