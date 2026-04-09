def _get_cursor(conn):
    try:
        conn.ping(True)
    except TypeError:
        conn.ping()
    return conn.cursor()


NORMALIZED_CONTACT_SQL = "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(contact_number, '+', ''), ' ', ''), '-', ''), '(', ''), ')', '')"


def fetch_customer_for_email_or_username(conn, identifier):
    cur = _get_cursor(conn)
    cur.execute(
        """
        SELECT id, username, email, name, contact_number, address, password_hash,
               COALESCE(failed_login_count, 0), COALESCE(account_locked, 0), locked_until
        FROM customers
        WHERE LOWER(email) = LOWER(%s) OR LOWER(username) = LOWER(%s)
        LIMIT 1
        """,
        (identifier, identifier),
    )
    return cur.fetchone()


def fetch_customer_for_login_identifier(conn, identifier):
    return fetch_customer_for_email_or_username(conn, identifier)


def fetch_customers_by_contact_variants(conn, contact_variants):
    if not contact_variants:
        return []

    normalized_variants = [str(value).strip() for value in contact_variants if str(value).strip()]
    if not normalized_variants:
        return []

    placeholders = ", ".join(["%s"] * len(normalized_variants))
    cur = _get_cursor(conn)
    cur.execute(
        f"""
        SELECT id, username, email, name, contact_number, address, password_hash,
               COALESCE(failed_login_count, 0), COALESCE(account_locked, 0), locked_until
        FROM customers
        WHERE {NORMALIZED_CONTACT_SQL} IN ({placeholders})
        ORDER BY id ASC
        """,
        tuple(normalized_variants),
    )
    return cur.fetchall()


def fetch_customers_for_contact_login(conn, contact_variants):
    return fetch_customers_by_contact_variants(conn, contact_variants)


def mark_customer_login_locked(conn, customer_id, failed_count, current_time, locked_until):
    cur = _get_cursor(conn)
    cur.execute(
        """
        UPDATE customers
        SET failed_login_count=%s, last_failed_login=%s, account_locked=1, locked_until=%s
        WHERE id=%s
        """,
        (failed_count, current_time, locked_until, customer_id),
    )


def mark_customer_login_failed(conn, customer_id, failed_count, current_time):
    cur = _get_cursor(conn)
    cur.execute(
        """
        UPDATE customers
        SET failed_login_count=%s, last_failed_login=%s
        WHERE id=%s
        """,
        (failed_count, current_time, customer_id),
    )


def reset_customer_login_status(conn, customer_id, new_password_hash=None):
    cur = _get_cursor(conn)
    if new_password_hash:
        cur.execute(
            """
            UPDATE customers
            SET password_hash=%s, failed_login_count=0, last_failed_login=NULL, account_locked=0, locked_until=NULL
            WHERE id=%s
            """,
            (new_password_hash, customer_id),
        )
        return

    cur.execute(
        """
        UPDATE customers
        SET failed_login_count=0, last_failed_login=NULL, account_locked=0, locked_until=NULL
        WHERE id=%s
        """,
        (customer_id,),
    )


def customer_exists_by_email(conn, email):
    cur = _get_cursor(conn)
    cur.execute("SELECT email FROM customers WHERE email=%s", (email,))
    return cur.fetchone() is not None


def customer_exists_by_username(conn, username):
    cur = _get_cursor(conn)
    cur.execute("SELECT username FROM customers WHERE LOWER(username)=LOWER(%s)", (username,))
    return cur.fetchone() is not None


def customer_exists_by_contact_variants(conn, contact_variants):
    if not contact_variants:
        return False

    normalized_variants = [str(value).strip() for value in contact_variants if str(value).strip()]
    if not normalized_variants:
        return False

    placeholders = ", ".join(["%s"] * len(normalized_variants))
    cur = _get_cursor(conn)
    cur.execute(
        f"SELECT id FROM customers WHERE {NORMALIZED_CONTACT_SQL} IN ({placeholders}) LIMIT 1",
        tuple(normalized_variants),
    )
    return cur.fetchone() is not None


def insert_customer(conn, email, username, password_hash, name, contact_number, address):
    cur = _get_cursor(conn)
    cur.execute(
        """
        INSERT INTO customers (email, username, password_hash, name, contact_number, address)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (email, username, password_hash, name, contact_number, address),
    )


def fetch_available_products(conn, search_term="", category="All Categories"):
    sql = "SELECT `item_id`, `name`, `price`, `quantity`, `category` FROM `stocks` WHERE CAST(`quantity` AS DECIMAL(10,2)) > 0"
    params = []

    if category != "All Categories":
        sql += " AND `category` = %s"
        params.append(category)

    if search_term:
        sql += " AND `name` LIKE %s"
        params.append(f"%{search_term}%")

    sql += " ORDER BY `name` ASC"

    cur = _get_cursor(conn)
    cur.execute(sql, params)
    return cur.fetchall()


def fetch_product_details(conn, item_id):
    cur = _get_cursor(conn)
    cur.execute(
        """
        SELECT
            s.item_id,
            s.name,
            s.price,
            s.quantity,
            s.category,
            pd.description,
            pd.specs_json,
            pd.image_path,
            pd.return_policy_text
        FROM stocks s
        LEFT JOIN product_details pd ON pd.item_id = s.item_id
        WHERE s.item_id = %s
        """,
        (item_id,),
    )
    row = cur.fetchone()
    if not row:
        return None

    return {
        "item_id": row[0],
        "name": row[1],
        "price": row[2],
        "quantity": row[3],
        "category": row[4],
        "description": row[5],
        "specs_json": row[6],
        "image_path": row[7],
        "return_policy_text": row[8],
    }


def create_order(
    conn,
    order_id,
    customer_name,
    customer_username,
    customer_email,
    contact_number,
    customer_address,
    subtotal,
    vat,
    grand_total,
    payment_method,
    order_date,
    status="Pending",
):
    cur = _get_cursor(conn)
    cur.execute(
        """
        INSERT INTO orders (
            order_id, customer_name, customer_username, customer_email, contact_number, customer_address,
            total_amount, vat_amount, grand_total, payment_method, order_date, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            order_id,
            customer_name,
            customer_username,
            customer_email,
            contact_number,
            customer_address,
            subtotal,
            vat,
            grand_total,
            payment_method,
            order_date,
            status,
        ),
    )
    return order_id


def order_id_exists(conn, order_id):
    cur = _get_cursor(conn)
    cur.execute("SELECT 1 FROM orders WHERE order_id = %s LIMIT 1", (order_id,))
    return cur.fetchone() is not None


def insert_order_item(conn, order_id, item_id, quantity, price):
    cur = _get_cursor(conn)
    cur.execute(
        "INSERT INTO order_items (order_id, item_id, quantity, price) VALUES (%s, %s, %s, %s)",
        (order_id, item_id, quantity, price),
    )


def decrement_stock(conn, item_id, quantity):
    cur = _get_cursor(conn)
    cur.execute(
        "UPDATE stocks SET quantity = CAST(quantity AS SIGNED) - %s WHERE item_id = %s AND CAST(quantity AS SIGNED) >= %s",
        (quantity, item_id, quantity),
    )
    return int(cur.rowcount)


def fetch_customer_orders(conn, email):
    cur = _get_cursor(conn)
    cur.execute(
        "SELECT order_id, order_date, grand_total, status FROM orders WHERE customer_email = %s ORDER BY order_date DESC, order_id DESC",
        (email,),
    )
    return cur.fetchall()
